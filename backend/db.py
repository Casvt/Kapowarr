# -*- coding: utf-8 -*-

"""
Setting up the database and handling connections
"""

from os.path import dirname, exists, isdir, join
from sqlite3 import (PARSE_DECLTYPES, Connection, Cursor, ProgrammingError,
                     Row, register_adapter, register_converter)
from threading import current_thread
from time import time
from typing import Any, Dict, List, Tuple, Type, Union, no_type_check

from flask import g

from backend.helpers import CommaList, DB_ThreadSafeSingleton
from backend.logging import LOGGER, set_log_level

__DATABASE_FOLDER__ = "db",
__DATABASE_NAME__ = "Kapowarr.db"
__DATABASE_VERSION__ = 27
__DATABASE_TIMEOUT__ = 10.0


class NoNoneCursor(Cursor):
    """
    `Cursor` but `lastrowid` typehinting is overwritten to remove `None`.
    The `lastrowid` property is only called when we know that we'll get
    an `int`, so remove the `None` possibility to fix loads of type hinting
    problems.
    """

    @property
    def lastrowid(self) -> int:
        return super().lastrowid or 1


class BaseConnection(Connection):
    file = ''

    def __init__(self, timeout: float) -> None:
        """Create a connection with a database

        Args:
            timeout (float): How long to wait before giving up on a command
        """
        super().__init__(
            self.file,
            timeout=timeout,
            detect_types=PARSE_DECLTYPES
        )
        super().cursor().execute("PRAGMA foreign_keys = ON;")
        self.closed = False
        return

    def cursor(self) -> NoNoneCursor: # type: ignore
        return super().cursor() # type: ignore

    def close(self) -> None:
        """Close the database connection"""
        self.closed = True
        super().close()
        return

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}; {current_thread().name}; {id(self)}>'


class DBConnection(BaseConnection, metaclass=DB_ThreadSafeSingleton):
    "For creating a connection with a database"

    def __init__(self, timeout: float) -> None:
        LOGGER.debug(f'Creating connection {self}')
        super().__init__(timeout)
        return

    def close(self) -> None:
        """Close the connection
        """
        LOGGER.debug(f'Closing connection {self}')
        super().close()
        return


class TempDBConnection(BaseConnection):
    """For creating a temporary connection with a database.
    The user needs to manually commit and close.
    """

    def __init__(self, timeout: float) -> None:
        """Create a temporary connection with a database

        Args:
            timeout (float): How long to wait before giving up on a command
        """
        LOGGER.debug(f'Creating temporary connection {self}')
        super().__init__(timeout)
        return

    def close(self) -> None:
        """Close the temporary connection
        """
        LOGGER.debug(f'Closing temporary connection {self}')
        super().close()
        return


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
    from backend.files import create_folder, folder_path
    from backend.settings import about_data

    if db_folder:
        if exists(db_folder) and not isdir(db_folder):
            raise ValueError

    db_file_location = join(
        db_folder or folder_path(*__DATABASE_FOLDER__),
        __DATABASE_NAME__
    )

    LOGGER.debug(f'Setting database location: {db_file_location}')

    create_folder(dirname(db_file_location))

    BaseConnection.file = about_data['database_location'] = db_file_location

    return


db_output_mapping: Dict[type, Any] = {
    dict: Row,
    tuple: None
}


def get_db(
    output_type: Union[Type[Dict[Any, Any]], Type[Tuple[Any]]] = tuple,
    temp: bool = False
) -> NoNoneCursor:
    """
    Get a database cursor instance or create a new one if needed

    Args:
        output_type (Union[type[dict], type[tuple]], optional):
        The type of output of the cursor.
            Defaults to tuple.

        temp (bool, optional): Decides if a new manually handled cursor is
        returned instead of the cached one.
            Defaults to False.

    Returns:
        NoAnyCursor: Database cursor instance with desired output type set.
    """
    if temp:
        cursor = TempDBConnection(timeout=__DATABASE_TIMEOUT__).cursor()
    else:
        try:
            cursor: NoNoneCursor = g.cursor
        except AttributeError:
            db = DBConnection(timeout=__DATABASE_TIMEOUT__)
            cursor = g.cursor = db.cursor()

    cursor.row_factory = db_output_mapping[output_type]

    return cursor


def close_db(e: Union[None, BaseException] = None):
    """Close database cursor, commit database and close database.

    Args:
        e (Union[None, BaseException], optional): Error. Defaults to None.
    """
    try:
        cursor = g.cursor
        db: DBConnection = cursor.connection
        cursor.close()
        delattr(g, 'cursor')
        db.commit()
        if not current_thread().name.startswith('waitress-'):
            db.close()
    except (AttributeError, ProgrammingError):
        pass

    return


def close_all_db() -> None:
    "Close all non-temporary database connections that are still open"
    LOGGER.debug('Closing any open database connections')
    for i in DB_ThreadSafeSingleton._instances.values():
        if not i.closed:
            i.close()
    c = DBConnection(timeout=20.0)
    c.commit()
    c.close()
    return


@no_type_check
def migrate_db(current_db_version: int) -> None:
    """
    Migrate a Kapowarr database from it's current version
    to the newest version supported by the Kapowarr version installed.
    """
    from backend.settings import Settings
    LOGGER.info('Migrating database to newer version...')
    s = Settings()
    cursor = get_db()
    if current_db_version == 1:
        # V1 -> V2
        cursor.executescript("DELETE FROM download_queue;")

        current_db_version = s['database_version'] = 2
        s._save_to_database()

    if current_db_version == 2:
        # V2 -> V3
        cursor.executescript("""
            BEGIN TRANSACTION;
            PRAGMA defer_foreign_keys = ON;

            -- Issues
            CREATE TEMPORARY TABLE temp_issues_3 AS
                SELECT * FROM issues;
            DROP TABLE issues;

            CREATE TABLE issues(
                id INTEGER PRIMARY KEY,
                volume_id INTEGER NOT NULL,
                comicvine_id INTEGER NOT NULL,
                issue_number VARCHAR(20) NOT NULL,
                calculated_issue_number FLOAT(20) NOT NULL,
                title VARCHAR(255),
                date VARCHAR(10),
                description TEXT,
                monitored BOOL NOT NULL DEFAULT 1,

                FOREIGN KEY (volume_id) REFERENCES volumes(id)
                    ON DELETE CASCADE
            );
            INSERT INTO issues
                SELECT * FROM temp_issues_3;

            -- Issues files
            CREATE TEMPORARY TABLE temp_issues_files_3 AS
                SELECT * FROM issues_files;
            DROP TABLE issues_files;

            CREATE TABLE issues_files(
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
            INSERT INTO issues_files
                SELECT * FROM temp_issues_files_3;

            COMMIT;
        """)

        current_db_version = s['database_version'] = 3
        s._save_to_database()

    if current_db_version == 3:
        # V3 -> V4

        cursor.execute("""
            DELETE FROM files
            WHERE rowid IN (
                SELECT f.rowid
                FROM files f
                LEFT JOIN issues_files if
                ON f.id = if.file_id
                WHERE if.file_id IS NULL
            );
        """)

        current_db_version = s['database_version'] = 4
        s._save_to_database()

    if current_db_version == 4:
        # V4 -> V5
        from backend.file_extraction import process_issue_number

        cursor2 = get_db(temp=True)
        for result in cursor2.execute("SELECT id, issue_number FROM issues;"):
            calc_issue_number = process_issue_number(result[1])
            cursor.execute(
                "UPDATE issues SET calculated_issue_number = ? WHERE id = ?;",
                (calc_issue_number, result[0])
            )
        cursor2.connection.close()

        current_db_version = s['database_version'] = 5
        s._save_to_database()

    if current_db_version == 5:
        # V5 -> V6
        from backend.comicvine import ComicVine

        cursor.executescript("""
            BEGIN TRANSACTION;
            PRAGMA defer_foreign_keys = ON;

            -- Issues
            CREATE TEMPORARY TABLE temp_issues_6 AS
                SELECT * FROM issues;
            DROP TABLE issues;

            CREATE TABLE IF NOT EXISTS issues(
                id INTEGER PRIMARY KEY,
                volume_id INTEGER NOT NULL,
                comicvine_id INTEGER UNIQUE NOT NULL,
                issue_number VARCHAR(20) NOT NULL,
                calculated_issue_number FLOAT(20) NOT NULL,
                title VARCHAR(255),
                date VARCHAR(10),
                description TEXT,
                monitored BOOL NOT NULL DEFAULT 1,

                FOREIGN KEY (volume_id) REFERENCES volumes(id)
                    ON DELETE CASCADE
            );
            INSERT INTO issues
                SELECT * FROM temp_issues_6;

            -- Volumes
            ALTER TABLE volumes
                ADD last_cv_update VARCHAR(255);
            ALTER TABLE volumes
                ADD last_cv_fetch INTEGER(8) DEFAULT 0;

            COMMIT;
        """)

        volume_ids = [
            str(v[0])
            for v in cursor.execute("SELECT comicvine_id FROM volumes;")
        ]
        updates = (
            (r['date_last_updated'], r['comicvine_id'])
            for r in ComicVine().fetch_volumes_async(volume_ids)
        )
        cursor.executemany(
            "UPDATE volumes SET last_cv_update = ? WHERE comicvine_id = ?;",
            updates
        )

        current_db_version = s['database_version'] = 6
        s._save_to_database()

    if current_db_version == 6:
        # V6 -> V7
        cursor.execute("""
            ALTER TABLE volumes
                ADD custom_folder BOOL NOT NULL DEFAULT 0;
        """)

        current_db_version = s['database_version'] = 7
        s._save_to_database()

    if current_db_version == 7:
        # V7 -> V8
        from backend.volumes import determine_special_version

        cursor.execute("""
            ALTER TABLE volumes
                ADD special_version VARCHAR(255);
        """)

        volumes = cursor.execute("""
            SELECT
                v.id,
                v.title,
                v.description,
                COUNT(*) AS issue_count,
                i.title AS first_issue_title
            FROM volumes v
            INNER JOIN issues i
            ON v.id = i.volume_id
            GROUP BY v.id;
        """).fetchall()

        updates = (
            (determine_special_version(v[1], v[2], v[3], v[4]), v[0])
            for v in volumes
        )

        cursor.executemany(
            "UPDATE volumes SET special_version = ? WHERE id = ?;",
            updates
        )

        current_db_version = s['database_version'] = 8
        s._save_to_database()

    if current_db_version == 8:
        # V8 -> V9
        cursor.executescript("""
            PRAGMA foreign_keys = OFF;

            CREATE TABLE new_volumes(
                id INTEGER PRIMARY KEY,
                comicvine_id INTEGER NOT NULL,
                title VARCHAR(255) NOT NULL,
                year INTEGER(5),
                publisher VARCHAR(255),
                volume_number INTEGER(8) DEFAULT 1,
                description TEXT,
                cover BLOB,
                monitored BOOL NOT NULL DEFAULT 0,
                root_folder INTEGER NOT NULL,
                folder TEXT,
                custom_folder BOOL NOT NULL DEFAULT 0,
                last_cv_fetch INTEGER(8) DEFAULT 0,
                special_version VARCHAR(255),

                FOREIGN KEY (root_folder) REFERENCES root_folders(id)
            );

            INSERT INTO new_volumes
                SELECT
                    id, comicvine_id, title, year, publisher,
                    volume_number, description, cover, monitored,
                    root_folder, folder, custom_folder,
                    0 AS last_cv_fetch, special_version
                FROM volumes;

            DROP TABLE volumes;

            ALTER TABLE new_volumes RENAME TO volumes;

            PRAGMA foreign_keys = ON;
        """)

        current_db_version = s['database_version'] = 9
        s._save_to_database()

    if current_db_version == 9:
        # V9 -> V10

        # Nothing is changed in the database
        # It's just that this code needs to run once
        # and the DB migration system does exactly that:
        # run pieces of code once.
        from backend.settings import update_manifest

        url_base: str = cursor.execute(
            "SELECT value FROM config WHERE key = 'url_base' LIMIT 1;"
        ).fetchone()[0]
        update_manifest(url_base)

        current_db_version = s['database_version'] = 10
        s._save_to_database()

    if current_db_version == 10:
        # V10 -> V11
        from backend.volumes import determine_special_version

        volumes = cursor.execute("""
            SELECT
                id, title,
                description
            FROM volumes;
            """
        ).fetchall()

        updates = []
        for volume in volumes:
            issue_titles = [
                i[0] for i in cursor.execute(
                    "SELECT title FROM issues WHERE volume_id = ?;",
                    (volume[0],)
                )
            ]
            updates.append(
                (determine_special_version(volume[1], volume[2], issue_titles),
                 volume[0])
            )

        cursor.executemany(
            "UPDATE volumes SET special_version = ? WHERE id = ?;",
            updates
        )

        current_db_version = s['database_version'] = 11
        s._save_to_database()

    if current_db_version == 11:
        # V11 -> V12
        cursor.executescript("""
            DROP TABLE download_queue;

            CREATE TABLE download_queue(
                id INTEGER PRIMARY KEY,
                client_type VARCHAR(255) NOT NULL,
                torrent_client_id INTEGER,

                link TEXT NOT NULL,
                filename_body TEXT NOT NULL,
                source VARCHAR(25) NOT NULL,

                volume_id INTEGER NOT NULL,
                issue_id INTEGER,
                page_link TEXT,

                FOREIGN KEY (torrent_client_id) REFERENCES torrent_clients(id),
                FOREIGN KEY (volume_id) REFERENCES volumes(id),
                FOREIGN KEY (issue_id) REFERENCES issues(id)
            );
        """)

        current_db_version = s['database_version'] = 12
        s._save_to_database()

    if current_db_version == 12:
        # V12 -> V13
        unzip = cursor.execute(
            "SELECT value FROM config WHERE key = 'unzip' LIMIT 1;"
        ).fetchone()[0]

        cursor.execute(
            "DELETE FROM config WHERE key = 'unzip';"
        )

        if unzip:
            cursor.executescript("""
                UPDATE config
                SET value = 'folder'
                WHERE key = 'format_preference';

                UPDATE config
                SET value = 1
                WHERE key = 'convert';
                """
            )

        current_db_version = s['database_version'] = 13
        s._save_to_database()

    if current_db_version == 13:
        # V13 -> V14
        format_preference: List[str] = cursor.execute("""
            SELECT value
            FROM config
            WHERE key = 'format_preference'
            LIMIT 1;
        """).fetchone()[0].split(',')

        if 'folder' in format_preference:
            cursor.execute("""
                UPDATE config
                SET value = 1
                WHERE key = 'extract_issue_ranges';
                """
            )
            format_preference.remove('folder')
            cursor.execute("""
                UPDATE config
                SET value = ?
                WHERE key = 'format_preference';
                """,
                (",".join(format_preference),)
            )

        current_db_version = s['database_version'] = 14
        s._save_to_database()

    if current_db_version == 14:
        # V14 -> V15
        service_preference = ','.join([
            source[0] for source in cursor.execute(
                "SELECT source FROM service_preference ORDER BY pref;"
            )
        ])

        # UPDATE, not INSERT,
        # because first default settings are entered and only then is the db
        # migration done, so the key will already exist.
        cursor.execute(
            "UPDATE config SET value = ? WHERE key = 'service_preference';",
            (service_preference,)
        )
        cursor.execute(
            "DROP TABLE service_preference;"
        )

        current_db_version = s['database_version'] = 15
        s._save_to_database()
        s._load_from_db()

    if current_db_version == 15:
        # V15 -> V16

        cursor.executescript("""
            BEGIN TRANSACTION;
            PRAGMA defer_foreign_keys = ON;

            DROP TABLE blocklist_reasons;

            CREATE TEMPORARY TABLE temp_blocklist_16 AS
                SELECT * FROM blocklist;
            DROP TABLE blocklist;

            CREATE TABLE blocklist(
                id INTEGER PRIMARY KEY,
                link TEXT NOT NULL UNIQUE,
                reason INTEGER NOT NULL CHECK (reason > 0),
                added_at INTEGER NOT NULL
            );
            INSERT INTO blocklist
                SELECT * FROM temp_blocklist_16;

            COMMIT;
        """)

        current_db_version = s['database_version'] = 16
        s._save_to_database()

    if current_db_version == 16:
        # V16 -> V17

        log_number = 20 if s['log_level'] == 'info' else 10
        s['log_level'] = log_number

        current_db_version = s['database_version'] = 17
        s._save_to_database()

    if current_db_version == 17:
        # V17 -> V18

        cursor.execute("""
            ALTER TABLE volumes ADD
                special_version_locked BOOL NOT NULL DEFAULT 0
        """)

        current_db_version = s['database_version'] = current_db_version + 1
        s._save_to_database()

    if current_db_version == 18:
        # V18 -> V19

        from re import IGNORECASE, compile

        format: str = cursor.execute(
            "SELECT value FROM config WHERE key = 'file_naming_tpb' LIMIT 1;"
        ).fetchone()[0]
        cursor.execute("DELETE FROM config WHERE key = 'file_naming_tpb';")

        tpb_replacer = compile(
            r'\b(tpb|trade[\s\.\-]?paper[\s\.\-]?back)\b',
            IGNORECASE
        )
        format = tpb_replacer.sub('{special_version}', format)

        cursor.execute(
            "UPDATE config SET value = ? WHERE key = 'file_naming_special_version';",
            (format,))

        current_db_version = s['database_version'] = current_db_version + 1
        s._save_to_database()

    if current_db_version == 19:
        # V19 -> V20

        service_preference: CommaList = s["service_preference"]
        service_preference.append("wetransfer")
        cursor.execute(
            "UPDATE config SET value = ? WHERE key = 'service_preference';",
            (service_preference,)
        )

        current_db_version = s['database_version'] = current_db_version + 1
        s._save_to_database()
        s._load_from_db()

    if current_db_version == 20:
        # V20 -> V21

        from backend.enums import BlocklistReasonID
        cursor.execute(
            "DELETE FROM blocklist WHERE reason = ?;",
            (BlocklistReasonID.SOURCE_NOT_SUPPORTED.value,)
        )

        current_db_version = s['database_version'] = current_db_version + 1
        s._save_to_database()

    if current_db_version == 21:
        # V21 -> V22

        service_preference: CommaList = s["service_preference"]
        service_preference.append("pixeldrain")
        cursor.execute(
            "UPDATE config SET value = ? WHERE key = 'service_preference';",
            (service_preference,)
        )

        current_db_version = s['database_version'] = current_db_version + 1
        s._save_to_database()
        s._load_from_db()

    if current_db_version == 22:
        # V22 -> V23

        cursor.executescript("""
            DROP TABLE download_queue;
            CREATE TABLE download_queue(
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
        """)

        current_db_version = s['database_version'] = current_db_version + 1
        s._save_to_database()

    if current_db_version == 23:
        # V23 -> V24

        from backend.enums import GCDownloadSource
        source_string_to_enum = {
            'mega': GCDownloadSource.MEGA.value,
            'mediafire': GCDownloadSource.MEDIAFIRE.value,
            'wetransfer': GCDownloadSource.WETRANSFER.value,
            'pixeldrain': GCDownloadSource.PIXELDRAIN.value,
            'getcomics': GCDownloadSource.GETCOMICS.value,
            'getcomics (torrent)': GCDownloadSource.GETCOMICS_TORRENT.value
        }

        new_service_preference = CommaList((
            source_string_to_enum[service]
            for service in s['service_preference']
        ))

        cursor.execute(
            "UPDATE config SET value = ? WHERE key = 'service_preference';",
            (new_service_preference,)
        )

        current_db_version = s['database_version'] = current_db_version + 1
        s._save_to_database()
        s._load_from_db()

    if current_db_version == 24:
        # V24 -> V25

        cursor.executescript("""
            BEGIN TRANSACTION;
            PRAGMA defer_foreign_keys = ON;

            CREATE TEMPORARY TABLE temp_blocklist_25 AS
                SELECT * FROM blocklist;
            DROP TABLE blocklist;

            CREATE TABLE blocklist(
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

                FOREIGN KEY (volume_id) REFERENCES volumes(id),
                FOREIGN KEY (issue_id) REFERENCES issues(id)
            );

            INSERT INTO blocklist
                SELECT
                    id,
                    NULL AS volume_id,
                    NULL AS issue_id,
                    NULL AS web_link,
                    NULL AS web_title,
                    NULL AS web_sub_title,
                    link AS download_link,
                    NULL AS source,
                    reason,
                    added_at
                FROM temp_blocklist_25
                WHERE link LIKE 'https://getcomics.org/dlds%';

            INSERT INTO blocklist
                SELECT
                    id,
                    NULL AS volume_id,
                    NULL AS issue_id,
                    link AS web_link,
                    NULL AS web_title,
                    NULL AS web_sub_title,
                    NULL AS download_link,
                    NULL AS source,
                    reason,
                    added_at
                FROM temp_blocklist_25
                WHERE NOT link LIKE 'https://getcomics.org/dlds%';

            COMMIT;
        """)

        current_db_version = s['database_version'] = current_db_version + 1
        s._save_to_database()

    if current_db_version == 25:
        # V25 -> V26

        cursor.executescript("""
            BEGIN TRANSACTION;
            PRAGMA defer_foreign_keys = ON;

            CREATE TEMPORARY TABLE temp_download_history_26 AS
                SELECT * FROM download_history;
            DROP TABLE download_history;

            CREATE TABLE download_history(
                web_link TEXT,
                web_title TEXT,
                web_sub_title TEXT,
                file_title TEXT,

                volume_id INTEGER,
                issue_id INTEGER,

                source VARCHAR(25),
                downloaded_at INTEGER NOT NULL CHECK (downloaded_at > 0),

                FOREIGN KEY (volume_id) REFERENCES volumes(id),
                FOREIGN KEY (issue_id) REFERENCES issues(id)
            );

            INSERT INTO download_history
                SELECT
                    original_link AS web_link,
                    title AS web_title,
                    NULL AS web_sub_title,
                    NULL AS file_title,
                    NULL AS volume_id,
                    NULL AS issue_id,
                    NULL AS source,
                    downloaded_at
                FROM temp_download_history_26;

            COMMIT;
        """)

        current_db_version = s['database_version'] = current_db_version + 1
        s._save_to_database()

    if current_db_version == 26:
        # V26 -> V27

        cursor.executescript("""
            BEGIN TRANSACTION;
            PRAGMA defer_foreign_keys = ON;

            CREATE TEMPORARY TABLE temp_download_history_27 AS
                SELECT * FROM download_history;
            DROP TABLE download_history;

            CREATE TABLE download_history(
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

            INSERT INTO download_history
                SELECT *
                FROM temp_download_history_27;

            CREATE TEMPORARY TABLE temp_blocklist_27 AS
                SELECT * FROM blocklist;
            DROP TABLE blocklist;

            CREATE TABLE blocklist(
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

            INSERT INTO blocklist
                SELECT *
                FROM temp_blocklist_27;

            COMMIT;
        """)

    return


def setup_db() -> None:
    """
    Setup the database tables and default config when they aren't setup yet
    """
    from backend.settings import Settings, credential_sources, task_intervals

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
            year INTEGER(5),
            publisher VARCHAR(255),
            volume_number INTEGER(8) DEFAULT 1,
            description TEXT,
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

    # Migrate database if needed
    current_db_version = settings['database_version']

    if current_db_version < __DATABASE_VERSION__:
        LOGGER.debug(
            f'Database migration: {current_db_version} -> {__DATABASE_VERSION__}'
        )
        migrate_db(current_db_version)
        # Redundant but just to be sure, in case
        # the version isn't updated in the last migration of the function
        settings['database_version'] = __DATABASE_VERSION__
        settings._save_to_database()

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
