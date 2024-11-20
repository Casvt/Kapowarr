# -*- coding: utf-8 -*-

"""
Handling folders, files and filenames.
"""

from collections import deque
from os import listdir, makedirs, remove, scandir
from os.path import (abspath, basename, commonpath, dirname, isdir,
                     isfile, join, relpath, samefile, splitext)
from re import compile
from shutil import copytree, move, rmtree
from typing import Deque, Dict, Iterable, List, Sequence, Set

from backend.base.definitions import CharConstants
from backend.base.helpers import check_filter, force_suffix
from backend.base.logging import LOGGER

filename_cleaner = compile(
    r'(<|>|(?<!^\w):|\"|\||\?|\*|\x00|(?:\s|\.)+(?=$|\\|/))'
)


# region Conversion
def dirname_times(path: str, amount: int = 1) -> str:
    """Apply `os.path.dirname` to `path` for `amount` times.

    Args:
        path (str): The path to apply to.
        amount (int, optional): The amount of times to apply dirname.
            Defaults to 1.

    Returns:
        str: The resulting path.
    """
    for _ in range(0, amount):
        path = dirname(path)
    return path


def folder_path(*folders: str) -> str:
    """Turn filepaths relative to the project folder into absolute paths.

    Returns:
        str: The absolute filepath.
    """
    return join(dirname_times(abspath(__file__), 3), *folders)


def folder_is_inside_folder(
    base_folder: str,
    folder: str
) -> bool:
    """Check if folder is inside base_folder.

    Args:
        base_folder (str): The base folder to check against.
        folder (str): The folder that should be inside base_folder.

    Returns:
        bool: Whether or not folder is in base_folder.
    """
    return (
        force_suffix(abspath(folder))
    ).startswith(
        force_suffix(abspath(base_folder))
    )


def find_common_folder(files: Sequence[str]) -> str:
    """Find the deepest folder that is shared between the files.

    Args:
        files (Sequence[str]): The list of files to find the deepest common folder
        for.

    Returns:
        str: The path of the deepest common folder.
    """
    if len(files) == 1:
        return dirname(files[0])

    return commonpath(files)


def uppercase_drive_letter(path: str) -> str:
    """Return the input, but if it's a Windows path that starts with a drive
    letter, then return the path with the drive letter uppercase.

    Args:
        path (str): The input path, possibly a windows path with a drive letter.

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


def make_filename_safe(unsafe_filename: str) -> str:
    """Make a filename safe to use in a filesystem.
    It removes illegal characters.

    Args:
        unsafe_filename (str): The filename to be made safe.

    Returns:
        str: The filename, now with characters removed/replaced
        so that it's filesystem-safe.
    """
    safe_filename = filename_cleaner.sub('', unsafe_filename)
    return safe_filename


def list_files(folder: str, ext: Iterable[str] = []) -> List[str]:
    """List all files in a folder recursively with absolute paths. Hidden files
    (files starting with `.`) are ignored.

    Args:
        folder (str): The base folder to search through.

        ext (Iterable[str], optional): File extensions to only include.
        Dot-prefix not necessary.
            Defaults to [].

    Returns:
        List[str]: The paths of the files in the folder.
    """
    files: Deque[str] = deque()

    def _list_files(folder: str, ext: Set[str] = set()):
        """Internal function to add all files in a folder to the files list.

        Args:
            folder (str): The base folder to search through.
            ext (Set[str], optional): A set of lowercase, dot-prefixed,
            extensions to filter for or empty for no filter. Defaults to set().
        """
        for f in scandir(folder):
            if f.is_dir():
                _list_files(f.path, ext)

            elif (
                f.is_file()
                and not f.name.startswith('.')
                and check_filter(
                    splitext(f.name)[1].lower(),
                    ext
                )
            ):
                files.append(f.path)

    ext = {'.' + e.lower().lstrip('.') for e in ext}
    _list_files(folder, ext)
    return list(files)


def propose_basefolder_change(
    files: Iterable[str],
    current_base_folder: str,
    desired_base_folder: str
) -> Dict[str, str]:
    """
    Propose new filenames with a different base folder for a list of files.
    E.g. /current/base/folder/file.ext -> /desired_base_folder/file.ext

    Args:
        files (Iterable[str]): Iterable of files to change base folder for.
        current_base_folder (str): Current base folder, to replace.
        desired_base_folder (str): Desired base folder, to replace with.

    Returns:
        Dict[str, str]: Key is old filename, value is new filename.
    """
    file_changes = {
        f: join(
            desired_base_folder,
            relpath(
                f,
                current_base_folder
            )
        )
        for f in files
    }

    return file_changes


# region Creation
def create_folder(folder: str) -> None:
    """Create a folder

    Args:
        folder (str): The path to the folder to create.
    """
    makedirs(folder, exist_ok=True)
    return


# region Moving
def rename_file(
    before: str,
    after: str
) -> None:
    """Rename a file, taking care of new folder locations and
    the possible complications with files on OS'es.

    Args:
        before (str): The current filepath of the file.
        after (str): The new desired filepath of the file.
    """
    if folder_is_inside_folder(before, after):
        # Cannot move folder into itself
        return

    LOGGER.debug(f'Renaming file {before} to {after}')

    create_folder(dirname(after))

    # Move file into folder
    try:
        move(before, after)
    except PermissionError:
        # Happens when moving between an NFS file system.
        # Raised when chmod is used inside.
        # Checking the source code, chmod is used at the very end,
        #     so just skipping it is alright I think.
        pass

    return


def copy_directory(source: str, target: str) -> None:
    """Copy a directory.

    Args:
        source (str): The path to the source directory.
        target (str): The path to where the directory should be copied.
    """
    try:
        copytree(source, target)
    except PermissionError:
        # Happens when moving between an NFS file system.
        # Raised when chmod is used inside.
        # Checking the source code, chmod is used at the very end,
        #     so just skipping it is alright I think.
        pass

    return


# region Deletion
def delete_file_folder(path: str) -> None:
    """Delete a file or folder. In the case of a folder, it is deleted recursively.

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

    For example, with the following file structure, and
    `top_folder="/a/b1/c1/d1", root_folder="/a"`, the folder `/a/b1/c1` is
    deleted.
    ```
    /a/b1/c1/d1/
    /a/b1/c2/d2.txt
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
                # Folder has content and it's not only the empty child
                break

        child_folder = basename(parent_folder)
        parent_folder = dirname(parent_folder)

    if child_folder:
        lowest_empty_folder = join(parent_folder, child_folder)
        LOGGER.debug(f'Deleting folder and children: {lowest_empty_folder}')
        delete_file_folder(lowest_empty_folder)

    return


def delete_empty_child_folders(base_folder: str) -> None:
    """Delete child folders that don't (indirectly) contain any files. Take
    notice of the difference between this function and
    `delete_empty_parent_folders()`.

    For example, with the following file structure, and `base_folder="/a"`,
    the folders `/a/b1` and `/a/b2/c2` are deleted because they don't contain
    any files.
    ```
    /a/b1/c1/d1/
    /a/b1/c1/d2/
    /a/b2/c2/
    /a/b2/c3.txt
    /a/b3.txt
    ```

    Args:
        base_folder (str): The base folder to remove children of.
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
            if f.is_dir():
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
