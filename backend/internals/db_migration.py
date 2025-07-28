# -*- coding: utf-8 -*-

from asyncio import run
from functools import lru_cache
from typing import Dict, List, Type

from backend.base.definitions import DBMigrator
from backend.base.helpers import get_subclasses
from backend.base.logging import LOGGER
from backend.internals.db import get_db, iter_commit


@lru_cache(1)
def get_db_migration_map() -> Dict[int, Type[DBMigrator]]:
    """Get a map of the database version to the migrator class for that version
    to one database version higher. E.g. 2 -> Migrate2To3.

    Returns:
        Dict[int, Type[DBMigrator]]: The map.
    """
    return {
        m.start_version: m
        for m in get_subclasses(DBMigrator)
    }


@lru_cache(1)
def get_latest_db_version() -> int:
    """Get the latest database version supported.

    Returns:
        int: The version.
    """
    return max(get_db_migration_map()) + 1


def migrate_db() -> None:
    """
    Migrate a Kapowarr database from it's current version
    to the newest version supported by the Kapowarr version installed.
    """
    from backend.internals.settings import Settings

    s = Settings()
    current_db_version = s["database_version"]
    newest_version = get_latest_db_version()
    if current_db_version == newest_version:
        get_db_migration_map.cache_clear()
        return

    LOGGER.info("Migrating database to newer version...")
    LOGGER.debug(
        "Database migration: %d -> %d",
        current_db_version, newest_version
    )

    db_migration_map = get_db_migration_map()
    for start_version in iter_commit(range(current_db_version, newest_version)):
        if start_version not in db_migration_map:
            continue
        db_migration_map[start_version]().run()
        s["database_version"] = start_version + 1

    get_db().execute("VACUUM;")
    s._fetch_settings()
    get_db_migration_map.cache_clear()

    return


class MigrateClearDownloadQueue(DBMigrator):
    start_version = 1

    def run(self) -> None:
        # V1 -> V2

        get_db().executescript("DELETE FROM download_queue;")
        return


class MigrateUpdateIssuesAndFiles(DBMigrator):
    start_version = 2

    def run(self) -> None:
        # V2 -> V3

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

        from backend.internals.db_models import FilesDB

        FilesDB.delete_unmatched_files()

        return


class MigrateRecalculateIssueNumber(DBMigrator):
    start_version = 4

    def run(self) -> None:
        # V4 -> V5

        from backend.base.file_extraction import process_issue_number

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

        get_db().execute("""
            ALTER TABLE volumes
                ADD custom_folder BOOL NOT NULL DEFAULT 0;
        """)
        return


class MigrateAddSpecialVersion(DBMigrator):
    start_version = 7

    def run(self) -> None:
        # V7 -> V8

        from backend.implementations.volumes import (Library,
                                                     determine_special_version)

        cursor = get_db()
        cursor.execute("""
            ALTER TABLE volumes
                ADD special_version VARCHAR(255);
        """)

        updates = (
            (
                determine_special_version(v_id),
                v_id
            )
            for v_id in Library().get_volumes()
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

        # There used to be a migration here that fixed the manifest file.
        # That has since been replaced by the dynamic endpoint serving the JSON.
        # So the migration doesn't do anything anymore, and a function used
        # doesn't exist anymore, so the whole migration is just removed.

        return


class MigrateUpdateSpecialVersion(DBMigrator):
    start_version = 10

    def run(self) -> None:
        # V10 -> V11

        from backend.implementations.volumes import (Library,
                                                     determine_special_version)

        updates = (
            (
                determine_special_version(v_id),
                v_id
            )
            for v_id in Library().get_volumes()
        )

        get_db().executemany(
            "UPDATE volumes SET special_version = ? WHERE id = ?;",
            updates
        )

        return


class MigrateAddTorrentClientToDownloadQueue(DBMigrator):
    start_version = 11

    def run(self) -> None:
        # V11 -> V12

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

        get_db().execute(
            "DELETE FROM blocklist WHERE reason = ?;",
            (BlocklistReasonID.SOURCE_NOT_SUPPORTED.value,)
        )
        return


class MigrateAddPixelDrainToPreference(DBMigrator):
    start_version = 21

    def run(self) -> None:
        # V21 -> V22

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

        get_db().execute("""
            ALTER TABLE volumes ADD
                site_url TEXT NOT NULL DEFAULT "";
        """)
        return


class MigrateAddAltTitleToVolumes(DBMigrator):
    start_version = 28

    def run(self) -> None:
        # V28 -> V29

        get_db().execute("""
            ALTER TABLE volumes ADD
                alt_title VARCHAR(255);
        """)
        return


class MigrateNoneToStringFlareSolverr(DBMigrator):
    start_version = 29

    def run(self) -> None:
        # V29 -> V30

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

        # This migration would remove unused settings, but one of those was
        # used in migration V31 -> V32, so removing the unused settings was
        # moved to that migration, after using the setting. But because people
        # already ran this migration, their database version already updated to
        # 31, so this migration couldn't be removed.

        return


class MigrateVaiNaming(DBMigrator):
    start_version = 31

    def run(self) -> None:
        # V31 -> V32

        from backend.internals.settings import SettingsValues

        cursor = get_db()

        volume_as_empty = (cursor.execute(
            "SELECT value FROM config WHERE key = 'volume_as_empty' LIMIT 1;"
        ).fetchone() or (None,))[0]
        if volume_as_empty:
            cursor.execute(
                "UPDATE config SET value = ? WHERE key = 'file_naming_vai';",
                ('{series_name} ({year}) Volume {volume_number} Issue {issue_number}',)
            )

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


class MigrateCredentials(DBMigrator):
    start_version = 32

    def run(self) -> None:
        # V32 -> V33

        get_db().executescript("""
            BEGIN TRANSACTION;
            PRAGMA defer_foreign_keys = ON;

            CREATE TEMPORARY TABLE temp_credentials_33 AS
                SELECT * FROM credentials;
            DROP TABLE credentials;

            DROP TABLE credentials_sources;

            CREATE TABLE IF NOT EXISTS credentials(
                id INTEGER PRIMARY KEY,
                source VARCHAR(30) NOT NULL UNIQUE,
                username TEXT,
                email TEXT,
                password TEXT,
                api_key TEXT
            );

            INSERT INTO credentials(id, source, email, password)
                SELECT id, 'mega' AS source, email, password
                FROM temp_credentials_33;

            COMMIT;
        """)

        return


class MigrateExternalDownloadClients(DBMigrator):
    start_version = 33

    def run(self) -> None:
        # V33 -> V34

        get_db().executescript(
            """
            BEGIN TRANSACTION;
            PRAGMA defer_foreign_keys = ON;

            CREATE TEMPORARY TABLE temp_download_queue_34 AS
                SELECT * FROM download_queue;
            DROP TABLE download_queue;

            CREATE TABLE IF NOT EXISTS download_queue(
                id INTEGER PRIMARY KEY,
                client_type VARCHAR(255) NOT NULL,
                external_client_id INTEGER,

                download_link TEXT NOT NULL,
                filename_body TEXT NOT NULL,
                source VARCHAR(25) NOT NULL,

                volume_id INTEGER NOT NULL,
                issue_id INTEGER,
                web_link TEXT,
                web_title TEXT,
                web_sub_title TEXT,

                FOREIGN KEY (external_client_id) REFERENCES external_download_clients(id),
                FOREIGN KEY (volume_id) REFERENCES volumes(id),
                FOREIGN KEY (issue_id) REFERENCES issues(id)
            );

            INSERT INTO download_queue(
                id, client_type, external_client_id,
                download_link, filename_body, source,
                volume_id, issue_id,
                web_link, web_title, web_sub_title
            )
                SELECT
                    id, client_type, torrent_client_id AS external_client_id,
                    download_link, filename_body, source,
                    volume_id, issue_id,
                    web_link, web_title, web_sub_title
                FROM temp_download_queue_34;

            CREATE TEMPORARY TABLE temp_torrent_clients_34 AS
                SELECT * FROM torrent_clients;
            DROP TABLE torrent_clients;

            INSERT INTO external_download_clients(
                id, download_type, client_type, title, base_url,
                username, password, api_token
            )
                SELECT
                    id, 2 AS download_type, type AS client_type, title, base_url,
                    username, password, api_token
                FROM temp_torrent_clients_34;

            COMMIT;
        """)

        return


class MigrateTypeHostingSettings(DBMigrator):
    start_version = 34

    def run(self) -> None:
        # V34 -> V35

        from backend.internals.settings import Settings

        cursor = get_db()
        port = cursor.execute(
            "SELECT value FROM config WHERE key = 'port' LIMIT 1;"
        ).fetchone()[0]

        cursor.execute(
            "UPDATE config SET value=? WHERE key = 'port';",
            (int(port),)
        )

        settings = Settings()
        settings._fetch_settings()
        settings.backup_hosting_settings()
        return


class MigrateDownloadQueueToRefactor(DBMigrator):
    start_version = 35

    def run(self) -> None:
        # V35 -> V36

        get_db().executescript("""
            DROP TABLE download_queue;
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
        """)
        return


class MigrateMultipleCredentials(DBMigrator):
    start_version = 36

    def run(self) -> None:
        # V36 -> V37

        get_db().executescript("""
            BEGIN TRANSACTION;
            PRAGMA defer_foreign_keys = ON;

            CREATE TEMPORARY TABLE temp_credentials_37 AS
                SELECT * FROM credentials;
            DROP TABLE credentials;

            CREATE TABLE IF NOT EXISTS credentials(
                id INTEGER PRIMARY KEY,
                source VARCHAR(30) NOT NULL,
                username TEXT,
                email TEXT,
                password TEXT,
                api_key TEXT
            );

            INSERT INTO credentials
                SELECT * FROM temp_credentials_37;

            COMMIT;
        """)
        return


class MigrateAddMonitorNewIssuesToVolumes(DBMigrator):
    start_version = 37

    def run(self) -> None:
        # V37 -> V38

        get_db().execute("""
            ALTER TABLE volumes ADD COLUMN
                monitor_new_issues BOOL NOT NULL DEFAULT 1;
        """)
        return


class MigrateTorrentTimeoutToDownloadTimeout(DBMigrator):
    start_version = 38

    def run(self) -> None:
        # V38 -> V39

        cursor = get_db()

        old_value = cursor.execute(
            "SELECT value FROM config WHERE key = 'failing_torrent_timeout' LIMIT 1;"
        ).fetchone()[0]

        cursor.execute(
            "UPDATE config SET value = ? WHERE key = 'failing_download_timeout';",
            (old_value,))

        cursor.execute(
            "DELETE FROM config WHERE key = 'failing_torrent_timeout';"
        )

        return


class MigrateDeleteCompletedTorrentsToDownloads(DBMigrator):
    start_version = 39

    def run(self) -> None:
        # V39 -> V40

        cursor = get_db()

        old_value = cursor.execute(
            "SELECT value FROM config WHERE key = 'delete_completed_torrents' LIMIT 1;"
        ).fetchone()[0]

        cursor.execute(
            "UPDATE config SET value = ? WHERE key = 'delete_completed_downloads';",
            (old_value,))

        cursor.execute(
            "DELETE FROM config WHERE key = 'delete_completed_torrents';"
        )

        return


class MigrateHashPassword(DBMigrator):
    start_version = 40

    def run(self) -> None:
        # V40 -> V41

        from backend.internals.settings import Settings

        s = Settings()
        settings = s.get_settings()

        if settings.auth_password:
            s.update({"auth_password": settings.auth_password})

        return


class MigrateAddSuccessToDownloadHistory(DBMigrator):
    start_version = 41

    def run(self) -> None:
        # V41 -> V42

        get_db().execute("""
            ALTER TABLE download_history ADD COLUMN
                success BOOL;
        """)

        return


class MigrateSeperateCoversTable(DBMigrator):
    start_version = 42

    def run(self) -> None:
        # V42 -> V43

        cursor = get_db()

        cursor.executescript("""
            PRAGMA foreign_keys = OFF;
            BEGIN TRANSACTION;

            INSERT OR IGNORE INTO volumes_covers(volume_id, cover)
                SELECT id, cover
                FROM volumes;

            CREATE TEMPORARY TABLE temp_volumes_43 AS SELECT
                id,
                comicvine_id,
                title,
                alt_title,
                year,
                publisher,
                volume_number,
                description,
                site_url,
                monitored,
                monitor_new_issues,
                root_folder,
                folder,
                custom_folder,
                last_cv_fetch,
                special_version,
                special_version_locked
            FROM volumes;
            DROP TABLE volumes;

            CREATE TABLE volumes(
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

            INSERT INTO volumes
                SELECT *
                FROM temp_volumes_43;

            COMMIT;
            PRAGMA foreign_keys = ON;
        """)

        return
