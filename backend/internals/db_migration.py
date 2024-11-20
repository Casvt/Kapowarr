# -*- coding: utf-8 -*-

from asyncio import run
from typing import Dict, List, Type

from backend.base.definitions import DBMigrator
from backend.base.logging import LOGGER


class VersionMappingContainer:
    version_map: Dict[int, Type[DBMigrator]] = {}


def _load_version_map() -> None:
    if VersionMappingContainer.version_map:
        return

    VersionMappingContainer.version_map = {
        m.start_version: m
        for m in DBMigrator.__subclasses__()
    }
    return


def get_latest_db_version() -> int:
    _load_version_map()
    return max(VersionMappingContainer.version_map) + 1


def migrate_db() -> None:
    """
    Migrate a Kapowarr database from it's current version
    to the newest version supported by the Kapowarr version installed.
    """
    from backend.internals.db import get_db
    from backend.internals.settings import Settings

    s = Settings()
    current_db_version = s['database_version']
    newest_version = get_latest_db_version()
    if current_db_version == newest_version:
        return

    LOGGER.info('Migrating database to newer version...')
    LOGGER.debug(
        "Database migration: %d -> %d",
        current_db_version, newest_version
    )

    cursor = get_db()
    for start_version in range(current_db_version, newest_version):
        if start_version not in VersionMappingContainer.version_map:
            continue
        VersionMappingContainer.version_map[start_version]().run()
        s["database_version"] = start_version + 1
        cursor.connection.commit()

    s._fetch_settings()

    return


class MigrateClearDownloadQueue(DBMigrator):
    start_version = 1

    def run(self) -> None:
        # V1 -> V2

        from backend.internals.db import get_db

        get_db().executescript("DELETE FROM download_queue;")
        return


class MigrateUpdateIssuesAndFiles(DBMigrator):
    start_version = 2

    def run(self) -> None:
        # V2 -> V3

        from backend.internals.db import get_db

        get_db().executescript("""
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
        return


class MigrateRemoveUnmatchedFiles(DBMigrator):
    start_version = 3

    def run(self) -> None:
        # V3 -> V4

        from backend.internals.db import get_db

        get_db().execute("""
            DELETE FROM files
            WHERE rowid IN (
                SELECT f.rowid
                FROM files f
                LEFT JOIN issues_files if
                ON f.id = if.file_id
                WHERE if.file_id IS NULL
            );
        """)
        return


class MigrateRecalculateIssueNumber(DBMigrator):
    start_version = 4

    def run(self) -> None:
        # V4 -> V5

        from backend.base.file_extraction import process_issue_number
        from backend.internals.db import get_db

        cursor = get_db()
        iter_cursor = get_db(force_new=True)
        iter_cursor.execute("SELECT id, issue_number FROM issues;")
        for result in iter_cursor:
            calc_issue_number = process_issue_number(result[1])
            cursor.execute(
                "UPDATE issues SET calculated_issue_number = ? WHERE id = ?;",
                (calc_issue_number, result[0])
            )
        return


class MigrateAddCVFetchTime(DBMigrator):
    start_version = 5

    def run(self) -> None:
        # V5 -> V6

        from backend.implementations.comicvine import ComicVine
        from backend.internals.db import get_db

        cursor = get_db()
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
            ('', r['comicvine_id'])
            for r in run(ComicVine().fetch_volumes(volume_ids))
        )
        cursor.executemany(
            "UPDATE volumes SET last_cv_update = ? WHERE comicvine_id = ?;",
            updates
        )

        return


class MigrateAddCustomFolder(DBMigrator):
    start_version = 6

    def run(self) -> None:
        # V6 -> V7

        from backend.internals.db import get_db

        get_db().execute("""
            ALTER TABLE volumes
                ADD custom_folder BOOL NOT NULL DEFAULT 0;
        """)
        return


class MigrateAddSpecialVersion(DBMigrator):
    start_version = 7

    def run(self) -> None:
        # V7 -> V8

        from backend.base.helpers import first_of_column
        from backend.implementations.volumes import determine_special_version
        from backend.internals.db import get_db

        cursor = get_db()
        cursor.execute("""
            ALTER TABLE volumes
                ADD special_version VARCHAR(255);
        """)

        volumes = cursor.execute("""
            SELECT
                v.id,
                v.title,
                v.description,
                i.date AS first_issue_date,
                COUNT(*) AS issue_count
            FROM volumes v
            INNER JOIN issues i
            ON v.id = i.volume_id
            GROUP BY v.id;
        """).fetchall()

        updates = (
            (
                determine_special_version(
                    v["title"],
                    v["description"],
                    v["first_issue_date"],
                    first_of_column(cursor.execute(
                        "SELECT title FROM issues WHERE volume_id = ?",
                        (v["id"],)
                    ))
                ),
                v["id"]
            )
            for v in volumes
        )

        cursor.executemany(
            "UPDATE volumes SET special_version = ? WHERE id = ?;",
            updates
        )
        return


class MigrateUpdateVolumeTable(DBMigrator):
    start_version = 8

    def run(self) -> None:
        # V8 -> V9

        from backend.internals.db import get_db

        get_db().executescript("""
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
        return


class MigrateUpdateManifest(DBMigrator):
    start_version = 9

    def run(self) -> None:
        # V9 -> V10

        from backend.internals.db import get_db
        from backend.internals.settings import update_manifest

        # Nothing is changed in the database
        # It's just that this code needs to run once
        # and the DB migration system does exactly that:
        # run pieces of code once.

        url_base: str = get_db().execute(
            "SELECT value FROM config WHERE key = 'url_base' LIMIT 1;"
        ).fetchone()[0]
        update_manifest(url_base)

        return


class MigrateUpdateSpecialVersion(DBMigrator):
    start_version = 10

    def run(self) -> None:
        # V10 -> V11

        from backend.base.helpers import first_of_column
        from backend.implementations.volumes import determine_special_version
        from backend.internals.db import get_db

        cursor = get_db()
        volumes = cursor.execute("""
            SELECT
                v.id,
                v.title,
                v.description,
                i.date AS first_issue_date,
                COUNT(*) AS issue_count
            FROM volumes v
            INNER JOIN issues i
            ON v.id = i.volume_id
            GROUP BY v.id;
        """).fetchall()

        updates = (
            (
                determine_special_version(
                    v["title"],
                    v["description"],
                    v["first_issue_date"],
                    first_of_column(cursor.execute(
                        "SELECT title FROM issues WHERE volume_id = ?",
                        (v["id"],)
                    ))
                ),
                v["id"]
            )
            for v in volumes
        )

        cursor.executemany(
            "UPDATE volumes SET special_version = ? WHERE id = ?;",
            updates
        )

        return


class MigrateAddTorrentClientToDownloadQueue(DBMigrator):
    start_version = 11

    def run(self) -> None:
        # V11 -> V12

        from backend.internals.db import get_db

        get_db().executescript("""
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
        return


class MigrateUnzipToFormatPreference(DBMigrator):
    start_version = 12

    def run(self) -> None:
        # V12 -> V13

        from backend.internals.db import get_db

        cursor = get_db()
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
        return


class MigrateFolderConversionToOwnSetting(DBMigrator):
    start_version = 13

    def run(self) -> None:
        # V13 -> V14

        from backend.internals.db import get_db

        cursor = get_db()
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
        return


class MigrateServicePreferenceToSetting(DBMigrator):
    start_version = 14

    def run(self) -> None:
        # V14 -> V15

        from backend.internals.db import get_db

        cursor = get_db()
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
        return


class MigrateUpdateBlocklistTable(DBMigrator):
    start_version = 15

    def run(self) -> None:
        # V15 -> V16

        from backend.internals.db import get_db

        get_db().executescript("""
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
        return


class MigrateLogLevelToInt(DBMigrator):
    start_version = 16

    def run(self) -> None:
        # V16 -> V17

        from backend.internals.settings import Settings

        s = Settings()
        log_number = 20 if s.sv.log_level == 'info' else 10
        s["log_level"] = log_number

        return


class MigrateAddSpecialVersionLock(DBMigrator):
    start_version = 17

    def run(self) -> None:
        # V17 -> V18

        from backend.internals.db import get_db

        get_db().execute("""
            ALTER TABLE volumes ADD
                special_version_locked BOOL NOT NULL DEFAULT 0
        """)
        return


class MigrateTPBNamingToSpecialVersionNaming(DBMigrator):
    start_version = 18

    def run(self) -> None:
        # V18 -> V19

        from re import IGNORECASE, compile

        from backend.internals.db import get_db

        cursor = get_db()

        format: str = cursor.execute(
            "SELECT value FROM config WHERE key = 'file_naming_tpb' LIMIT 1;"
        ).fetchone()[0]

        cursor.execute(
            "DELETE FROM config WHERE key = 'file_naming_tpb';"
        )

        tpb_replacer = compile(
            r'\b(tpb|trade[\s\.\-]?paper[\s\.\-]?back)\b',
            IGNORECASE
        )
        format = tpb_replacer.sub('{special_version}', format)

        cursor.execute(
            "UPDATE config SET value = ? WHERE key = 'file_naming_special_version';",
            (format,))

        return


class MigrateAddWeTransferToPreference(DBMigrator):
    start_version = 19

    def run(self) -> None:
        # V19 -> V20

        from backend.internals.db import get_db
        from backend.internals.settings import Settings

        service_preference = Settings().sv.service_preference
        service_preference.append("wetransfer")
        get_db().execute(
            "UPDATE config SET value = ? WHERE key = 'service_preference';",
            (service_preference,)
        )
        return


class MigrateClearUnsupportedSourceBlocklistEntries(DBMigrator):
    start_version = 20

    def run(self) -> None:
        # V20 -> V21

        from backend.base.definitions import BlocklistReasonID
        from backend.internals.db import get_db
        get_db().execute(
            "DELETE FROM blocklist WHERE reason = ?;",
            (BlocklistReasonID.SOURCE_NOT_SUPPORTED.value,)
        )
        return


class MigrateAddPixelDrainToPreference(DBMigrator):
    start_version = 21

    def run(self) -> None:
        # V21 -> V22

        from backend.internals.db import get_db
        from backend.internals.settings import Settings

        service_preference = Settings().sv.service_preference
        service_preference.append("pixeldrain")
        get_db().execute(
            "UPDATE config SET value = ? WHERE key = 'service_preference';",
            (service_preference,)
        )

        return


class MigrateAddLinksInDownloadQueue(DBMigrator):
    start_version = 22

    def run(self) -> None:
        # V22 -> V23

        from backend.internals.db import get_db

        get_db().executescript("""
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
        return


class MigrateServicePreferenceToEnumValues(DBMigrator):
    start_version = 23

    def run(self) -> None:
        # V23 -> V24

        from backend.base.definitions import GCDownloadSource
        from backend.base.helpers import CommaList
        from backend.internals.db import get_db
        from backend.internals.settings import Settings

        source_string_to_enum = {
            'mega': GCDownloadSource.MEGA.value,
            'mediafire': GCDownloadSource.MEDIAFIRE.value,
            'wetransfer': GCDownloadSource.WETRANSFER.value,
            'pixeldrain': GCDownloadSource.PIXELDRAIN.value,
            'getcomics': GCDownloadSource.GETCOMICS.value,
            'getcomics (torrent)': GCDownloadSource.GETCOMICS_TORRENT.value
        }

        new_service_preference = CommaList((
            source_string_to_enum[service.lower()]
            for service in Settings().sv.service_preference
        ))

        get_db().execute(
            "UPDATE config SET value = ? WHERE key = 'service_preference';",
            (new_service_preference,)
        )

        return


class MigrateAddLinksInBlocklist(DBMigrator):
    start_version = 24

    def run(self) -> None:
        # V24 -> V25

        from backend.internals.db import get_db

        get_db().executescript("""
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
        return


class MigrateAddLinksInHistory(DBMigrator):
    start_version = 25

    def run(self) -> None:
        # V25 -> V26

        from backend.internals.db import get_db

        get_db().executescript("""
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
        return


class MigrateAddForeignKeysToHistoryAndBlocklist(DBMigrator):
    start_version = 26

    def run(self) -> None:
        # V26 -> V27

        from backend.internals.db import get_db

        get_db().executescript("""
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


class MigrateAddSiteURLToVolumes(DBMigrator):
    start_version = 27

    def run(self) -> None:
        # V27 -> V28

        from backend.internals.db import get_db

        get_db().execute("""
            ALTER TABLE volumes ADD
                site_url TEXT NOT NULL DEFAULT "";
        """)
        return


class MigrateAddAltTitleToVolumes(DBMigrator):
    start_version = 28

    def run(self) -> None:
        # V28 -> V29

        from backend.internals.db import get_db

        get_db().execute("""
            ALTER TABLE volumes ADD
                alt_title VARCHAR(255);
        """)
        return


class MigrateNoneToStringFlareSolverr(DBMigrator):
    start_version = 29

    def run(self) -> None:
        # V29 -> V30

        from backend.internals.db import get_db

        cursor = get_db()
        value = cursor.execute("""
            SELECT value
            FROM config
            WHERE key = 'flaresolverr_base_url'
            LIMIT 1;
            """
        ).fetchone()['value']

        if not value:
            cursor.execute("""
                UPDATE config
                SET value = ''
                WHERE key = 'flaresolverr_base_url';
            """)
        return


class MigrateRemoveUnusedSettings(DBMigrator):
    start_version = 30

    def run(self) -> None:
        # V30 -> V31

        from backend.internals.db import get_db
        from backend.internals.settings import SettingsValues

        cursor = get_db()
        cursor.execute("SELECT key FROM config")
        delete_keys = [
            key
            for key in cursor
            if key[0] not in SettingsValues.__dataclass_fields__
        ]
        cursor.executemany(
            "DELETE FROM config WHERE key = ?;",
            delete_keys
        )
        return
