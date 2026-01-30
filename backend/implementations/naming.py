# -*- coding: utf-8 -*-

"""
The (re)naming of folders and media files
"""

from __future__ import annotations

from os.path import abspath, basename, isdir, isfile, join, splitext
from re import compile
from string import Formatter
from typing import Dict, List, Tuple, Type, Union

from backend.base.custom_exceptions import InvalidKeyValue, IssueNotFound
from backend.base.definitions import (SV_TO_FULL_TERM, SV_TO_SHORT_TERM,
                                      BaseNamingKeys, Constants, FileConstants,
                                      IssueData, IssueNamingKeys, OSType,
                                      SpecialVersion, TitlelessIssueNamingKeys,
                                      VolumeData, VolumeNamingKeys)
from backend.base.file_extraction import (cover_regex, extract_filename_data,
                                          extract_issue_number, page_regex,
                                          page_regex_2)
from backend.base.files import (clean_filepath_simple, clean_filepath_smartly,
                                clean_filestring_simple,
                                clean_filestring_smartly,
                                delete_empty_child_folders,
                                delete_empty_parent_folders, list_files,
                                rename_file)
from backend.base.helpers import (extract_year_from_date,
                                  filtered_iter, force_range)
from backend.base.logging import LOGGER
from backend.implementations.file_processing import mass_process_files
from backend.implementations.matching import file_importing_filter, match_title
from backend.implementations.root_folders import RootFolders
from backend.implementations.volumes import Issue, Volume
from backend.internals.db_models import FilesDB
from backend.internals.server import TaskStatusEvent, WebSocket
from backend.internals.settings import Settings, System

remove_year_in_image_regex = compile(r'(?:19|20)\d{2}')
extra_spaces_regex = compile(r'(?<=\s)(\s+)')


# region Cleaning names
def clean_filestring(filestring: str) -> str:
    """Clean a part of a filename (so no path separators) by removing illegal
    characters or replacing them smartly (depending on the settings).

    Args:
        filestring (str): The string to clean.

    Returns:
        str: The cleaned string.
    """
    if Settings().sv.replace_illegal_characters:
        result = clean_filestring_smartly(filestring)
    else:
        result = clean_filestring_simple(filestring)

    return extra_spaces_regex.sub('', result).strip()


def clean_filepath(filepath: str) -> str:
    """Clean a filepath by removing illegal characters or replacing them smartly
    (depending on the settings).

    Args:
        filepath (str): The filepath to clean.

    Returns:
        str: The cleaned filepath.
    """
    if Settings().sv.replace_illegal_characters:
        result = clean_filepath_smartly(filepath)
    else:
        result = clean_filepath_simple(filepath)

    return extra_spaces_regex.sub('', result).strip()


# region Name generation
def _fill_format(
    naming_format: str,
    formatting_data: BaseNamingKeys
) -> str:
    """Fill in a naming format using the given values for the formatting keys.
    Also makes the resulting filename safe for filesystems.

    Args:
        naming_format (str): The format to fill in.
        formatting_data (BaseNamingKeys): The values for the formatting keys.

    Returns:
        str: The resulting filename.
    """
    filled_format = naming_format.format_map({
        k: v if v is not None else 'Unknown'
        for k, v in formatting_data.__dict__.items()
    })
    save_filled_format = clean_filepath(filled_format)
    return save_filled_format


def _get_base_naming_keys(volume_data: VolumeData) -> BaseNamingKeys:
    """Generate the values of the base naming keys for any type of naming.

    Args:
        volume_data (VolumeData): The data of the volume to base the values on.

    Returns:
        BaseNamingKeys: The values of the base naming keys.
    """
    settings = Settings().get_settings()
    volume_padding = settings.volume_padding

    series_name = clean_filestring(volume_data.title)

    for prefix in ('The ', 'A '):
        if series_name.startswith(prefix):
            clean_title = series_name[len(prefix):] + ", " + prefix.strip()
            break
    else:
        clean_title = series_name

    return BaseNamingKeys(
        series_name=series_name,
        clean_series_name=clean_title,
        volume_number=str(volume_data.volume_number).zfill(volume_padding),
        comicvine_id=volume_data.comicvine_id,
        year=volume_data.year,
        publisher=clean_filestring(volume_data.publisher)
    )


def get_volume_naming_keys(volume_data: VolumeData) -> VolumeNamingKeys:
    """Generate the values of the naming keys for a volume.

    Args:
        volume_data (VolumeData): The data of the volume to base the values on.

    Returns:
        VolumeNamingKeys: The values of the naming keys for a volume.
    """
    if Settings().sv.long_special_version:
        sv_mapping = SV_TO_FULL_TERM
    else:
        sv_mapping = SV_TO_SHORT_TERM

    return VolumeNamingKeys(
        **_get_base_naming_keys(volume_data).__dict__,

        special_version=sv_mapping.get(volume_data.special_version)
    )


def get_special_version_naming_keys(
    volume_data: VolumeData,
    is_volume_cover: bool = False
) -> VolumeNamingKeys:
    """Generate the values of the naming keys for a Special Version file, like
    an OS, HC, etc.

    Args:
        volume_data (VolumeData): The data of the volume to base the values on.
        is_volume_cover (bool, optional): Whether the special version key should
            be given a value for covers.
            Defaults to False.

    Returns:
        VolumeNamingKeys: The values of the naming keys for a Special Version file.
    """
    if Settings().sv.long_special_version:
        sv_mapping = SV_TO_FULL_TERM
    else:
        sv_mapping = SV_TO_SHORT_TERM

    if is_volume_cover:
        special_version = SpecialVersion.COVER
    else:
        special_version = volume_data.special_version

    result = get_volume_naming_keys(volume_data)
    result.special_version = sv_mapping.get(special_version)
    return result


def get_issue_naming_keys(
    volume_data: VolumeData,
    issue_data: IssueData
) -> IssueNamingKeys:
    """Generate the values of the naming keys for an issue.

    Args:
        volume_data (VolumeData): The data of the volume to base the values on.
        issue_data (IssueData): The data of the volume to base the values on.

    Returns:
        IssueNamingKeys: The values of the naming keys for an issue.
    """
    issue_padding = Settings().sv.issue_padding

    if issue_data.issue_number:
        issue_number = str(issue_data.issue_number).zfill(issue_padding)
    else:
        issue_number = None

    return IssueNamingKeys(
        **_get_base_naming_keys(volume_data).__dict__,

        issue_comicvine_id=issue_data.comicvine_id,
        issue_number=issue_number,
        issue_release_date=issue_data.date,
        issue_release_year=extract_year_from_date(issue_data.date),
        issue_title=clean_filestring(issue_data.title or '') or None
    )


def generate_volume_folder_name(volume_data: VolumeData) -> str:
    """Generate a volume folder name based on the format string.

    Args:
        volume_data (VolumeData): The data of the volume to generate a name with.

    Returns:
        str: The volume folder name.
    """
    formatting_data = get_volume_naming_keys(volume_data)
    format = Settings().sv.volume_folder_naming

    name = _fill_format(format, formatting_data)
    return name


def generate_volume_folder_path(
    root_folder: str,
    volume_data: VolumeData,
    custom_folder: Union[str, None] = None
) -> str:
    """Generate an absolute path to a volume folder.

    Args:
        root_folder (str): The root folder that the volume is in.
        volume_data (VolumeData): The data of the volume to generate a name with.
        custom_folder (Union[str, None], optional): Instead of generating a
            volume folder, use the given custom path.
            Defaults to None.

    Returns:
        str: The absolute path to the volume folder, allowing custom folders.
    """
    if custom_folder:
        vf = custom_folder
    else:
        vf = generate_volume_folder_name(volume_data)

    return clean_filepath(abspath(join(root_folder, vf)))


def _determine_format(
    volume_data: VolumeData,
    calculated_issue_number: Union[float, Tuple[float, float], None],
    is_volume_cover: bool = False
) -> Tuple[str, BaseNamingKeys]:
    """Determine which naming format should be used and prepare the formatting
    key values for it.

    Args:
        volume_data (VolumeData): The data of the volume the file is for.
        calculated_issue_number (Union[float, Tuple[float, float], None]):
            The issue (or issue range) that the file covers. Give volume number
            here in case of VAI.
        is_volume_cover (bool, optional): Whether the special version key should
            be given a value for volume covers.
            Defaults to False.

    Raises:
        IssueNotFound: No issue found with the given issue number.

    Returns:
        Tuple[str, BaseNamingKeys]: The selected naming format and the
            formatting keys.
    """
    sv = Settings().sv

    if is_volume_cover:
        # Iron-Man Volume 2 Cover
        formatting_data = get_special_version_naming_keys(
            volume_data,
            is_volume_cover=True
        )
        format = sv.file_naming_special_version

    elif volume_data.special_version in (
        SpecialVersion.TPB,
        SpecialVersion.ONE_SHOT,
        SpecialVersion.HARD_COVER,
        SpecialVersion.OMNIBUS
    ):
        # Iron-Man Volume 2 One-Shot
        formatting_data = get_special_version_naming_keys(volume_data)
        format = sv.file_naming_special_version

    elif calculated_issue_number is None:
        raise IssueNotFound(-1)

    elif volume_data.special_version == SpecialVersion.VOLUME_AS_ISSUE:
        # Iron-Man Volume 1 - 3
        issue = Issue.from_volume_and_calc_number(
            volume_data.id, force_range(calculated_issue_number)[0]
        )
        formatting_data = get_issue_naming_keys(volume_data, issue.get_data())
        format = sv.file_naming_vai

    else:
        # Iron-Man Volume 1 Issue 2 - 3
        issue = Issue.from_volume_and_calc_number(
            volume_data.id,
            force_range(calculated_issue_number)[0]
        )
        formatting_data = get_issue_naming_keys(volume_data, issue.get_data())

        if formatting_data.issue_title is None:
            format = sv.file_naming_empty
        else:
            format = sv.file_naming

    return format, formatting_data


def generate_issue_name(
    volume_data: VolumeData,
    calculated_issue_number: Union[float, Tuple[float, float], None],
    is_volume_cover: bool = False
) -> str:
    """Generate an issue filename based on the format string for the issue type.

    Args:
        volume_id (int): The ID of the volume that the file is for.
        calculated_issue_number (Union[float, Tuple[float, float], None]):
            The issue (or issue range) that the file covers. Give volume number
            here in case of VAI.
        is_volume_cover (bool, optional): Whether the name is for a volume cover
            instead of an issue file.
            Defaults to False.

    Raises:
        IssueNotFound: No issue found with the given issue number.

    Returns:
        str: The issue file name.
    """
    sv = Settings().sv

    naming_format, formatting_data = _determine_format(
        volume_data, calculated_issue_number, is_volume_cover
    )

    if (
        isinstance(calculated_issue_number, tuple)
        and isinstance(formatting_data, IssueNamingKeys)
    ):
        # Update issue number value to range
        issue_number_end = Issue.from_volume_and_calc_number(
            volume_data.id,
            calculated_issue_number[1]
        ).get_data().issue_number

        formatting_data.issue_number = (
            str(formatting_data.issue_number)
            .zfill(sv.issue_padding)
            + ' - ' +
            str(issue_number_end)
            .zfill(sv.issue_padding)
        )

    # Fill in variables into format
    resulting_name = _fill_format(naming_format, formatting_data)

    if naming_format != sv.file_naming:
        return resulting_name

    # Format is standard issue naming, so we have to do some extra checks.

    if len(resulting_name) > Constants.MAX_FILENAME_LENGTH:
        # Filename too long, so generate without issue title
        # and see if that fixes it.
        titleless_name = _fill_format(sv.file_naming_empty, formatting_data)
        if len(titleless_name) <= Constants.MAX_FILENAME_LENGTH:
            resulting_name = titleless_name

    elif extract_filename_data(resulting_name)['issue_number'] != calculated_issue_number:
        # When applying the EFD algorithm to the generated filename, we don't
        # get back the same issue number(s) as that we originally made the
        # filename for. This probably means that the title of the issue is
        # messing up the algorithm. E.g. the title of issue 4 is "Book 1",
        # then EFD might think the file is for issue 1 instead of 4. Try a name
        # without the title and see if that fixes it. If so, use it. If not,
        # then give up and just use the original name.
        titleless_name = _fill_format(sv.file_naming_empty, formatting_data)
        efd_check = extract_filename_data(titleless_name)
        if efd_check['issue_number'] == calculated_issue_number:
            resulting_name = titleless_name

    return resulting_name


def generate_image_name(filename: str) -> str:
    """Generate an image filename based on what the current filename suggests
    is the cover or page covered.

    Args:
        filename (str): The current filename of the image file.

    Returns:
        str: The image filename.
    """
    file_body = remove_year_in_image_regex.sub(
        '',
        splitext(basename(filename))[0]
    )

    cover_result = cover_regex.search(file_body)
    if cover_result:
        return f'Cover {cover_result.groups("")[0]}'.strip()

    page_result = page_regex.search(file_body)
    if page_result:
        return next(filter(
            bool,
            page_result.groups()
        ))

    page_result = page_regex_2.findall(file_body)
    if page_result:
        return page_result[-1]

    return '1'


# region Checking formats
NAMING_MAPPING: Dict[str, Type[BaseNamingKeys]] = {
    'volume_folder_naming': VolumeNamingKeys,
    'file_naming': IssueNamingKeys,
    'file_naming_empty': TitlelessIssueNamingKeys,
    'file_naming_special_version': VolumeNamingKeys,
    'file_naming_vai': IssueNamingKeys
}


def check_format(format: str, type: str) -> bool:
    """Check if a format string is valid.

    Args:
        format (str): The format string to check.
        type (str): What type of format string it is, specified by their
            settings key. E.g. 'file_naming'.

    Returns:
        bool: Whether the format is allowed.
    """
    if System.os_type == OSType.WINDOWS:
        disallowed_sep = '/'
    else:
        disallowed_sep = '\\'

    if disallowed_sep in format:
        return False

    keys = [
        fn
        for _, fn, _, _ in Formatter().parse(format)
        if fn is not None
    ]

    naming_keys = NAMING_MAPPING[type]
    for format_key in keys:
        if format_key not in naming_keys.__dataclass_fields__:
            return False

    return True


def check_mock_filename(
    volume_folder_naming: Union[str, None],
    file_naming: Union[str, None],
    file_naming_empty: Union[str, None],
    file_naming_special_version: Union[str, None],
    file_naming_vai: Union[str, None]
) -> None:
    """Check if the supplied naming formats are supported. This is checked by
    creating a filename using the format, and seeing if it matches to a mock
    volume and issue. If it does not match, then the filename must be
    insufficient.

    Args:
        volume_folder_naming (Union[str, None]): The new naming format for the
            volume folder, or `None` if the current one should be used.

        file_naming (Union[str, None]): The new naming format for a standard
            file, or `None` if the current one should be used.

        file_naming_empty (Union[str, None]): The new naming format for an issue
            without title, or `None` if the current one should be used.

        file_naming_special_version (Union[str, None]): The new naming format
            for a Special Version, or `None` if the current one should be used.

        file_naming_vai (Union[str, None]): The new naming format for a VAI,
            or `None` if the current one should be used.

    Raises:
        InvalidKeyValue: One of the formats is insufficient.
    """
    mock_volume = VolumeData(
        id=0,
        comicvine_id=123,
        title="Spider-Man",
        alt_title="Spiderman",
        year=2023,
        publisher="Marvel",
        volume_number=2,
        description="",
        site_url="",
        monitored=True,
        monitor_new_issues=True,
        root_folder=1,
        folder="",
        custom_folder=False,
        special_version=SpecialVersion.ONE_SHOT,
        special_version_locked=False,
        last_cv_fetch=0
    )
    mock_issue = IssueData(
        id=0,
        volume_id=0,
        comicvine_id=456,
        issue_number="1",
        calculated_issue_number=force_range(
            extract_issue_number("1") or 0.0
        )[0],
        title="One Shot",
        date="2023-03-04",
        description="",
        monitored=True,
        files=[]
    )

    naming_mocks = {
        "file_naming_special_version": [
            (
                {"special_version": SpecialVersion.ONE_SHOT},
                {
                    "issue_number": "1",
                    "calculated_issue_number": force_range(
                            extract_issue_number("1") or 0.0
                    )[0],
                    "title": "One Shot"
                }
            ),
            (
                {"special_version": SpecialVersion.TPB},
                {
                    "issue_number": "1",
                    "calculated_issue_number": force_range(
                            extract_issue_number("1") or 0.0
                    )[0],
                    "title": ""
                }
            )
        ],
        "file_naming": [
            (
                {"special_version": SpecialVersion.NORMAL},
                {
                    "issue_number": "3b",
                    "calculated_issue_number": force_range(
                            extract_issue_number("3b") or 0.0
                    )[0],
                    "title": ""
                }
            )
        ],
        "file_naming_vai": [
            (
                {"special_version": SpecialVersion.VOLUME_AS_ISSUE},
                {
                    "issue_number": "8",
                    "calculated_issue_number": force_range(
                            extract_issue_number("8") or 0.0
                    )[0],
                    "title": ""
                }
            )
        ]
    }
    naming_mocks['file_naming_empty'] = naming_mocks['file_naming']

    settings = Settings().get_settings()
    vf_naming = volume_folder_naming or settings.volume_folder_naming
    namings = {
        'file_naming': file_naming or settings.file_naming,
        'file_naming_empty': file_naming_empty or settings.file_naming_empty,
        'file_naming_special_version': file_naming_special_version or settings.file_naming_special_version,
        'file_naming_vai': file_naming_vai or settings.file_naming_vai}

    for key, value in namings.items():
        for volume_entry, issue_entry in naming_mocks[key]:
            mock_volume.__dict__.update(volume_entry)
            mock_issue.__dict__.update(issue_entry)

            volume_formatting_data = get_volume_naming_keys(mock_volume)

            if key == 'file_naming_special_version':
                formatting_data = get_special_version_naming_keys(mock_volume)
            else:
                formatting_data = get_issue_naming_keys(
                    mock_volume, mock_issue
                )

            resulting_folder = _fill_format(vf_naming, volume_formatting_data)
            resulting_name = _fill_format(
                join(resulting_folder, value), formatting_data
            )

            number_to_year = {
                mock_issue.calculated_issue_number: extract_year_from_date(
                    mock_issue.date
                )
            }
            efd = extract_filename_data(resulting_name)
            if not (
                file_importing_filter(
                    efd,
                    mock_volume,
                    [mock_issue],
                    number_to_year
                )
                and match_title(efd['series'], mock_volume.title)
                and (
                    # Special version doesn't need issue matching
                    key == 'file_naming_special_version'
                    or (
                        # Issue number must match
                        key in (
                            'file_naming', 'file_naming_empty',
                            'file_naming_vai'
                        )
                        and efd["issue_number"] == mock_issue.calculated_issue_number
                    )
                    or (
                        # VAI name has issue number labeled as volume number
                        key == 'file_naming_vai'
                        and efd["volume_number"] == mock_issue.calculated_issue_number
                    )
                )
            ):
                raise InvalidKeyValue(key, value)
    return


# region Renaming
def same_name_indexing(
    volume_folder: str,
    planned_renames: Dict[str, str]
) -> Dict[str, str]:
    """Add a number at the end the filenames if the suggested filename already
    exists to avoid files with the same filename.

    Args:
        volume_folder (str): The volume folder that the files will be in.
        planned_renames (Dict[str, str]): The currently planned renames
            (key is before, value is after).

    Returns:
        Dict[str, str]: The planned renames, now updated with numbers if needed.
    """
    if not isdir(volume_folder):
        return planned_renames

    final_names = set(list_files(volume_folder))
    for before, after in planned_renames.items():
        new_after = after
        index = 1
        while before != new_after and new_after in final_names:
            st = splitext(after)
            new_after = st[0] + f' ({index})' + st[1]
            index += 1

        final_names.add(new_after)
        planned_renames[before] = new_after

    return planned_renames


def preview_mass_rename(
    volume_id: int,
    issue_id: Union[int, None] = None,
    filepath_filter: Union[List[str], None] = None
) -> Tuple[Dict[str, str], Union[str, None]]:
    """Determine what the new filenames would be, if they aren't already
    following the format.

    Args:
        volume_id (int): The ID of the volume for which to check the renaming.

        issue_id (Union[int, None], optional): The ID of the issue for which to
            check the renaming.
            Defaults to None.

        filepath_filter (Union[List[str], None], optional): Only process files
            that are in the list.
            Defaults to None.

    Returns:
        Tuple[Dict[str, str], Union[str, None]]: The renaming proposals where
            the key is the "before" and the value is the "after" (including
            files that are already named correctly; their key and value are
            equal), and the new volume folder if it is not the same as the
            current folder. Otherwise, it's `None`.
    """
    volume = Volume(volume_id)
    volume_data = volume.get_data()
    volume_folder = volume_data.folder

    if not issue_id:
        # Rename for volume
        files = volume.get_all_files()

        if not volume_data.custom_folder:
            root_folder = RootFolders()[volume_data.root_folder]
            volume_folder = generate_volume_folder_path(
                root_folder, volume_data
            )

    else:
        # Rename for issue
        files = volume.get_issue(issue_id).get_files()

    if not files and volume_folder == volume_data.folder:
        return {}, None

    files = sorted(filtered_iter(
        (f["filepath"] for f in files),
        set(filepath_filter or [])
    ))
    renames = {}
    for file in files:
        if not isfile(file):
            continue

        LOGGER.debug(f'Renaming: original filename: {file}')

        issues = FilesDB.issues_covered(file)
        if len(issues) > 1:
            # Issue range
            gen_filename_body = generate_issue_name(
                volume_data,
                (issues[0], issues[-1]),
            )

        elif issues:
            # One issue
            gen_filename_body = generate_issue_name(
                volume_data,
                issues[0],
            )

            if basename(file.lower()) in FileConstants.METADATA_FILES:
                gen_filename_body += ' ' + splitext(basename(file))[0]

        elif file.endswith(FileConstants.IMAGE_EXTENSIONS):
            # Volume Cover
            gen_filename_body = generate_issue_name(
                volume_data,
                calculated_issue_number=None,
                is_volume_cover=True
            )

        else:
            # Metadata
            gen_filename_body = splitext(basename(file))[0]

        if issues and file.endswith(FileConstants.IMAGE_EXTENSIONS):
            # Image file is page of issue, so put it in its own
            # folder together with the other images.
            gen_filename_body = join(
                gen_filename_body,
                generate_image_name(file)
            )

        suggested_name = join(
            volume_folder,
            gen_filename_body + splitext(file)[1].lower()
        )

        renames[file] = suggested_name
        if file != suggested_name:
            LOGGER.debug(
                'Renaming: added suggested filename: %s',
                suggested_name
            )
        else:
            LOGGER.debug(
                'Renaming: suggested filename: %s',
                suggested_name
            )

    renames = same_name_indexing(volume_folder, renames)

    if volume_folder != volume_data.folder:
        return renames, volume_folder
    else:
        return renames, None


def mass_rename(
    volume_id: int,
    issue_id: Union[int, None] = None,
    filepath_filter: Union[List[str], None] = None,
    update_websocket: bool = False,
    process_individual_files: bool = True
) -> List[str]:
    """Rename files so that they follow the naming formats.

    Args:
        volume_id (int): The ID of the volume for which to rename.

        issue_id (Union[int, None], optional): The ID of the issue for which
            to rename.
            Defaults to None.

        filepath_filter (Union[List[str], None], optional): Only rename files
            that are in the list.
            Defaults to None.

        update_websocket (bool, optional): Send task progress updates over
            the websocket.
            Defaults to False.

        process_individual_files (bool, optional): Set the ownership,
            permissions and date for all folders and/or files after renaming.
            Defaults to True.

    Returns:
        List[str]: The new filenames of all files, even files that haven't been
            renamed.
    """
    all_namings, new_volume_folder = preview_mass_rename(
        volume_id, issue_id,
        filepath_filter
    )
    renames = {
        before: after
        for before, after in all_namings.items()
        if before != after
    }
    if not renames and not new_volume_folder:
        return list(all_namings.values())

    volume = Volume(volume_id)
    volume_data = volume.get_data()
    root_folder = RootFolders()[volume_data.root_folder]

    if new_volume_folder:
        # No need to run the volume.change_volume_folder method as we do the
        # moving to the new folder below.
        volume.update({'folder': new_volume_folder})

    if update_websocket:
        ws = WebSocket()
        total_renames = len(renames)
        for idx, (before, after) in enumerate(renames.items()):
            ws.emit(TaskStatusEvent(
                f'Renaming file {idx+1}/{total_renames}'
            ))
            rename_file(before, after)

    else:
        for before, after in renames.items():
            rename_file(before, after)

    FilesDB.update_filepaths(renames)

    if renames:
        delete_empty_child_folders(volume_data.folder, skip_hidden_folders=True)
        delete_empty_parent_folders(volume_data.folder, root_folder)

        if process_individual_files:
            mass_process_files(
                volume_id,
                issue_id,
                filepath_filter=list(renames.values())
            )

    LOGGER.info(
        "Renamed volume %d %s",
        volume_id, f"issue {issue_id}" if issue_id else ""
    )
    return list(all_namings.values())
