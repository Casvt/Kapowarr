# -*- coding: utf-8 -*-

from __future__ import annotations

from datetime import datetime
from os import remove
from os.path import basename, dirname, exists, join
from re import compile
from sqlite3 import OperationalError
from typing import List

from backend.base.custom_exceptions import (DatabaseFileNotFound,
                                            InvalidDatabaseFile)
from backend.base.definitions import (Constants, DatabaseBackupEntry,
                                      InvalidDatabaseReason, StartType)
from backend.base.files import copy, folder_path, list_files, rename_file
from backend.base.logging import LOGGER
from backend.internals.db import DBConnection, get_db
from backend.internals.db_migration import DatabaseMigrationHandler
from backend.internals.settings import Settings

# region Backup
DB_FILE_REGEX = compile(
    r'Kapowarr_(?P<year>\d{4})_(?P<month>\d{2})_(?P<day>\d{2})_(?P<hour>\d{2})_(?P<minute>\d{2}).db'
)


def get_backups() -> List[DatabaseBackupEntry]:
    """Get a list of currently existing backups, as found in the backup folder.

    Returns:
        List[DatabaseBackupEntry]: The backups found.
    """
    db_files = list_files(Settings().sv.db_backup_folder, ('.db',))
    result: List[DatabaseBackupEntry] = []

    for file in db_files:
        file_match = DB_FILE_REGEX.match(basename(file))
        if file_match is None:
            continue

        time_els = file_match.groupdict()
        timestamp = datetime(
            year=int(time_els['year']),
            month=int(time_els['month']),
            day=int(time_els['day']),
            hour=int(time_els['hour']),
            minute=int(time_els['minute'])
        ).timestamp()

        result.append({
            "index": len(result),
            "creation_date": int(timestamp),
            "filepath": file,
            "filename": basename(file)
        })

    result.sort(key=lambda f: f["creation_date"], reverse=True)

    return result


def get_backup(index: int) -> DatabaseBackupEntry:
    """Get info on a specific database backup.

    Args:
        index (int): The index of the backup (supplied by `get_backups()`).

    Raises:
        DatabaseFileNotFound: No backup entry with the given index.

    Returns:
        DatabaseBackupEntry: The info on the backup entry.
    """
    for b in get_backups():
        if b['index'] == index:
            return b
    raise DatabaseFileNotFound(index)


def create_database_copy(folder: str) -> str:
    """Export the current database into a file.

    Args:
        folder (str): The folder to put the copy into.

    Returns:
        str: The complete filepath of the created file.
    """
    current_date = datetime.now().strftime(r"%Y_%m_%d_%H_%M")
    filename = join(folder, f'Kapowarr_{current_date}.db')
    DBConnection().create_backup(filename)
    return filename


def backup_database() -> None:
    """
    Create a backup of the database, delete old backups that
    surpass the backup limit and set timer for next run.
    """
    settings = Settings()
    sv = settings.get_settings()
    current_backups = get_backups()

    while len(current_backups) >= sv.db_backup_amount:
        removed_backup = current_backups.pop()["filepath"]
        remove(removed_backup)
        LOGGER.info(f"Removed database backup: {removed_backup}")

    filepath = create_database_copy(sv.db_backup_folder)
    LOGGER.info(f"Created database backup: {filepath}")

    return


# region Import
def revert_db_import(
    swap: bool,
    other_db_file: str = ''
) -> None:
    """Revert the database import process.

    Args:
        swap (bool): Keep the other database file instead of the current
            database file.

        other_db_file (str, optional): The other database file. Keep empty to
            use `Constants.DB_ORIGINAL_FILENAME`.
            Defaults to ''.

    Raises:
        InvalidDatabaseFile: The other database file does not exist.
    """
    original_db_file = DBConnection.default_file
    if not other_db_file:
        other_db_file = join(
            dirname(DBConnection.default_file),
            Constants.DB_ORIGINAL_NAME
        )

    if not exists(other_db_file):
        raise InvalidDatabaseFile(
            other_db_file,
            InvalidDatabaseReason.DOES_NOT_EXIST
        )

    if swap:
        remove(original_db_file)
        rename_file(
            other_db_file,
            original_db_file
        )

    else:
        remove(other_db_file)

    return


def import_db(
    new_db_file: str,
    copy_hosting_settings: bool
) -> None:
    """Replace the current database with a new one.

    Args:
        new_db_file (str): The path to the new database file.
        copy_hosting_settings (bool): Keep the hosting settings from the current
            database.

    Raises:
        InvalidDatabaseFile: The new database file is invalid or unsupported.
    """
    from backend.internals.server import Server

    LOGGER.info(f"Importing new database; {copy_hosting_settings=}")

    cursor_current = get_db()
    cursor_new = DBConnection(db_file=new_db_file).cursor()

    try:
        try:
            database_version = cursor_new.execute(
                "SELECT value FROM config WHERE key = 'database_version' LIMIT 1;"
            ).exists()
            if not isinstance(database_version, int):
                raise OperationalError
        except OperationalError:
            raise InvalidDatabaseFile(
                new_db_file,
                InvalidDatabaseReason.NOT_KAPOWARR_DB
            )

        if database_version > DatabaseMigrationHandler.latest_db_version():
            raise InvalidDatabaseFile(
                new_db_file,
                InvalidDatabaseReason.VERSION_NOT_SUPPORTED
            )

    except InvalidDatabaseFile:
        cursor_new.connection.close()
        revert_db_import(
            swap=False,
            other_db_file=new_db_file
        )
        raise

    if copy_hosting_settings:
        cursor_current.execute("""
            SELECT key, value
            FROM config
            WHERE key = 'host'
                OR key = 'port'
                OR key = 'url_base';
            """
        )
        for key, value in cursor_current:
            cursor_new.execute(
                "UPDATE config SET value = ? WHERE key = ?;",
                (value, key)
            )

    has_backup_task = cursor_new.execute(
        "SELECT 1 FROM task_intervals WHERE task_name = 'backup_db';"
    ).exists()
    if has_backup_task:
        last_run = cursor_current.execute(
            "SELECT last_run FROM task_intervals WHERE task_name = 'backup_db';"
        ).exists()
        cursor_new.execute(
            "UPDATE task_intervals SET last_run = ? WHERE task_name = 'backup_db';",
            (last_run,))

    cursor_new.connection.commit()
    cursor_new.connection.close()

    DBConnection().merge_wal_files()
    rename_file(
        DBConnection.default_file,
        join(dirname(DBConnection.default_file), Constants.DB_ORIGINAL_NAME)
    )
    rename_file(
        new_db_file,
        DBConnection.default_file
    )

    Server().restart(StartType.RESTART_DB_CHANGES)

    return


def import_db_backup(
    index: int,
    copy_hosting_settings: bool
) -> None:
    """Replace the current database with a backup.

    Args:
        index (int): The index of the backup (supplied by `get_backups()`).
        copy_hosting_settings (bool): Keep the hosting settings from the current
            database.

    Raises:
        DatabaseFileNotFound: No backup entry with the given index.
        InvalidDatabaseFile: The new database file is invalid or unsupported.
    """
    LOGGER.info(f"Importing database backup with index {index}")

    backup = get_backup(index)
    dest = copy(
        backup["filepath"],
        folder_path("db", "Kapowarr_upload.db")
    )

    import_db(dest, copy_hosting_settings)
    return
