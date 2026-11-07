# -*- coding: utf-8 -*-

"""
Create a ComicInfo.xml metadata file and export it into comic archives
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from os import replace, stat
from os.path import basename, dirname, join, splitext
from shutil import chown, copy2, copystat
from tempfile import TemporaryDirectory
from typing import Dict, List, Sequence, Union
from zipfile import ZIP_DEFLATED, ZipFile

from bs4 import BeautifulSoup

from backend.base.definitions import (SV_TO_FULL_TERM, ExtendedIssueMetadata,
                                      IssueData, OSType, VolumeData)
from backend.base.helpers import get_os_type, run_rar
from backend.implementations.comicvine import _clean_description
from backend.internals.settings import System

FILENAME = 'ComicInfo.xml'
ZIP_EXTS = ('.cbz', '.zip')
RAR_EXTS = ('.cbr', '.rar')

FIELD_ORDER = (
    'Title', 'Series', 'Number', 'Volume', 'Summary', 'Notes',
    'Year', 'Month', 'Day',
    'Writer', 'Penciller', 'Inker', 'Colorist', 'Letterer', 'CoverArtist',
    'Editor', 'Publisher', 'Web', 'Format',
    'Characters', 'Teams', 'Locations', 'StoryArc'
)

ROLE_PATTERNS = {
    'CoverArtist': re.compile(r'\bcover'),
    'Writer': re.compile(r'\b(writ|script|plot|story\b)'),
    'Penciller': re.compile(r'\b(pencil|art|breakdown)'),
    'Inker': re.compile(r'\b(ink|finish)'),
    'Colorist': re.compile(r'\b(color|colour)'),
    'Letterer': re.compile(r'\b(letter)'),
    'Editor': re.compile(r'\b(editor)')
}


# region Content
def _clean_html(html: Union[str, None]) -> Union[str, None]:
    if not html:
        return None

    soup = BeautifulSoup(_clean_description(html), 'html.parser')
    for br in soup.find_all('br'):
        br.replace_with('\n')
    for p in soup.find_all('p'):
        p.append('\n\n')

    text = soup.get_text().replace('\xa0', ' ')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip() or None


def _map_extended_metadata(
    extended_metadata: Sequence[Union[ExtendedIssueMetadata, None]]
) -> Dict[str, str]:
    result: Dict[str, Dict[str, None]] = {}

    def add(field: str, name: str) -> None:
        if clean_name := name.replace(',', '').strip():
            result.setdefault(field, {})[clean_name] = None

    for metadata in filter(None, extended_metadata):
        for name, roles in metadata['people']:
            for role in roles.split(','):
                for field, pattern in ROLE_PATTERNS.items():
                    if pattern.search(role.strip().lower()):
                        add(field, name)
                        break

        for field in ('Characters', 'Teams', 'Locations', 'StoryArc'):
            for name in metadata.get(field.lower(), []):
                add(field, name)

    return {field: ', '.join(names) for field, names in result.items()}


def _build_fields(
    volume: VolumeData,
    issues: Sequence[IssueData],
    extended_metadata: Sequence[Union[ExtendedIssueMetadata, None]]
) -> Dict[str, str]:
    issue = issues[0]
    fields = {
        'Series': volume.title,
        'Number': issue.issue_number,
        'Volume': volume.volume_number,
        'Publisher': volume.publisher,
        'Format': SV_TO_FULL_TERM.get(volume.special_version)
    }

    try:
        date = datetime.strptime(issue.date or '', '%Y-%m-%d')
        fields.update({'Year': date.year, 'Month': date.month, 'Day': date.day})
    except ValueError:
        fields['Year'] = volume.year

    if len(issues) == 1:
        fields['Title'] = issue.title
        fields['Summary'] = _clean_html(issue.description)
        fields['Web'] = issue.site_url
        fields['Notes'] = (
            f'Exported by Kapowarr. [Issue ID {issue.comicvine_id}]')
    else:
        fields['Web'] = volume.site_url
        fields['Notes'] = (
            f'Exported by Kapowarr. [Volume ID {volume.comicvine_id}]')

    fields.update(_map_extended_metadata(extended_metadata))
    return {k: str(v) for k, v in fields.items() if v}


def _build_xml(fields: Dict[str, str]) -> bytes:
    root = ET.Element('ComicInfo')
    for name in FIELD_ORDER:
        if name in fields:
            ET.SubElement(root, name).text = fields[name]

    # Added for compatibility with 3.8
    if hasattr(ET, 'indent'): # TODO: remove once python is >= 3.9
        ET.indent(root, space='  ')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


# region Archives
def _is_zip(filepath: str) -> bool:
    return splitext(filepath)[1].lower() in ZIP_EXTS


def _is_rar(filepath: str) -> bool:
    return splitext(filepath)[1].lower() in RAR_EXTS


def can_export(filepath: str) -> bool:
    """Check if the file extension is supported to export metadata.

    Args:
        filepath (str): The filepath of the archive.

    Returns:
        bool: Whether the file is supported for metadata export.
    """
    return _is_zip(filepath) or _is_rar(filepath)


def _find_comicinfo(filepath: str) -> List[str]:
    if _is_zip(filepath):
        with ZipFile(filepath) as zip:
            names = zip.namelist()

    else:
        result = run_rar([
            'lb',
            filepath
        ])
        if result.returncode != 0:
            raise OSError(
                f'Failed to list files with rar: Error {result.returncode}')
        names = [n.strip() for n in result.stdout.splitlines()]

    return [n for n in names if n.lower() == FILENAME.lower()]


def has_comicinfo(filepath: str) -> bool:
    """Check if an archive has a ComicInfo.xml file.

    Args:
        filepath (str): The filepath of the archive.

    Raises:
        BadZipFile: The zip archive is not valid.
        OSError: The archive couldn't be read.

    Returns:
        bool: Whether the archive has a ComicInfo.xml file.
    """
    return bool(_find_comicinfo(filepath))


def _zip_with_xml(source: str, target: str, xml: bytes) -> None:
    if not has_comicinfo(filepath=source):
        copy2(source, target)
        with ZipFile(target, 'a') as zip:
            zip.writestr(FILENAME, xml, ZIP_DEFLATED)
        return

    with ZipFile(source) as zin, ZipFile(target, 'w') as zout:
        zout.comment = zin.comment
        for item in zin.infolist():
            if item.filename.lower() != FILENAME.lower():
                zout.writestr(item, data=zin.read(item))
        zout.writestr(FILENAME, xml, ZIP_DEFLATED)
    return


def _rar_with_xml(source: str, target: str, xml: bytes) -> None:
    copy2(source, target)

    for name in _find_comicinfo(target):
        result = run_rar([
            'd',
            '-inul',
            target,
            name
        ])
        if result.returncode != 0:
            raise OSError(
                f'Failed to remove from rar: Error {result.returncode}')

    xml_file = join(dirname(target), FILENAME)
    with open(xml_file, 'wb') as f:
        f.write(xml)

    result = run_rar([
        'a',
        '-ep',
        '-inul',
        target,
        xml_file
    ])
    if result.returncode != 0:
        raise OSError(f'Failed to add to rar: Error {result.returncode}')
    return


def export_comicinfo(
    filepath: str,
    volume: VolumeData,
    issues: Sequence[IssueData],
    extended_metadata: Sequence[Union[ExtendedIssueMetadata, None]] = ()
) -> None:
    """Export metadata as a ComicInfo.xml into the comic archive file.

    Args:
        filepath (str): The filepath of the archive.

        volume (VolumeData): The volume that the archive is in.

        issues (Sequence[IssueData]): The issue(s) in the archive.

        extended_metadata (Sequence[Union[ExtendedIssueMetadata, None]], optional):
            The extended metadata of the archive's issues.
            Defaults to ().

    Raises:
        BadZipFile: The zip archive is not valid.
        OSError: The archive couldn't be read.
    """
    xml = _build_xml(_build_fields(volume, issues, extended_metadata))

    # Make edits on temporary file
    with TemporaryDirectory(
        dir=dirname(filepath), prefix='.kapowarr-'
    ) as folder:
        target = join(folder, basename(filepath))

        if _is_zip(filepath):
            _zip_with_xml(filepath, target, xml)
        else:
            _rar_with_xml(filepath, target, xml)

        copystat(filepath, target)
        if get_os_type() in (OSType.LINUX, OSType.MACOS):
            st = stat(filepath)
            try:
                chown(target, st.st_uid, st.st_gid)
            except OSError:
                pass

        replace(target, filepath)
    return
