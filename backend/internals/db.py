# -*- coding: utf-8 -*-

"""
Setting up the database and handling connections
"""

from __future__ import annotations

from os.path import dirname, exists, isdir, join
from sqlite3 import (PARSE_DECLTYPES, Connection, Cursor, ProgrammingError,
                     Row, register_adapter, register_converter)
from threading import current_thread
from time import time
from typing import Any, Dict, List, Union

from flask import g

from backend.base.definitions import Constants
from backend.base.helpers import CommaList
from backend.base.logging import LOGGER, set_log_level
from backend.internals.db_migration import migrate_db


class KapowarrCursor(Cursor):

    row_factory: Union[Type[Row], None] # type: ignore

    @property
    def lastrowid(self) -> int:
        return super().lastrowid or 1

    def fetchonedict(self) -> Union[dict, None]:
        """Same as `fetchone` but convert the Row object to a dict.

        Returns:
            Union[dict, None]: The dict or None i.c.o. no result.
        """
        r = self.fetchone()
        if r is None:
            return r
        return dict(r)

    def fetchmanydict(self, size: Union[int, None] = 1) -> List[dict]:
        """Same as `fetchmany` but convert the Row object to a dict.

        Args:
            size (Union[int, None], optional): The amount of rows to return.
                Defaults to 1.

        Returns:
            List[dict]: The rows.
        """
        return [dict(e) for e in self.fetchmany(size)]

    def fetchalldict(self) -> List[dict]:
        """Same as `fetchall` but convert the Row object to a dict.

        Returns:
            List[dict]: The results.
        """
        return [dict(e) for e in self]

    def exists(self) -> Union[Any, None]:
        """Return the first column of the first row, or `None` if not found.

        Returns:
            Union[Any, None]: The value of the first column of the first row,
            or `None` if not found.
        """
        r = self.fetchone()
        if r is None:
            return r
        return r[0]


class DBConnectionManager(type):
    instances: Dict[int, DBConnection] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> DBConnection:
        thread_id = current_thread().native_id or -1

        if (
            not thread_id in cls.instances
            or cls.instances[thread_id].closed
        ):
            cls.instances[thread_id] = super().__call__(*args, **kwargs)

        return cls.instances[thread_id]


class DBConnection(Connection, metaclass=DBConnectionManager):
    file = ''

    def __init__(self, timeout: float) -> None:
        """Create a connection with a database

        Args:
            timeout (float): How long to wait before giving up on a command
        """
        LOGGER.debug(f'Creating connection {self}')
        super().__init__(
            self.file,
            timeout=timeout,
            detect_types=PARSE_DECLTYPES
        )
        super().cursor().execute("PRAGMA foreign_keys = ON;")
        self.closed = False
        return

    def cursor( # type: ignore
        self,
        force_new: bool = False
    ) -> KapowarrCursor:
        """Get a database cursor from the connection.

        Args:
            force_new (bool, optional): Get a new cursor instead of the cached
            one.
                Defaults to False.

        Returns:
            KapowarrCursor: The database cursor.
        """
        if not hasattr(g, 'cursors'):
            g.cursors = []

        if not force_new and g.cursors:
            return g.cursors[0]
        else:
            c = KapowarrCursor(self)
            c.row_factory = Row
            g.cursors.append(c)
            return g.cursors[-1]

    def close(self) -> None:
        """Close the database connection"""
        LOGGER.debug(f'Closing connection {self}')
        self.closed = True
        super().close()
        return

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}; {current_thread().name}; {id(self)}>'


def set_db_location(
    db_folder: Union[str, None] = None
) -> None:
    """Setup database location. Create folder for database and set location for
    `db.DBConnection` and `db.TempDBConnection`.

    Args:
        db_folder (Union[str, None], optional): The folder in which the database
        will be stored or in which a database is for Kapowarr to use. Give
        `None` for the default location.
            Defaults to None.

    Raises:
        ValueError: Value of `db_folder` exists but is not a folder.
    """
    from backend.base.files import create_folder, folder_path
    from backend.internals.settings import about_data

    if db_folder:
        if exists(db_folder) and not isdir(db_folder):
            raise ValueError

    db_file_location = join(
        db_folder or folder_path(*Constants.DB_FOLDER),
        Constants.DB_NAME
    )

    LOGGER.debug(f'Setting database location: {db_file_location}')

    create_folder(dirname(db_file_location))

    DBConnection.file = about_data['database_location'] = db_file_location

    return


def get_db(force_new: bool = False) -> KapowarrCursor:
    """
    Get a database cursor instance or create a new one if needed

    Args:
        force_new (bool, optional): Decides if a new cursor is
        returned instead of the standard one.
            Defaults to False.

    Returns:
        KapowarrCursor: Database cursor instance that outputs Row objects.
    """
    cursor = (
        DBConnection(timeout=Constants.DB_TIMEOUT)
        .cursor(force_new=force_new)
    )
    return cursor


def close_db(e: Union[None, BaseException] = None):
    """Close database cursor, commit database and close database.

    Args:
        e (Union[None, BaseException], optional): Error. Defaults to None.
    """
    try:
        cursors = g.cursors
        db: DBConnection = cursors[0].connection
        for c in cursors:
            c.close()
        delattr(g, 'cursors')
        db.commit()
        if not current_thread().name.startswith('waitress-'):
            db.close()

    except (AttributeError, ProgrammingError):
        pass

    return


def close_all_db() -> None:
    "Close all non-temporary database connections that are still open"
    LOGGER.debug('Closing any open database connections')

    for i in DBConnectionManager.instances.values():
        if not i.closed:
            i.close()

    c = DBConnection(timeout=20.0)
    c.commit()
    c.close()
    return


def setup_db() -> None:
    """
    Setup the database tables and default config when they aren't setup yet
    """
    from backend.internals.settings import (Settings, credential_sources,
                                            task_intervals)

    cursor = get_db()
    cursor.execute("PRAGMA journal_mode = wal;")
    register_adapter(bool, lambda b: int(b))
    register_converter("BOOL", lambda b: b == b'1')
    register_adapter(CommaList, lambda c: str(c))

    setup_commands = """
        CREATE TABLE IF NOT EXISTS config(
            key VARCHAR(100) PRIMARY KEY,
            value BLOB
        );
        CREATE TABLE IF NOT EXISTS root_folders(
            id INTEGER PRIMARY KEY,
            folder VARCHAR(254) UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS volumes(
            id INTEGER PRIMARY KEY,
            comicvine_id INTEGER NOT NULL,
            title VARCHAR(255) NOT NULL,
            alt_title VARCHAR(255),
            year INTEGER(5),
            publisher VARCHAR(255),
            volume_number INTEGER(8) DEFAULT 1,
            description TEXT,
            site_url TEXT NOT NULL DEFAULT "",
            cover BLOB,
            monitored BOOL NOT NULL DEFAULT 0,
            root_folder INTEGER NOT NULL,
            folder TEXT,
            custom_folder BOOL NOT NULL DEFAULT 0,
            last_cv_fetch INTEGER(8) DEFAULT 0,
            special_version VARCHAR(255),
            special_version_locked BOOL NOT NULL DEFAULT 0,

            FOREIGN KEY (root_folder) REFERENCES root_folders(id)
        );
        CREATE TABLE IF NOT EXISTS issues(
            id INTEGER PRIMARY KEY,
            volume_id INTEGER NOT NULL,
            comicvine_id INTEGER NOT NULL UNIQUE,
            issue_number VARCHAR(20) NOT NULL,
            calculated_issue_number FLOAT(20) NOT NULL,
            title VARCHAR(255),
            date VARCHAR(10),
            description TEXT,
            monitored BOOL NOT NULL DEFAULT 1,

            FOREIGN KEY (volume_id) REFERENCES volumes(id)
                ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS issues_volume_number_index
            ON issues(volume_id, calculated_issue_number);
        CREATE TABLE IF NOT EXISTS files(
            id INTEGER PRIMARY KEY,
            filepath TEXT UNIQUE NOT NULL,
            size INTEGER
        );
        CREATE TABLE IF NOT EXISTS issues_files(
            file_id INTEGER NOT NULL,
            issue_id INTEGER NOT NULL,

            FOREIGN KEY (file_id) REFERENCES files(id)
                ON DELETE CASCADE,
            FOREIGN KEY (issue_id) REFERENCES issues(id),
            CONSTRAINT PK_issues_files PRIMARY KEY (
                file_id,
                issue_id
            )
        );
        CREATE TABLE IF NOT EXISTS volume_files(
            file_id INTEGER PRIMARY KEY,
            volume_id INTEGER NOT NULL,
            file_type VARCHAR(15) NOT NULL,

            FOREIGN KEY (volume_id) REFERENCES volumes(id)
                ON DELETE CASCADE,
            FOREIGN KEY (file_id) REFERENCES files(id)
                ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS torrent_clients(
            id INTEGER PRIMARY KEY,
            type VARCHAR(255) NOT NULL,
            title VARCHAR(255) NOT NULL,
            base_url TEXT NOT NULL,
            username VARCHAR(255),
            password VARCHAR(255),
            api_token VARCHAR(255)
        );
        CREATE TABLE IF NOT EXISTS download_queue(
            id INTEGER PRIMARY KEY,
            client_type VARCHAR(255) NOT NULL,
            torrent_client_id INTEGER,

            download_link TEXT NOT NULL,
            filename_body TEXT NOT NULL,
            source VARCHAR(25) NOT NULL,

            volume_id INTEGER NOT NULL,
            issue_id INTEGER,
            web_link TEXT,
            web_title TEXT,
            web_sub_title TEXT,

            FOREIGN KEY (torrent_client_id) REFERENCES torrent_clients(id),
            FOREIGN KEY (volume_id) REFERENCES volumes(id),
            FOREIGN KEY (issue_id) REFERENCES issues(id)
        );
        CREATE TABLE IF NOT EXISTS download_history(
            web_link TEXT,
            web_title TEXT,
            web_sub_title TEXT,
            file_title TEXT,

            volume_id INTEGER,
            issue_id INTEGER,

            source VARCHAR(25),
            downloaded_at INTEGER NOT NULL CHECK (downloaded_at > 0),

            FOREIGN KEY (volume_id) REFERENCES volumes(id)
                ON DELETE SET NULL,
            FOREIGN KEY (issue_id) REFERENCES issues(id)
                ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS task_history(
            task_name NOT NULL,
            display_title NOT NULL,
            run_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS task_intervals(
            task_name PRIMARY KEY,
            interval INTEGER NOT NULL,
            next_run INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS blocklist(
            id INTEGER PRIMARY KEY,
            volume_id INTEGER,
            issue_id INTEGER,

            web_link TEXT,
            web_title TEXT,
            web_sub_title TEXT,

            download_link TEXT UNIQUE,
            source VARCHAR(30),

            reason INTEGER NOT NULL CHECK (reason > 0),
            added_at INTEGER NOT NULL CHECK (added_at > 0),

            FOREIGN KEY (volume_id) REFERENCES volumes(id)
                ON DELETE SET NULL,
            FOREIGN KEY (issue_id) REFERENCES issues(id)
                ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS credentials_sources(
            id INTEGER PRIMARY KEY,
            source VARCHAR(30) NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS credentials(
            id INTEGER PRIMARY KEY,
            source INTEGER NOT NULL UNIQUE,
            email VARCHAR(255) NOT NULL,
            password VARCHAR(255) NOT NULL,

            FOREIGN KEY (source) REFERENCES credentials_sources(id)
                ON DELETE CASCADE
        );
    """
    cursor.executescript(setup_commands)

    settings = Settings()

    set_log_level(settings['log_level'])

    migrate_db()

    # Generate api key
    if settings['api_key'] is None:
        settings.generate_api_key()

    # Add task intervals
    LOGGER.debug(f'Inserting task intervals: {task_intervals}')
    current_time = round(time())
    cursor.executemany(
        """
        INSERT INTO task_intervals
        VALUES (?, ?, ?)
        ON CONFLICT(task_name) DO
        UPDATE
        SET
            interval = ?;
        """,
        ((k, v, current_time, v) for k, v in task_intervals.items())
    )

    # Add credentials sources
    LOGGER.debug(f'Inserting credentials sources: {credential_sources}')
    cursor.executemany(
        """
        INSERT OR IGNORE INTO credentials_sources(source)
        VALUES (?);
        """,
        [(s,) for s in credential_sources]
    )

    return
