# -*- coding: utf-8 -*-

from datetime import datetime
from json import JSONDecodeError, dumps, load
from os import replace, stat
from os.path import basename, dirname, isdir, isfile, join, splitext
from re import sub
from shutil import chown, copystat
from tempfile import TemporaryDirectory
from typing import Dict, List, Union, cast
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from bs4 import BeautifulSoup

from backend.base.definitions import (SV_TO_SHORT_TERM,
                                      ExtendedIssueFileMetadata, IssueData,
                                      IssueFileMetadata, OSType, VolumeData,
                                      VolumeFileMetadata)
from backend.base.files import copy, create_folder
from backend.base.helpers import get_os_type, run_rar
from backend.implementations.comicvine import clean_description
from backend.implementations.file_processing import mass_process_files
from backend.internals.db_models import FilesDB

_FIELD_MAPPING = {
    "Series": ("series", str),
    "Volume": ("volume_number", str),
    "Format": ("format", str),
    "Publisher": ("publisher", str),
    "Number": ("issue_number", str),
    "Title": ("issue_title", str),
    "Summary": ("issue_description", str),
    "Notes": ("notes", str),
    "Year": ("issue_year", str),
    "Month": ("issue_month", str),
    "Day": ("issue_day", str),
    "Web": ("issue_site_url", str),
    "CoverArtist": ("cover_artist", list),
    "Writer": ("writer", list),
    "Penciller": ("penciller", list),
    "Inker": ("inker", list),
    "Colorist": ("colorist", list),
    "Letterer": ("letterer", list),
    "Editor": ("editor", list),
    "Characters": ("characters", list),
    "Teams": ("teams", list),
    "Locations": ("locations", list),
    "StoryArc": ("storyarc", list)
}


# region Get Content
def get_volume_metadata_contents(
    filepath: str
) -> Union[VolumeFileMetadata, None]:
    """Get the metadata from a volume's folder.

    Args:
        filepath (str): The path to a volume folder or its metadata file.

    Returns:
        Union[VolumeFileMetadata, None]: The metadata, or `None` if the file is
            missing or invalid.
    """
    if isdir(filepath):
        filepath = join(filepath, "series.json")
    elif basename(filepath).lower() != "series.json":
        return None

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            contents = load(f)
    except (OSError, UnicodeDecodeError, JSONDecodeError):
        return None

    if not isinstance(contents, dict) and "metadata" in contents:
        return None

    return cast(VolumeFileMetadata, contents["metadata"])


def get_issue_metadata_contents(
    filepath: str
) -> Union[IssueFileMetadata, None]:
    """Get the metadata of an issue file.

    Args:
        filepath (str): The filepath to an issue file (that the metadata file
            is in), metadata file directly or folder that it is in.

    Returns:
        Union[IssueFileMetadata, None]: The metadata found in the file, or `None`
            if no metadata file could be found.
    """
    if isdir(filepath):
        if isfile(join(filepath, "ComicInfo.xml")):
            filepath = join(filepath, "ComicInfo.xml")
        else:
            return None

    if basename(filepath).lower() == "comicinfo.xml":
        with open(filepath, "r") as f:
            contents = f.read()

    elif splitext(filepath)[1].lower() in (".cbz", ".zip"):
        try:
            with ZipFile(filepath, "r") as zip:
                matching_files = [
                    file
                    for file in zip.namelist()
                    if file.lower() == "comicinfo.xml"
                ]
                if not matching_files:
                    # File doesn't exist in zip
                    return None
                contents = zip.read(matching_files[0])

        except BadZipFile:
            return None

    elif splitext(filepath)[1].lower() in (".cbr", ".rar"):
        namelist = run_rar([
            "lb", # Get list of files
            filepath
        ])
        if namelist.returncode != 0:
            # Failed to get contents
            return None

        matching_files = [
            file
            for file in namelist.stdout.splitlines()
            if file.lower() == "comicinfo.xml"
        ]
        if not matching_files:
            # File doesn't exist in rar
            return None

        contents = run_rar([
            "p", # Get file contents
            filepath,
            matching_files[0]
        ]).stdout

    else:
        # File format not supported
        return None

    try:
        xml = ElementTree.XML(contents)
    except ElementTree.ParseError:
        # Invalid content
        return None

    def extract_list(key: str) -> Union[List[str], None]:
        raw_value = xml.findtext(key)
        if raw_value is None:
            # Not present
            return None
        if not raw_value:
            # Empty value
            return []
        # Filled value
        return raw_value.split(", ")

    result = cast(IssueFileMetadata, {
        data_key: (
            xml.findtext(file_key)
            if type_key is str else
            extract_list(file_key)
        )
        for file_key, (data_key, type_key) in _FIELD_MAPPING.items()
    })

    return result


# region Build Content
def _clean_summary(description: str) -> str:
    """Clean a volume/issue description and turn it from html into text.

    Args:
        description (str): The full issue description in HTML.

    Returns:
        str: The cleaned description.
    """
    soup = BeautifulSoup(clean_description(description), 'html.parser')
    text = soup.get_text(" ").replace('\xa0', ' ')
    text = sub(r'\n+', ' ', text)
    return " ".join(text.split())


def _build_series_json(
    volume_data: VolumeData,
    issue_data: List[IssueData]
) -> str:
    """Build the metadata dictionary for a volume.

    Args:
        volume_data (VolumeData): The data of the volume.
        issue_data (List[IssueData]): The data of the issues in the volume.

    Returns:
        str: The resulting series json.
    """
    series_json = {"metadata": {
        "type": "comicSeries",
        "publisher": volume_data.publisher,
        "imprint": None,
        "name": volume_data.title,
        "comicid": volume_data.comicvine_id,
        "year": volume_data.year,
        "description_text": _clean_summary(volume_data.description),
        "description_formatted": volume_data.description,
        "volume": volume_data.volume_number,
        "booktype": SV_TO_SHORT_TERM.get(volume_data.special_version, ""),
        "age_rating": None,
        "collects": None,
        "comic_image": None,
        "total_issues": len(issue_data),
        "publication_run": "",
        "status": ""
    }}

    return dumps(series_json, indent=4, ensure_ascii=False)


def _build_comicinfo(
    volume_data: VolumeData,
    issue_datas: List[IssueData],
    extended_issue_datas: Dict[int, ExtendedIssueFileMetadata]
) -> str:
    """Build the ComicInfo xml data structure.

    Args:
        volume_data (VolumeData): The data of the volume that the file is for.
        issue_datas (List[IssueData]): The data of the issues that the file
            covers.
        extended_issue_datas (Dict[int, ExtendedIssueFileMetadata]): The map
            from the issue IDs to their extended metadata.

    Returns:
        str: The resulting ComicInfo xml.
    """
    if len(issue_datas) == 1:
        number = issue_datas[0].issue_number
    else:
        number = f"{issue_datas[0].issue_number}-{issue_datas[-1].issue_number}"

    if extended_issue_datas:
        extended_fields = {
            file_key: []
            for file_key, (data_key, _) in _FIELD_MAPPING.items()
            if data_key in ExtendedIssueFileMetadata.__annotations__
        }
        for issue in issue_datas:
            if issue.comicvine_id not in extended_issue_datas:
                continue

            extended_data = extended_issue_datas[issue.comicvine_id]
            for extended_key, extended_list in extended_fields.items():
                for entry in extended_data[_FIELD_MAPPING[extended_key][0]]:
                    if entry not in extended_list:
                        extended_list.append(entry)

    else:
        extended_fields = {}

    fields: Dict[str, str] = {
        "Series": volume_data.title,
        "Volume": str(volume_data.volume_number),
        "Publisher": str(volume_data.publisher),
        "Format": SV_TO_SHORT_TERM.get(volume_data.special_version, ""),
        "Web": issue_datas[0].site_url or volume_data.site_url,
        "Number": number,
        "Title": "; ".join((i.title for i in issue_datas if i.title)),
        "Summary": "\n\n".join((
            _clean_summary(i.description)
            for i in issue_datas
            if i.description
        )),
        "Notes": "Exported by Kapowarr. [CVID 4000-%s]" % (
            ',4000-'.join((str(i.comicvine_id) for i in issue_datas))
        )
    }

    try:
        date = datetime.strptime(issue_datas[0].date or '', '%Y-%m-%d')
        fields.update({
            'Year': str(date.year),
            'Month': str(date.month),
            'Day': str(date.day)
        })
    except ValueError:
        fields['Year'] = str(volume_data.year or "")

    fields.update({
        file_key: ", ".join(value_set)
        for file_key, value_set in extended_fields.items()
    })

    xml_root = ElementTree.Element("ComicInfo")
    for key in _FIELD_MAPPING:
        if key not in fields:
            continue
        ElementTree.SubElement(xml_root, key).text = fields[key]

    if hasattr(ElementTree, 'indent'): # >= 3.9
        ElementTree.indent(xml_root, space='  ')

    return ElementTree.tostring(
        xml_root,
        encoding='utf-8',
        xml_declaration=True
    ).decode("utf-8")


# region Export Content
def export_volume_metadata_file(
    volume_data: VolumeData,
    issue_data: List[IssueData]
) -> None:
    """Export a volume's metadata to a file in its volume folder.

    Args:
        volume_data (VolumeData): The data of the volume to export.
        issue_data (List[IssueData]): The data of the issues in the volume.
    """
    create_folder(volume_data.folder)
    filepath = join(volume_data.folder, "series.json")
    with open(filepath, "wt") as f:
        f.write(_build_series_json(volume_data, issue_data))
    return


def export_volume_cover_file(cover: bytes, volume_folder: str) -> None:
    """Export a volume cover image to an image file in its volume folder.

    Args:
        cover (bytes): The image data of the volume cover.
        volume_folder (str): The folder to export the image to.
    """
    create_folder(volume_folder)
    with open(join(volume_folder, "cover.jpg"), "wb") as f:
        f.write(cover)
    return


def _export_to_zip(xml: str, filepath: str) -> None:
    """Put the metadata into a ComicInfo.xml file inside the zip. Handles both
    when the file doesn't contain one yet and when it does.

    Args:
        xml (str): The ComicInfo xml.
        filepath (str): The path to the zip file.
    """
    with ZipFile(filepath, "r") as source_zip:
        has_metadata_file = any(
            existing_file.lower() == "comicinfo.xml"
            for existing_file in source_zip.namelist()
        )

    if not has_metadata_file:
        with ZipFile(filepath, "a") as zip:
            zip.writestr("ComicInfo.xml", xml)

    else:
        with TemporaryDirectory(
            dir=dirname(filepath), prefix='.kapowarr-'
        ) as temp_dir:
            target_filepath = join(temp_dir, basename(filepath))
            with ZipFile(filepath, "r") as source_zip, \
                ZipFile(target_filepath, "w") as target_zip:

                target_zip.comment = source_zip.comment
                for item in source_zip.infolist():
                    if item.filename.lower() != "comicinfo.xml":
                        target_zip.writestr(item, data=source_zip.read(item))
                target_zip.writestr("ComicInfo.xml", xml)

            copystat(filepath, target_filepath)
            if get_os_type() in (OSType.LINUX, OSType.MACOS):
                st = stat(filepath)
                try:
                    chown(target_filepath, st.st_uid, st.st_gid)
                except OSError:
                    pass

            replace(target_filepath, filepath)
    return


def _export_to_rar(xml: str, filepath: str) -> None:
    """Put the metadata into a ComicInfo.xml file inside the rar. Handles both
    when the file doesn't contain one yet and when it does.

    Args:
        xml (str): The ComicInfo xml.
        filepath (str): The path to the rar file.
    """
    with TemporaryDirectory(
        dir=dirname(filepath), prefix=".kapowarr-"
    ) as temp_dir:
        target_filepath = join(temp_dir, basename(filepath))
        copy(filepath, target_filepath)

        namelist = run_rar([
            "lb", # Get list of files
            target_filepath
        ])
        if namelist.returncode != 0:
            # Failed to get contents
            return None

        for file in namelist.stdout.splitlines():
            if file.lower() == "comicinfo.xml":
                run_rar([
                    "d", # Delete file from rar
                    "-inul",
                    target_filepath,
                    file
                ])

        xml_file = join(temp_dir, "ComicInfo.xml")
        with open(xml_file, "wt") as f:
            f.write(xml)

        result = run_rar([
            "a", # Add file to rar
            "-ep",
            "-inul",
            target_filepath,
            xml_file
        ])
        if result.returncode != 0:
            # Failed to add file
            return None

        copystat(filepath, target_filepath)
        if get_os_type() in (OSType.LINUX, OSType.MACOS):
            st = stat(filepath)
            try:
                chown(target_filepath, st.st_uid, st.st_gid)
            except OSError:
                pass

        replace(target_filepath, filepath)

    return


def export_issue_metadata(
    filepath: str,
    volume_data: VolumeData,
    issue_datas: List[IssueData],
    extended_issue_datas: Dict[int, ExtendedIssueFileMetadata]
) -> None:
    """Export the metadata to the file of the issue.

    Args:
        filepath (str): The path to the issue file.
        volume_data (VolumeData): The data of the volume that the file is for.
        issue_datas (List[IssueData]): The data of the issues that the file
            covers.
        extended_issue_datas (Dict[int, ExtendedIssueFileMetadata]): The map
            from the issue IDs to their extended metadata.
    """
    xml = _build_comicinfo(volume_data, issue_datas, extended_issue_datas)

    if isdir(filepath):
        if isfile(join(filepath, "ComicInfo.xml")):
            filepath = join(filepath, "ComicInfo.xml")
        else:
            return None

    if basename(filepath).lower() == "comicinfo.xml":
        with open(filepath, "wt") as f:
            f.write(xml)

    elif splitext(filepath)[1].lower() in (".cbz", ".zip"):
        _export_to_zip(xml, filepath)

    elif splitext(filepath)[1].lower() in (".cbr", ".rar"):
        _export_to_rar(xml, filepath)

    else:
        # File format not supported; should already be filtered out
        raise RuntimeError(
            f"File format not supported to get metadata of: {filepath}")

    FilesDB.update_size(filepath)
    mass_process_files(volume_data.id, filepath_filter=[filepath])
    return
