# -*- coding: utf-8 -*-

"""
Handling folders, files and filenames.
"""

from collections import deque
from os import listdir, makedirs, remove, scandir
from os.path import (abspath, basename, commonpath, dirname, isdir,
                     isfile, join, relpath, samefile, sep, splitext)
from re import compile
from shutil import copy2, copytree, move, rmtree
from typing import Dict, Iterable, List, Sequence, Union
from zipfile import ZIP_DEFLATED, ZipFile

from backend.base.definitions import CharConstants, Constants, FileConstants
from backend.base.helpers import (check_filter, force_prefix,
                                  force_suffix, run_rar)
from backend.base.logging import LOGGER

filepath_cleaner = compile(
    r'(<|>|(?<!^\w):|\"|\||\?|\*|\x00|(?:\s|\.)+(?=$|\\|/))'
)
smart_filepath_cleaner_compact = compile(
    r'(\b[<>:]\b)'
)
smart_filepath_cleaner_spaced = compile(
    r'(\b\s[<>]\s\b|\b:\s\b)'
)
smart_filestring_cleaner_compact = compile(
    r'((?:\b|^)/(?:\b|$))'
)


# region Getting
def folder_path(*folders: str) -> str:
    """Turn filepaths relative to the project folder into absolute paths.

    Returns:
        str: The absolute filepath.
    """
    return join(dirname(dirname(dirname(abspath(__file__)))), *folders)


def list_files(folder: str, ext: Iterable[str] = []) -> List[str]:
    """List all files in a folder recursively with absolute paths. Hidden files
    (files starting with `.`) are ignored.

    Args:
        folder (str): The base folder to search through.

        ext (Iterable[str], optional): File extensions to only include.
            Dot-prefix optional. Keep empty to allow all extensions.
            Defaults to [].

    Returns:
        List[str]: The absolute paths of the files in the folder.
    """
    files: List[str] = []
    to_dos = deque((folder,))
    ext = {force_prefix(e.lower(), '.') for e in ext}

    while to_dos:
        to_do = to_dos.popleft()
        for f in scandir(to_do):
            if f.is_dir():
                to_dos.append(f.path)

            elif (
                f.is_file()
                and not f.name.startswith('.')
                and check_filter(
                    splitext(f.name)[1].lower(),
                    ext
                )
            ):
                files.append(f.path)

    return files


def get_archive_mimetype(filepath: str) -> Union[str, None]:
    """Find the archive type of a file based on its actual mimetype (via magic
    bytes) and return accompanying extension if found.

    Note: This function is not very fast because it has to read the first few
    bytes of the file from disc. So only use when really necessary.

    Args:
        filepath (str): The (archive) file to check for.

    Returns:
        Union[str, None]: The proper lowercase file extension without dot-prefix.
            If the file isn't an archive or isn't recognised as one, return None.
    """
    max_len = max(len(sig) for sig in FileConstants.ARCHIVE_MAGIC_BYTES)

    with open(filepath, 'rb') as f:
        file_start = f.read(max_len)
        for sig, ext in FileConstants.ARCHIVE_MAGIC_BYTES.items():
            if file_start.startswith(sig):
                return ext
        return None


# region Checking
def folder_is_inside_folder(
    base_folder: str,
    folder: str
) -> bool:
    """Check whether `folder` is inside `base_folder`. If folders are equal,
    they are also considered inside.

    ```
    >>> folder_is_inside_folder('/foo', '/foo/bar')
    True
    >>> folder_is_inside_folder('/foo', '/quux/bar')
    False
    >>> folder_is_inside_folder('/foo/', '/foo')
    True
    ```

    Args:
        base_folder (str): The base folder to check against.
        folder (str): The folder that should be inside `base_folder` or equal
            to it.

    Returns:
        bool: Whether `folder` is in `base_folder` or equal to it.
    """
    return (
        force_suffix(abspath(folder))
    ).startswith(
        force_suffix(abspath(base_folder))
    )


def are_folders_colliding(
    check_folder: str,
    existing_folders: Iterable[str],
    folder_to_skip: Union[str, None] = None
) -> bool:
    """Check whether the folder is the parent or child of any folder
    in the iterable.

    ```
    >>> are_folders_colliding('/foo/bar', ['/foo/quux', '/foo/baz'])
    False
    >>> are_folders_colliding('/foo/bar', [])
    False
    >>> are_folders_colliding('/foo/bar', ['/foo/bar', '/foo/quux'])
    True
    >>> are_folders_colliding('/foo/bar', ['/foo/bar/baz'])
    True
    >>> are_folders_colliding('/foo/bar', ['/foo'])
    True
    ```

    Args:
        check_folder (str): The folder to check for.
        existing_folders (Iterable[str]): The folders to check against.
        folder_to_skip (Union[str, None], optional): If given, a folder in the
            `existing_folders` iterable that should be skipped.
            Defaults to None.

    Returns:
        bool: Whether `check_folder` is the parent or child of any of the folders
            inside `existing_folders` excluding `folder_to_skip` (if not `None`).
    """
    for existing_folder in existing_folders:
        if existing_folder == folder_to_skip:
            continue

        if (
            folder_is_inside_folder(check_folder, existing_folder)
            or folder_is_inside_folder(existing_folder, check_folder)
        ):
            return True

    return False


def archive_contains_issues(archive_file: str) -> bool:
    """Check whether an archive file contains complete issues or is one single
    issue.

    Args:
        archive_file (str): The archive file to check. Must have the zip or rar
            extension.

    Returns:
        bool: Whether the archive file contains complete issue files.
    """
    ext = splitext(archive_file)[1].lower()

    if ext == '.zip':
        with ZipFile(archive_file, "r") as zip:
            namelist = zip.namelist()

    elif ext == '.rar':
        namelist = run_rar([
            "lb", # List archive contents bare
            archive_file # Archive to list contents of
        ]).stdout.split("\n")[:-1]

    else:
        return False

    return any(
        splitext(f)[1].lower() in FileConstants.CONTAINER_EXTENSIONS
        for f in namelist
    )


# region Conversion
def uppercase_drive_letter(path: str) -> str:
    """Return the input, but if it's a Windows path that starts with a drive
    letter, then return the path with the drive letter uppercase.

    Args:
        path (str): The input path, possibly a Windows path with a drive letter.

    Returns:
        str: The input path, but with an upper case Windows drive letter if
        a Windows drive letter is present.
    """
    if (
        len(path) >= 4
        and (
            path[1:3] == ":\\"
            or path[1:3] == ":/"
        )
        and path[0].lower() in CharConstants.ALPHABET
    ):
        path = path[0].upper() + path[1:]

    return path


def set_detected_extension(filepath: str) -> str:
    """Find the archive type of a file based on its actual mimetype (via magic
    bytes) and return the filepath with the correct extension. If the file
    is not an archive or the archive is not recognised, the original
    filepath is returned.

    Note: This function is not very fast because it has to read the first few
    bytes of the file from disc. So only use when really necessary.

    Args:
        filepath (str): The filepath to check and possibly change the extension of.

    Returns:
        str: The filepath with the correct extension based on the archive type.
    """
    ext = get_archive_mimetype(filepath)
    if ext is None:
        return filepath

    # Found archive type
    file_parts = splitext(filepath)
    current_extension = file_parts[1].lower().lstrip('.')
    if current_extension == ext:
        # Already has the correct extension
        return filepath

    if current_extension in FileConstants.CB_TO_ARCHIVE_EXTENSIONS:
        # Current file uses cb* extension instead of normal extension
        # (e.g. cbz instead of zip), so find cb* version of proper extension
        for cb_ext, normal_ext in FileConstants.CB_TO_ARCHIVE_EXTENSIONS.items():
            if ext == normal_ext:
                ext = cb_ext
                break
        else:
            # Not an archive
            return filepath

    return file_parts[0] + '.' + ext


def change_basefolder(
    files: Iterable[str],
    current_base_folder: str,
    desired_base_folder: str
) -> Dict[str, str]:
    """
    Propose new filenames with a different base folder for a list of files.
    It's only a proposition, so nothing is actually renamed.

    ```
    >>> change_basefolder(
        ['/foo/bar/baz.cbr', '/foo/bar/quux/tac.cbr'],
        '/foo/bar',
        '/new'
    )
    {
        '/foo/bar/baz.cbr': '/new/baz.cbr',
        '/foo/bar/quux/tac.cbr': '/new/quux/tac.cbr'
    }
    ```

    Args:
        files (Iterable[str]): Files to change the base folder for.
        current_base_folder (str): Current base folder, to replace.
        desired_base_folder (str): Desired base folder, to replace with.

    Returns:
        Dict[str, str]: Key is old filename, value is new filename.
    """
    file_changes = {
        f: abspath(join(
            desired_base_folder,
            relpath(
                f,
                current_base_folder
            )
        ))
        for f in files
    }

    return file_changes


def clean_filepath_simple(filepath: str) -> str:
    """Clean a filepath by removing illegal characters. This makes it safe to
    use in a filesystem.

    ```
    >>> clean_filepath_simple('/comics/Batman: The Start... ')
    '/comics/Batman The Start'
    ```

    Args:
        filepath (str): The filepath to be cleaned.

    Returns:
        str: The cleaned filepath.
    """
    safe_filepath = filepath_cleaner.sub('', filepath)
    return safe_filepath


def clean_filepath_smartly(filepath: str) -> str:
    """Clean a filepath by replacing illegal characters smartly. Remove the
    character, replace it with a dash or replace it with a dash with spaces
    around it, all based on the context. This makes it safe to use in a
    filesystem.

    ```
    >>> clean_filepath_smartly('/comics/Batman: Joker>Riddler... ')
    '/comics/Batman - Joker-Riddler'
    ```

    Args:
        filepath (str): The filepath to be cleaned.

    Returns:
        str: The cleaned filepath.
    """
    save_filepath = smart_filepath_cleaner_compact.sub('-', filepath)
    save_filepath = smart_filepath_cleaner_spaced.sub(' - ', save_filepath)
    save_filepath = clean_filepath_simple(save_filepath)
    return save_filepath


def clean_filestring_simple(filestring: str) -> str:
    """Clean (a part of) a filename by removing illegal characters. This makes
    it safe to use in a filesystem. This does the same as
    `clean_filepath_simple()`, but also replaces `/` and `\\`.

    ```
    >>> clean_filestring_simple('Batman/Bruce: Which one is it?')
    'BatmanBruce Which one is it'
    ```

    Args:
        filestring (str): The string to clean.

    Returns:
        str: The cleaned string.
    """
    return clean_filepath_simple(
        filestring.replace('/', '').replace('\\', '')
    )


def clean_filestring_smartly(filestring: str) -> str:
    """Clean (a part of) a filename by replacing illegal characters smartly.
    Remove the character, replace it with a dash or replace it with a dash with
    spaces around it, all based on the context. This does the same as
    `clean_filepath_smartly()`, but also replaces `/` and `\\`. This makes it
    safe to use in a filesystem.

    ```
    >>> clean_filestring_smartly('Batman/Bruce: Which one is it?')
    'Batman-Bruce - Which one is it'
    ```

    Args:
        filestring (str): The string to clean.

    Returns:
        str: The cleaned string.
    """
    save_filepath = smart_filestring_cleaner_compact.sub('-', filestring)
    save_filepath = save_filepath.replace(' / ', ' - ')
    save_filepath = clean_filepath_smartly(save_filepath)
    return save_filepath


# region Processing
def common_folder(files: Sequence[str]) -> str:
    """Find the deepest folder that is shared between the folders and files.

    ```
    >>> common_folder(['/foo/bar/baz', '/foo/bar/quux/tac.cbr'])
    '/foo/bar'
    >>> common_folder(['/foo/bar/baz'])
    '/foo/bar/baz'
    ```

    Args:
        files (Sequence[str]): The list of files to find the deepest common
            folder for.

    Returns:
        str: The path of the deepest common folder.
    """
    if len(files) == 1:
        return dirname(files[0])

    return commonpath(files)


def generate_archive_folder(
    volume_folder: str,
    archive_file: str
) -> str:
    """Generate a folder in which the given archive file can be extracted. The
    folder is not created.

    ```
    >>> generate_archive_folder(
        '/comics/Batman',
        '/comics/Batman/Batman #1-100/Batman (2010) #1-100.cbr'
    )
    '/comics/Batman/.archive_extract_Batman #1-100_Batman (2010) #1-100'
    ```

    Args:
        volume_folder (str): The volume folder that the archive file is in.
        archive_file (str): The filepath of the archive file itself.

    Returns:
        str: The folder in which the archive file can be extracted.
    """
    folder_name_parts = (
        Constants.ARCHIVE_EXTRACT_FOLDER,
        *relpath(splitext(archive_file)[0], volume_folder).split(sep)
    )

    return join(
        volume_folder,
        '_'.join(folder_name_parts)
    )


# region Creation
def create_folder(folder: str) -> None:
    """Create a folder recursively, if any of the folders don't exist already.

    Args:
        folder (str): The path to the folder to create.
    """
    makedirs(folder, exist_ok=True)
    return


def create_zip_archive(
    base_folder: str,
    zip_filename: str
) -> None:
    """Put all files in a folder (recursively) into a zip archive.

    Args:
        base_folder (str): The folder to zip. The folder itself is not included.
        zip_filename (str): The path of the zip file to create.
    """
    with ZipFile(zip_filename, "w", ZIP_DEFLATED) as zip:
        for file in list_files(base_folder):
            zip.write(file, relpath(file, base_folder))
    return


# region Moving
def __copy2(src, dst, *, follow_symlinks=True):
    try:
        return copy2(src, dst, follow_symlinks=follow_symlinks)

    except PermissionError as pe:
        if pe.errno == 1:
            # Issue 117
            # NFS file system doesn't allow/support chmod.
            # This is done after the file is already copied. So just accept that
            # it isn't possible to change the permissions. Continue like normal.
            return dst

        raise

    except OSError as oe:
        if oe.errno == 524:
            # Issue 229
            # NFS file system doesn't allow/support setting extended attributes.
            # This is done after the file is already copied. So just accept that
            # it isn't possible to set them. Continue like normal.
            return dst

        raise


def rename_file(
    before: str,
    after: str
) -> None:
    """Rename a file/folder, but also taking care of creating the new location,
    handling the possible complications with files on OSes and filesystems,
    moving a folder into a sub-folder of itself and logging the rename.

    Args:
        before (str): The current filepath of the file.
        after (str): The new desired filepath of the file.
    """
    LOGGER.debug(f'Renaming file {before} to {after}')

    if folder_is_inside_folder(before, after):
        # Cannot move folder into itself
        old_before = before
        before = old_before + '_temp'
        move(old_before, before, copy_function=__copy2)

    create_folder(dirname(after))

    # Move file into folder
    move(before, after, copy_function=__copy2)

    return


def copy_directory(source: str, target: str) -> None:
    """Copy a directory.

    Args:
        source (str): The current folderpath of the source directory.
        target (str): The desired folderpath to where the directory should be copied.
    """
    copytree(source, target, copy_function=__copy2)
    return


# region Deletion
def delete_file_folder(path: str) -> None:
    """Delete a file or folder. In the case of a folder, it is deleted
    recursively. Does nothing if it doesn't exist. I.E.: delete whatever it is,
    if it exists.

    Args:
        path (str): The path to the file or folder.
    """
    if isfile(path):
        remove(path)

    elif isdir(path):
        rmtree(path, ignore_errors=True)

    return


def delete_empty_parent_folders(top_folder: str, root_folder: str) -> None:
    """Delete parent folders that are empty until we reach a folder with content
    or the root folder. Take notice of the difference between this function and
    `delete_empty_child_folders()`.

    For example, assume the following folder and file structure:

    ```
    /ant/bear/cat/dog/
    /ant/bear/cow/deer.txt
    ```

    Then:

    ```
    >>> delete_empty_parent_folders(
        top_folder="/ant/bear/cat/dog",
        root_folder="/ant"
    )
    # Deletes "/ant/bear/cat"
    ```

    Args:
        top_folder (str): The folder to start deleting from.
        root_folder (str): The root folder to stop at in case we reach it.
    """
    if top_folder == root_folder:
        return

    LOGGER.debug(
        f'Deleting empty parent folders from {top_folder} until {root_folder}'
    )

    if not folder_is_inside_folder(root_folder, top_folder):
        LOGGER.error(f'The folder {top_folder} is not in {root_folder}')
        return

    if isfile(top_folder):
        top_folder = dirname(top_folder)

    parent_folder = top_folder
    child_folder = None

    while parent_folder:
        if isdir(parent_folder):
            if samefile(parent_folder, root_folder):
                break

            if listdir(parent_folder) not in ([], [child_folder]):
                # Folder has content and that content isn't just the empty child
                break

        child_folder = basename(parent_folder)
        parent_folder = dirname(parent_folder)

    if child_folder:
        lowest_empty_folder = join(parent_folder, child_folder)
        LOGGER.debug(f'Deleting folder and children: {lowest_empty_folder}')
        delete_file_folder(lowest_empty_folder)

    return


def delete_empty_child_folders(
    base_folder: str,
    skip_hidden_folders: bool = False
) -> None:
    """Delete child folders that don't (recursively) contain any files. Take
    notice of the difference between this function and
    `delete_empty_parent_folders()`.

    For example, assume the following folder and file structure:

    ```
    /ant/bear/cat/dog/
    /ant/bear/cat/deer/
    /ant/bee/cow/
    /ant/bee/camel.txt
    /ant/bat.txt
    ```

    Then:

    ```
    >>> delete_empty_child_folders(base_folder="/ant")
    # Deletes "/ant/bear" and "/ant/bee/cow"
    ```

    Args:
        base_folder (str): The base folder to remove empty children of.
        skip_hidden_folders (bool, optional): Whether to skip hidden folders
            (folders starting with `.`). Defaults to False.
    """
    LOGGER.debug(f'Deleting empty child folders from {base_folder}')

    if isfile(base_folder):
        base_folder = dirname(base_folder)

    resulting_folders: List[str] = []

    def _decf(
        folder: str,
        resulting_folders: List[str],
        _first_call: bool = True
    ) -> bool:
        folders: List[str] = []
        contains_files: bool = False

        for f in scandir(folder):
            if f.is_dir() and (
                not skip_hidden_folders
                or not f.name.startswith('.')
            ):
                folders.append(f.path)

            elif f.is_file():
                contains_files = True

        if not (contains_files or folders):
            # Folder is empty
            return True

        sub_folder_results = {
            f: _decf(f, resulting_folders, False)
            for f in folders
        }

        if not contains_files and all(sub_folder_results.values()):
            # Folder only contains (indirectly) empty folders
            if _first_call:
                resulting_folders.extend(sub_folder_results.keys())
            return True

        resulting_folders.extend((
            k
            for k, v in sub_folder_results.items()
            if v
        ))

        return False

    _decf(base_folder, resulting_folders)

    for f in resulting_folders:
        LOGGER.debug(f"Deleting folder and children: {f}")
        delete_file_folder(f)

    return
