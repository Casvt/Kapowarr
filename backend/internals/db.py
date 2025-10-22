# -*- coding: utf-8 -*-

"""
Setting up the database, handling connections, using it and closing it.
"""

from __future__ import annotations

from os.path import dirname, exists, isdir, join
from sqlite3 import (PARSE_DECLTYPES, Connection, Cursor, ProgrammingError,
                     Row, register_adapter, register_converter)
from threading import current_thread
from time import time
from typing import Any, Dict, Iterable, Iterator, List, Type, Union

from flask import g

from backend.base.definitions import (Constants, DateType,
                                      SeedingHandling, SpecialVersion, T)
from backend.base.files import create_folder, folder_path
from backend.base.helpers import CommaList, current_thread_id
from backend.base.logging import LOGGER, set_log_level


class KapowarrCursor(Cursor):
    row_factory: Union[Type[Row], None] # type: ignore

    @property
    def lastrowid(self) -> int:
        return super().lastrowid or 1

    @property
    def connection(self) -> DBConnection:
        return super().connection # type: ignore

    def __init__(self, cursor: DBConnection, /) -> None:
        super().__init__(cursor)
        return

    def fetchonedict(self) -> Union[Dict[str, Any], None]:
        """Same as `fetchone` but convert the Row object to a dict.

        Returns:
            Union[Dict[str, Any], None]: The dict or None in case of no result.
        """
        r = self.fetchone()
        if r is None:
            return r
        return dict(r)

    def fetchmanydict(self, size: Union[int, None] = 1) -> List[Dict[str, Any]]:
        """Same as `fetchmany` but convert the Row object to a dict.

        Args:
            size (Union[int, None], optional): The amount of rows to return.
                Defaults to 1.

        Returns:
            List[Dict[str, Any]]: The rows.
        """
        return [dict(e) for e in self.fetchmany(size)]

    def fetchalldict(self) -> List[Dict[str, Any]]:
        """Same as `fetchall` but convert the Row object to a dict.

        Returns:
            List[Dict[str, Any]]: The results.
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

    def __enter__(self):
        """Start a transaction"""
        self.connection.isolation_level = None
        self.execute("BEGIN TRANSACTION;")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Commit the transaction or rollback if an exception occurred"""
        if self.connection.in_transaction:
            if exc_type is not None:
                self.execute("ROLLBACK;")
            else:
                self.execute("COMMIT;")

        self.connection.isolation_level = "DEFERRED"
        return


class DBConnectionManager(type):
    instances: Dict[int, DBConnection] = {}

    def __call__(cls, **kwargs: Any) -> DBConnection:
        thread_id = current_thread_id()

        if (
            not thread_id in cls.instances
            or cls.instances[thread_id].closed
        ):
            cls.instances[thread_id] = super().__call__(**kwargs)

        return cls.instances[thread_id]


class DBConnection(Connection, metaclass=DBConnectionManager):
    file = ''

    def __init__(
        self, *,
        timeout: float = Constants.DB_TIMEOUT
    ) -> None:
        """Create a connection with a database

        Args:
            timeout (float, optional): How long to wait before giving up
                on a command.
                Defaults to Constants.DB_TIMEOUT.
        """
        self.closed = False
        LOGGER.debug(f'Creating connection {self}')
        super().__init__(
            self.file,
            timeout=timeout,
            detect_types=PARSE_DECLTYPES
        )
        super().cursor().execute("PRAGMA foreign_keys = ON;")
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

        if not g.cursors:
            c = KapowarrCursor(self)
            c.row_factory = Row
            g.cursors.append(c)

        if not force_new:
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
        return f'<{self.__class__.__name__}; {current_thread().name}; {id(self)}; closed={self.closed}>'


def set_db_location(
    db_folder: Union[str, None]
) -> None:
    """Setup database location. Create folder for database and set location for
    `db.DBConnection`.

    Args:
        db_folder (Union[str, None], optional): The folder in which the database
            will be stored or in which a database is for Kapowarr to use. Give
            `None` for the default location.

    Raises:
        ValueError: Value of `db_folder` exists but is not a folder.
    """
    if db_folder:
        if exists(db_folder) and not isdir(db_folder):
            raise ValueError('Database location is not a folder')

    db_file_location = join(
        db_folder or folder_path(*Constants.DB_FOLDER),
        Constants.DB_NAME
    )

    LOGGER.debug(f'Setting database location: {db_file_location}')

    create_folder(dirname(db_file_location))

    DBConnection.file = db_file_location

    return


def get_db(force_new: bool = False) -> KapowarrCursor:
    """Get a database cursor instance or create a new one if needed.

    Args:
        force_new (bool, optional): Decides whether a new cursor is
            returned instead of the standard one.
            Defaults to False.

    Returns:
        KapowarrCursor: Database cursor instance that outputs Row objects.
    """
    return DBConnection().cursor(force_new=force_new)


def commit() -> None:
    """Commit the database changes"""
    get_db().connection.commit()
    return


def iter_commit(iterable: Iterable[T]) -> Iterator[T]:
    """Commit the database after yielding each value in the iterable. Also
    commits just before the first iteration starts.

    ```
    # commits
    for i in iter_commit(iterable):
        ...
        # commits
    ```

    Args:
        iterable (Iterable[T]): Iterable that will be iterated over like normal.

    Yields:
        Iterator[T]: Items of iterable.
    """
    commit = get_db().connection.commit
    commit()
    for i in iterable:
        yield i
        commit()
    return


def close_db(e: Union[BaseException, None] = None) -> None:
    """Close database cursor, commit database and close database.

    Args:
        e (Union[BaseException, None], optional): Error. Defaults to None.
    """
    if not hasattr(g, 'cursors'):
        return

    try:
        cursors = g.cursors
        db: DBConnection = cursors[0].connection
        for c in cursors:
            c.close()
        delattr(g, 'cursors')
        db.commit()
        if not current_thread().name.startswith('waitress-'):
            db.close()

    except ProgrammingError:
        pass

    return


def setup_db_adapters_and_converters() -> None:
    """Add DB adapters and converters for custom types and bool"""
    register_adapter(bool, lambda b: int(b))
    register_converter("BOOL", lambda b: b == b'1')
    register_adapter(CommaList, lambda c: str(c))
    register_adapter(SeedingHandling, lambda e: e.value)
    register_adapter(SpecialVersion, lambda e: e.value)
    register_adapter(DateType, lambda e: e.value)
    return


def setup_db() -> None:
    """Setup the default config and database connection and tables"""
    from backend.internals.db_migration import DatabaseMigrationHandler
    from backend.internals.settings import Settings, task_intervals

    cursor = get_db()
    cursor.execute("PRAGMA journal_mode = wal;")
    setup_db_adapters_and_converters()

    cursor.executescript(DB_SCHEMA)

    settings = Settings()
    settings_values = settings.get_settings()

    set_log_level(settings_values.log_level)

    DatabaseMigrationHandler.migrate()

    # Generate api key
    if not settings_values.api_key:
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

    return


DB_SCHEMA = """
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
    monitored BOOL NOT NULL DEFAULT 0,
    monitor_new_issues BOOL NOT NULL DEFAULT 1,
    root_folder INTEGER NOT NULL,
    folder TEXT,
    custom_folder BOOL NOT NULL DEFAULT 0,
    last_cv_fetch INTEGER(8) DEFAULT 0,
    special_version VARCHAR(255),
    special_version_locked BOOL NOT NULL DEFAULT 0,

    FOREIGN KEY (root_folder) REFERENCES root_folders(id)
);
CREATE TABLE IF NOT EXISTS volumes_covers(
    volume_id INTEGER UNIQUE NOT NULL,
    cover BLOB,
    FOREIGN KEY (volume_id) REFERENCES volumes(id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS volumes_covers_volume_id_index
    ON volumes_covers(volume_id);
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
CREATE INDEX IF NOT EXISTS issues_volume_index
    ON issues(volume_id);
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
CREATE INDEX IF NOT EXISTS issues_files_issue_id_index
    ON issues_files(issue_id);
CREATE TABLE IF NOT EXISTS volume_files(
    file_id INTEGER PRIMARY KEY,
    volume_id INTEGER NOT NULL,
    file_type VARCHAR(15) NOT NULL,

    FOREIGN KEY (volume_id) REFERENCES volumes(id)
        ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES files(id)
        ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS external_download_clients(
    id INTEGER PRIMARY KEY,
    download_type INTEGER NOT NULL,
    client_type VARCHAR(255) NOT NULL,
    title VARCHAR(255) NOT NULL,
    base_url TEXT NOT NULL,
    username VARCHAR(255),
    password VARCHAR(255),
    api_token VARCHAR(255)
);
CREATE TABLE IF NOT EXISTS download_queue(
    id INTEGER PRIMARY KEY,
    volume_id INTEGER NOT NULL,
    client_type VARCHAR(255) NOT NULL,
    external_client_id INTEGER,

    download_link TEXT NOT NULL,
    covered_issues VARCHAR(255),
    force_original_name BOOL,

    source_type VARCHAR(25) NOT NULL,
    source_name VARCHAR(255) NOT NULL,

    web_link TEXT,
    web_title TEXT,
    web_sub_title TEXT,

    FOREIGN KEY (external_client_id) REFERENCES external_download_clients(id),
    FOREIGN KEY (volume_id) REFERENCES volumes(id)
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
    success BOOL,

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
CREATE TABLE IF NOT EXISTS credentials(
    id INTEGER PRIMARY KEY,
    source VARCHAR(30) NOT NULL,
    username TEXT,
    email TEXT,
    password TEXT,
    api_key TEXT
);
CREATE TABLE IF NOT EXISTS remote_mappings(
    id INTEGER PRIMARY KEY,
    external_download_client_id INTEGER NOT NULL,
    remote_path TEXT NOT NULL,
    local_path TEXT NOT NULL,

    FOREIGN KEY (external_download_client_id)
        REFERENCES external_download_clients(id)
        ON DELETE CASCADE
);
"""
