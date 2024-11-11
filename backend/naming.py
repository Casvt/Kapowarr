# -*- coding: utf-8 -*-

"""
The (re)naming of folders and media
"""

from __future__ import annotations

from os import listdir
from os.path import basename, isdir, isfile, join, splitext
from re import compile, escape, match
from string import Formatter
from sys import platform
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Tuple, Union

from backend.custom_exceptions import InvalidSettingValue
from backend.db import get_db
from backend.definitions import (SpecialVersion, full_sv_mapping,
                                 short_sv_mapping)
from backend.file_extraction import cover_regex, image_extensions
from backend.files import (delete_empty_child_folders,
                           delete_empty_parent_folders,
                           propose_basefolder_change, rename_file)
from backend.helpers import filtered_iter, first_of_column
from backend.logging import LOGGER
from backend.root_folders import RootFolders
from backend.server import WebSocket
from backend.settings import Settings
from backend.volumes import Issue, Volume

if TYPE_CHECKING:
    from backend.volumes import VolumeData

formatting_keys = (
    'series_name',
    'clean_series_name',
    'volume_number',
    'comicvine_id',
    'year',
    'publisher'
)

formatting_keys_sv = formatting_keys + (
    'special_version',
)

issue_formatting_keys = formatting_keys + (
    'issue_comicvine_id',
    'issue_number',
    'issue_title',
    'issue_release_date',
    'issue_release_year'
)

filename_cleaner = compile(
    r'(<|>|(?<!^\w):|\"|\||\?|\*|\x00|(?:\s|\.)+(?=$|\\|/))')
remove_year_in_image_regex = compile(r'(?:19|20)\d{2}')
page_regex = compile(
    r'^(\d+(?:[a-f]|_\d+)?)$|\b(?i:page|pg)[\s\.\-_]?(\d+(?:[a-f]|_\d+)?)|n?\d+[_\-p](\d+(?:[a-f]|_\d+)?)'
)
page_regex_2 = compile(r'(\d+)')

# =====================
# Name generation
# =====================


def make_filename_safe(unsafe_filename: str) -> str:
    """Make a filename safe to use in a filesystem. It removes illegal characters.

    Args:
        unsafe_filename (str): The filename to be made safe.

    Returns:
        str: The filename, now with characters removed/replaced
        so that it's filesystem-safe.
    """
    safe_filename = filename_cleaner.sub('', unsafe_filename)
    return safe_filename


def _get_formatting_data(
    volume_id: int,
    issue_id: Union[int, None] = None,
    _volume_data: Union[VolumeData, None] = None,
    _volume_number: Union[int, Tuple[int, int], None] = None
) -> Dict[str, Any]:
    """Get the values of the formatting keys for a volume or issue.

    Args:
        volume_id (int): The id of the volume.

        issue_id (Union[int, None], optional): The id of the issue.
            Defaults to None.

        _volume_data (Union[VolumeData, None], optional): Instead of fetching
        data based on the volume id, work with the data given in this variable.
            Defaults to None.

        _volume_number (Union[int, Tuple[int, int], None], optional):
        Override the volume number.
            Defaults to None.

    Raises:
        VolumeNotFound: The volume id doesn't map to any volume in the library.
        IssueNotFound: The issue id doesn't map to any issue in the volume.

    Returns:
        Dict[str, Any]: The formatting keys and their values for the item.
    """
    if _volume_data is not None:
        volume_data = _volume_data
    else:
        volume_data = Volume(volume_id, check_existence=True).get_keys((
            'comicvine_id',
            'title', 'year', 'volume_number',
            'publisher', 'special_version'
        ))

    if _volume_number:
        _vn = _volume_number
    else:
        _vn = volume_data.volume_number

    if not isinstance(_vn, tuple):
        _vn = (_vn,)

    settings = Settings()
    long_special_version = settings['long_special_version']
    volume_padding = settings['volume_padding']
    issue_padding = settings['issue_padding']

    # Build formatted data
    if volume_data.title.startswith('The '):
        clean_title = volume_data.title[len('The '):] + ', The'
    elif volume_data.title.startswith('A '):
        clean_title = volume_data.title[len('A '):] + ', A'
    else:
        clean_title = volume_data.title or 'Unknown'

    volume_number = ' - '.join((
        str(n).zfill(volume_padding)
        for n in _vn
    ))

    if long_special_version:
        sv_mapping = full_sv_mapping
    else:
        sv_mapping = short_sv_mapping

    formatting_data = {
        'series_name': ((volume_data.title or 'Unknown')
            .replace('/', '')
            .replace(r'\\', '')
        ),
        'clean_series_name': (clean_title
            .replace('/', '')
            .replace(r'\\', '')
        ),
        'volume_number': volume_number,
        'comicvine_id': volume_data.comicvine_id or 'Unknown',
        'year': volume_data.year or 'Unknown',
        'publisher': volume_data.publisher or 'Unknown',
        'special_version': sv_mapping.get(volume_data.special_version)
    }

    if issue_id:
        # Add issue data if issue is found
        issue_data: Dict[str, Any] = Issue(issue_id, check_existence=True).get_keys(
            ('comicvine_id', 'issue_number', 'title', 'date'))

        formatting_data.update({
            'issue_comicvine_id': issue_data.get('comicvine_id') or 'Unknown',
            'issue_number': (
                str(issue_data.get('issue_number'))
                .zfill(issue_padding)
                or 'Unknown'
            ),
            'issue_title': ((issue_data.get('title') or 'Unknown')
                .replace('/', '')
                .replace(r'\\', '')
            ),
            'issue_release_date': issue_data.get('date') or 'Unknown',
            'issue_release_year': ((issue_data.get('date') or '')
                    .split('-')[0]
                or 'Unknown'
            )
        })

    return formatting_data


def generate_volume_folder_name(
    volume_id: int,
    _volume_data: Union[VolumeData, None] = None
) -> str:
    """Generate a volume folder name based on the format string

    Args:
        volume_id (int): The id of the volume for which to generate the string

        _volume_data (Union[VolumeData, None], optional): Instead of fetching
        data based on the volume id, work with the data given in this variable.
            Defaults to None.

    Returns:
        str: The volume folder name.
    """
    formatting_data = _get_formatting_data(volume_id, None, _volume_data)
    format: str = Settings()['volume_folder_naming']

    name = format.format(**formatting_data)
    save_name = make_filename_safe(name)
    return save_name


def generate_sv_name(
    volume_id: int,
    _volume_number: Union[int, Tuple[int, int], None] = None
) -> str:
    """Generate a special version name based on the format string

    Args:
        volume_id (int): The id of the volume for which to generate the string.

        _volume_number (Union[int, Tuple[int, int], None], optional):
        Override the volume number.
            Defaults to None.

    Returns:
        str: The name for special versions
    """
    formatting_data = _get_formatting_data(
        volume_id,
        _volume_number=_volume_number
    )
    format: str = Settings()['file_naming_special_version']

    name = format.format(**formatting_data)
    save_name = make_filename_safe(name)
    return save_name


def generate_empty_name(
    volume_id: int,
    _volume_number: Union[int, Tuple[int, int], None] = None
) -> str:
    """Generate a name without issue number or sv marking

    Args:
        volume_id (int): The id of the volume for which to generate the string.

        _volume_number (Union[int, Tuple[int, int], None], optional):
            Override the volume number.
                Defaults to None.

    Returns:
        str: The empty name
    """
    save_sv_name = generate_sv_name(volume_id, _volume_number)
    sv_l = save_sv_name.split(' ')
    sv_l.reverse()
    sv_l.remove('None')
    sv_l.reverse()
    save_name = ' '.join(sv_l).strip()
    return save_name


def generate_issue_range_name(
    volume_id: int,
    calculated_issue_number_start: float,
    calculated_issue_number_end: float
) -> str:
    """Generate an issue range name based on the format string

    Args:
        volume_id (int): The id of the volume of the issues

        calculated_issue_number_start (float): The start of the issue range.
            Output of `files.process_issue_number()`.

        calculated_issue_number_end (float): The end of the issue range.
            Output of `files.process_issue_number()`.

    Returns:
        str: The issue range name
    """
    issue = Issue.from_volume_and_calc_number(
        volume_id,
        calculated_issue_number_start
    )
    formatting_data = _get_formatting_data(volume_id, issue.id)
    settings = Settings()

    if formatting_data['issue_title'] == 'Unknown':
        format: str = settings['file_naming_empty']
    else:
        format: str = settings['file_naming']

    # Override issue number to range
    issue_number_start = issue['issue_number']
    issue_number_end = Issue.from_volume_and_calc_number(
        volume_id,
        calculated_issue_number_end
    )['issue_number']

    formatting_data['issue_number'] = (
        str(issue_number_start)
        .zfill(settings['issue_padding'])
        + ' - ' +
        str(issue_number_end)
        .zfill(settings['issue_padding'])
    )

    name = format.format(**formatting_data)
    save_name = make_filename_safe(name)
    return save_name


def generate_issue_name(
    volume_id: int,
    calculated_issue_number: float
) -> str:
    """Generate a issue name based on the format string

    Args:
        volume_id (int): The id of the volume of the issue

        calculated_issue_number (float): The issue number.
            Output of `files.process_issue_number()`.

    Returns:
        str: The issue name
    """
    issue = Issue.from_volume_and_calc_number(
        volume_id,
        calculated_issue_number
    )

    formatting_data = _get_formatting_data(volume_id, issue.id)
    settings = Settings()

    if formatting_data['issue_title'] == 'Unknown':
        format: str = settings['file_naming_empty']
    else:
        format: str = settings['file_naming']

    name = format.format(**formatting_data)
    save_name = make_filename_safe(name)
    return save_name

# =====================
# Checking formats
# =====================


def check_format(format: str, type: str) -> None:
    """Check if a format string is valid

    Args:
        format (str): The format string to check
        type (str): What type of format string it is
            Options: 'file_naming', 'file_naming_special_version',
            'file_naming_empty', 'folder_naming'.

    Raises:
        InvalidSettingValue: Something in the string is invalid
    """
    if platform.startswith('win32'):
        disallowed_sep = '/'
    else:
        disallowed_sep = '\\'

    if disallowed_sep in format:
        raise InvalidSettingValue(type, format)

    keys = [fn for _, fn, _, _ in Formatter().parse(format) if fn is not None]

    if type == 'folder_naming':
        naming_keys = formatting_keys
    elif type == 'file_naming_special_version':
        naming_keys = formatting_keys_sv
    else:
        naming_keys = issue_formatting_keys

    for format_key in keys:
        if format_key not in naming_keys:
            raise InvalidSettingValue(type, format)

    return

# =====================
# Renaming
# =====================


def same_name_indexing(
    suggested_name: str,
    current_name: str,
    folder: str,
    planned_names: List[Dict[str, str]]
) -> str:
    """Add a number after a filename if the filename already exists.

    Args:
        suggested_name (str): The currently suggested filename
        current_name (str): The current name of the file
        folder (str): The folder that the file is in
        planned_names (List[Dict[str, str]]): The already planned names of
        other files.

    Returns:
        str: The suggested name, now with number at the end if needed
    """
    same_names = tuple(
        filter(
            lambda r: match(escape(suggested_name) + r'( \(\d+\))?$', r),
            [splitext(basename(r['after']))[0] for r in planned_names]
        )
    )
    if isdir(folder):
        # Add number to filename if an other file has the same name
        basename_file = splitext(basename(current_name))[0]
        same_names += tuple(
            filter(
                lambda f: (
                    not f == basename_file
                    and match(
                        escape(suggested_name) + r'(?: \(\d+\))?$',
                        f
                    )
                ),
                [splitext(f)[0] for f in listdir(folder) if isfile(f)]
            )
        )

    if same_names:
        i = 0
        while True:
            if not i and suggested_name not in same_names:
                break
            if i and not f"{suggested_name} ({i})" in same_names:
                suggested_name += f" ({i})"
                break
            i += 1

    return suggested_name


def preview_mass_rename(
    volume_id: int,
    issue_id: Union[int, None] = None,
    filepath_filter: Union[List[str], None] = None
) -> Tuple[List[Dict[str, str]], Union[str, None]]:
    """Preview what naming.mass_rename() will do.

    Args:
        volume_id (int): The id of the volume for which to check the renaming.

        issue_id (Union[int, None], optional): The id of the issue for which to
        check the renaming.
            Defaults to None.

        filepath_filter (Union[List[str], None], optional): Only process files
        that are in the list.
            Defaults to None.

    Returns:
        Tuple[List[Dict[str, str]], Union[str, None]]: The renaming proposals,
        and the new volume folder if it is not the same as the current folder.
        Otherwise, it's `None`.
    """
    result = []
    volume = Volume(volume_id)
    cursor = get_db()
    # Fetch all files linked to the volume or issue
    new_vf = None
    if not issue_id:
        file_infos: Iterable[str] = sorted((
            f["filepath"] for f in volume.get_files()
        ))
        if not volume['custom_folder']:
            root_folder = RootFolders()[volume['root_folder']]
            folder = join(root_folder, generate_volume_folder_name(volume_id))
            if folder != volume['folder']:
                new_vf = folder
        else:
            folder = volume['folder']
    else:
        file_infos: Iterable[str] = [
            f["filepath"]
            for f in volume.get_files(issue_id)
        ]
        if not file_infos:
            return result, new_vf
        folder = volume['folder']

    if filepath_filter is not None:
        # We're checking a lot if strings are in this list,
        # so making it a set will increase performance (due to hashing).
        hashed_files = set(filepath_filter)

        file_infos = filter(
            lambda f: f in hashed_files,
            file_infos
        )
    else:
        filepath_filter = []

    special_version = volume['special_version']
    name_volume_as_issue = Settings()['volume_as_empty']

    for file in file_infos:
        if not isfile(file):
            continue
        LOGGER.debug(f'Renaming: original filename: {file}')

        # Find the issues that the file covers
        issues = first_of_column(cursor.execute("""
            SELECT
                i.calculated_issue_number
            FROM issues i
            INNER JOIN issues_files if
            INNER JOIN files f
            ON
                i.id = if.issue_id
                AND if.file_id = f.id
            WHERE f.filepath = ?
            ORDER BY calculated_issue_number;
            """,
            (file,)
        ))
        if special_version in (
            SpecialVersion.TPB,
            SpecialVersion.ONE_SHOT,
            SpecialVersion.HARD_COVER
        ):
            suggested_name = generate_sv_name(volume_id)

        elif (special_version == SpecialVersion.VOLUME_AS_ISSUE
        and not name_volume_as_issue):
            if len(issues) > 1:
                suggested_name = generate_empty_name(
                    volume_id,
                    (int(issues[0]), int(issues[-1]))
                )
            else:
                suggested_name = generate_empty_name(
                    volume_id,
                    int(issues[0])
                )

        elif (special_version.value or SpecialVersion.VOLUME_AS_ISSUE) != SpecialVersion.VOLUME_AS_ISSUE:
            # Covers, etc.
            suggested_name = generate_empty_name(volume_id)

        elif len(issues) > 1:
            # File covers multiple issues
            suggested_name = generate_issue_range_name(
                volume_id,
                issues[0],
                issues[-1]
            )

        else:
            # File covers one issue
            suggested_name = generate_issue_name(volume_id, issues[0])

        # If file is image, it's probably a page instead of a whole issue/tpb.
        # So put it in it's own folder together with the other images.
        if file.endswith(image_extensions):
            filename: str = splitext(basename(file))[0]
            page_number = None
            cover_result = cover_regex.search(filename)
            if cover_result:
                cover_number = cover_result.group(1)
                if cover_number:
                    page_number = f'Cover {cover_number}'
                else:
                    page_number = 'Cover'
            else:
                page_result = page_regex.search(
                    remove_year_in_image_regex.sub('', filename)
                )
                if page_result:
                    page_number = next(
                        r
                        for r in page_result.groups()
                        if r is not None
                    )
                else:
                    page_result = None
                    r = page_regex_2.finditer(basename(file))
                    for page_result in r:
                        pass
                    if page_result:
                        page_number = page_result.group(1)
            suggested_name = join(suggested_name, page_number or '1')

        # Add number to filename if other file has the same name
        suggested_name = same_name_indexing(
            suggested_name,
            file,
            folder,
            result
        )

        suggested_name = join(
            folder,
            suggested_name + splitext(file)[1]
        )

        LOGGER.debug(f'Renaming: suggested filename: {suggested_name}')
        if file != suggested_name:
            LOGGER.debug(f'Renaming: added rename')
            result.append({
                'before': file,
                'after': suggested_name
            })

    if folder != volume['folder']:
        # New volume folder so rename general files too
        new_general_files = propose_basefolder_change(
            filtered_iter(
                (f['filepath'] for f in volume.get_general_files()),
                filepath_filter
            ),
            volume['folder'],
            folder
        )
        for old, new in new_general_files.items():
            LOGGER.debug(f'Renaming: original filename: {old}')
            LOGGER.debug(f'Renaming: suggested filename: {new}')
            LOGGER.debug(f'Renaming: added rename')
            result.append({
                'before': old,
                'after': new
            })

    return result, new_vf


def mass_rename(
    volume_id: int,
    issue_id: Union[int, None] = None,
    filepath_filter: Union[List[str], None] = None,
    update_websocket: bool = False
) -> List[str]:
    """Carry out proposal of `naming.preview_mass_rename()`.

    Args:
        volume_id (int): The id of the volume for which to rename.

        issue_id (Union[int, None], optional): The id of the issue for which
        to rename.
            Defaults to None.

        filepath_filter (Union[List[str], None], optional): Only rename files
        that are in the list.
            Defaults to None.

        update_websocket (bool, optional): Send task progress updates over
        the websocket.
            Defaults to False.

    Returns:
        List[str]: The new files.
    """
    cursor = get_db()
    renames, new_folder = preview_mass_rename(
        volume_id, issue_id,
        filepath_filter
    )

    volume = Volume(volume_id)
    root_folder = RootFolders()[volume['root_folder']]

    if new_folder:
        volume['folder'] = new_folder

    if update_websocket:
        ws = WebSocket()
        total_renames = len(renames)
        for idx, r in enumerate(renames):
            ws.update_task_status(
                message=f'Renaming file {idx+1}/{total_renames}'
            )
            rename_file(r['before'], r['after'])

    else:
        for idx, r in enumerate(renames):
            rename_file(r['before'], r['after'])

    cursor.executemany(
        "UPDATE files SET filepath = ? WHERE filepath = ?;",
        ((r['after'], r['before']) for r in renames)
    )

    if renames:
        delete_empty_child_folders(volume['folder'])
        delete_empty_parent_folders(volume['folder'], root_folder)

    LOGGER.info(
        f'Renamed volume {volume_id} {f"issue {issue_id}" if issue_id else ""}'
    )
    return [r['after'] for r in renames]
