# -*- coding: utf-8 -*-

"""
Create a ComicInfo.xml metadata file and embed it in comic archives
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from os import replace, stat
from pathlib import Path
from shutil import chown, copy2, copystat
from tempfile import TemporaryDirectory
from typing import Dict, Sequence, Union
from zipfile import ZIP_DEFLATED, ZipFile

from bs4 import BeautifulSoup

from backend.base.definitions import (IssueCredits, IssueData,
                                      OSType, VolumeData)
from backend.base.files import get_archive_mimetype
from backend.base.helpers import get_os_type, run_rar
from backend.implementations.comicvine import _clean_description
from backend.internals.settings import System

FILENAME = 'ComicInfo.xml'
FILE_EXTS = ('.cbz', '.zip', '.cbr', '.rar')

FIELD_ORDER = (
    'Title', 'Series', 'Number', 'Volume', 'Summary', 'Notes',
    'Year', 'Month', 'Day',
    'Writer', 'Penciller', 'Inker', 'Colorist', 'Letterer', 'CoverArtist',
    'Editor', 'Publisher', 'Web', 'Format',
    'Characters', 'Teams', 'Locations', 'StoryArc'
)

ROLE_PATTERNS = {
    'CoverArtist': re.compile(r'\bcover'),
    'Writer': re.compile(r'\b(writ|script|plot|story)'),
    'Penciller': re.compile(r'\b(pencil|art|breakdown)'),
    'Inker': re.compile(r'\b(ink|finish)'),
    'Colorist': re.compile(r'\b(color|colour)'),
    'Letterer': re.compile(r'\b(letter)'),
    'Editor': re.compile(r'\b(editor)')
}

# Data Formatting


def _clean_html(html: Union[str, None]) -> Union[str, None]:
    if not html:
        return None
    html = _clean_description(html)
    soup = BeautifulSoup(html, 'html.parser')
    for br in soup.find_all('br'):
        br.replace_with('\n')
    for p in soup.find_all('p'):
        p.append('\n\n')

    text = soup.get_text().replace('\xa0', ' ')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip() or None


def _map_credits(
    credits: Sequence[Union[IssueCredits, None]]) -> Dict[str, str]:
    result_map: Dict[str, Dict[str, None]] = {}

    def add(field: str, name: str):
        if clean_name := name.replace(',', '').strip():
            result_map.setdefault(field, {})[clean_name] = None

    for credit in filter(None, credits):
        for name, roles in credit.get('people', []):
            for role in roles.split(','):
                for xml_field, pattern in ROLE_PATTERNS.items():
                    if pattern.search(role.strip().lower()):
                        add(xml_field, name)
                        break

        for xml_field in ('Characters', 'Teams', 'Locations', 'StoryArc'):
            for name in credit.get(xml_field.lower(), []):
                add(xml_field, name)

    return {field: ', '.join(names) for field, names in result_map.items()}


def _build_fields(volume: VolumeData,
    issues: Sequence[IssueData],
    credits: Sequence[Union[IssueCredits,
    None]]) -> Dict[str,
     str]:
    issue = issues[0]
    fields = {
        'Series': volume.title,
        'Number': issue.issue_number,
        'Volume': volume.volume_number,
        'Publisher': volume.publisher,
        'Format': volume.special_version.value,
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
        fields['Notes'] = f'Tagged by Kapowarr using info from Comic Vine. [Issue ID {issue.comicvine_id}]'
    else:
        fields['Web'] = volume.site_url
        fields['Notes'] = 'Tagged by Kapowarr using info from Comic Vine.'

    fields.update(_map_credits(credits))
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


# Archive File Modifiers


def can_embed(filepath: Union[str, Path]) -> bool:
    path = Path(filepath)
    if path.suffix.lower() not in FILE_EXTS or not path.is_file():
        return False
    archive_type = get_archive_mimetype(str(path))
    return archive_type == 'zip' or (
        archive_type == 'rar' and System.runs_64bit)


def has_comicinfo(filepath: Union[str, Path]) -> bool:
    path = str(filepath)
    if get_archive_mimetype(path) == 'zip':
        with ZipFile(path) as zf:
            return any(n.lower() == FILENAME.lower() for n in zf.namelist())
    else:
        result = run_rar(['lb', path])
        if result.returncode == 0:
            return any(
                n.strip().lower() == FILENAME.lower()
                for n in result.stdout.splitlines())
        return False


def _zip_with_xml(source: Path, target: Path, xml_bytes: bytes) -> None:
    if not has_comicinfo(source):
        copy2(source, target)
        with ZipFile(target, 'a') as zf:
            zf.writestr(FILENAME, xml_bytes, ZIP_DEFLATED)
        return

    with ZipFile(source) as zin, ZipFile(target, 'w') as zout:
        zout.comment = zin.comment
        for item in zin.infolist():
            if item.filename.lower() != FILENAME.lower():
                zout.writestr(item, zin.read(item))
        zout.writestr(FILENAME, xml_bytes, ZIP_DEFLATED)


def _rar_with_xml(source: Path, target: Path, xml_bytes: bytes) -> None:
    copy2(source, target)

    result = run_rar(['lb', str(target)])
    if result.returncode == 0:
        for name in [n.strip() for n in result.stdout.splitlines()
                     if n.strip().lower() == FILENAME.lower()]:
            run_rar(['d', '-inul', str(target), name])

    xml_file = target.parent / FILENAME
    xml_file.write_bytes(xml_bytes)

    res = run_rar(['a', '-ep', '-inul', str(target), str(xml_file)])
    if res.returncode != 0:
        raise RuntimeError(f'Failed to add to rar: Error {res.returncode}')


# Main Entry Point


def tag_archive(filepath: Union[str, Path], volume: VolumeData,
                issues: Sequence[IssueData],
                credits: Sequence[Union[IssueCredits, None]] = ()) -> None:
    path = Path(filepath)

    fields = _build_fields(volume, issues, credits)
    xml_bytes = _build_xml(fields)

    # Make edits on temporary file
    with TemporaryDirectory(dir=path.parent, prefix='.kapowarr-') as folder:
        target = Path(folder) / path.name

        if get_archive_mimetype(str(path)) == 'zip':
            _zip_with_xml(path, target, xml_bytes)
        else:
            _rar_with_xml(path, target, xml_bytes)

        copystat(path, target)
        if get_os_type() in (OSType.LINUX, OSType.MACOS):
            st = stat(path)
            try:
                chown(target, st.st_uid, st.st_gid)
            except OSError:
                pass

        replace(target, path)
