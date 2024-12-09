# -*- coding: utf-8 -*-

"""
Interacting with the database
"""

from os import stat
from typing import Iterable, List, Union

from backend.base.custom_exceptions import FileNotFound
from backend.base.definitions import FileData, GeneralFileData
from backend.base.helpers import first_of_column
from backend.base.logging import LOGGER
from backend.internals.db import get_db


class FilesDB:
    @staticmethod
    def fetch(
        *,
        volume_id: Union[int, None] = None,
        issue_id: Union[int, None] = None,
        file_id: Union[int, None] = None,
        filepath: Union[str, None] = None
    ) -> List[FileData]:

        cursor = get_db()
        if volume_id:
            cursor.execute("""
                SELECT DISTINCT f.id, filepath, size
                FROM files f
                INNER JOIN issues_files if
                INNER JOIN issues i
                ON
                    f.id = if.file_id
                    AND if.issue_id = i.id
                WHERE volume_id = ?
                ORDER BY filepath;
                """,
                (volume_id,)
            )

        elif issue_id:
            cursor.execute("""
                SELECT DISTINCT f.id, filepath, size
                FROM files f
                INNER JOIN issues_files if
                ON f.id = if.file_id
                WHERE if.issue_id = ?
                ORDER BY filepath;
                """,
                (issue_id,)
            )

        elif file_id:
            cursor.execute("""
                SELECT id, filepath, size
                FROM files f
                WHERE f.id = ?
                LIMIT 1;
                """,
                (file_id,)
            )

        elif filepath:
            cursor.execute("""
                SELECT id, filepath, size
                FROM files f
                WHERE f.filepath = ?
                LIMIT 1;
                """,
                (filepath,)
            )

        else:
            cursor.execute("""
                SELECT id, filepath, size
                FROM files
                ORDER BY filepath;
                """
            )

        result: List[FileData] = cursor.fetchalldict() # type: ignore

        if (file_id or filepath) and not result:
            raise FileNotFound

        return result

    @staticmethod
    def volume_of_file(filepath: str) -> Union[int, None]:
        volume_id = get_db().execute("""
            SELECT i.volume_id
            FROM
                files f
                INNER JOIN issues_files if
                INNER JOIN issues i
            ON
                f.id = if.file_id
                AND if.issue_id = i.id
            WHERE f.filepath = ?
            LIMIT 1;
            """,
            (filepath,)
        ).fetchone()

        if not volume_id:
            volume_id = get_db().execute("""
                SELECT vf.volume_id
                FROM
                    files f
                    INNER JOIN volume_files vf
                ON
                    f.id = vf.file_id
                WHERE f.filepath = ?
                LIMIT 1;
                """,
                (filepath,)
            ).fetchone()

        if not volume_id:
            return None
        return volume_id[0]

    @staticmethod
    def issues_covered(filepath: str) -> List[float]:
        return first_of_column(get_db().execute("""
            SELECT DISTINCT
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
            (filepath,)
        ))

    @staticmethod
    def add_file(
        filepath: str
    ) -> int:
        cursor = get_db()
        cursor.execute(
            "INSERT OR IGNORE INTO files(filepath, size) VALUES (?,?)",
            (filepath, stat(filepath).st_size)
        )

        if cursor.rowcount:
            LOGGER.debug(f'Added file to the database: {filepath}')
            return cursor.lastrowid

        return FilesDB.fetch(filepath=filepath)[0]["id"]

    @staticmethod
    def update_filepaths(
        old_filepaths: Iterable[str],
        new_filepaths: Iterable[str]
    ) -> None:
        get_db().executemany(
            "UPDATE files SET filepath = ? WHERE filepath = ?;",
            ((new, old) for old, new in zip(old_filepaths, new_filepaths))
        )
        return

    @staticmethod
    def delete_file(
        file_id: int
    ) -> None:
        get_db().execute(
            "DELETE FROM files WHERE id = ?;",
            (file_id,)
        )
        return

    @staticmethod
    def delete_linked_files(volume_id: int) -> None:
        get_db().execute(
            """
            DELETE FROM files
            WHERE id IN (
                SELECT DISTINCT file_id
                FROM issues_files
                INNER JOIN issues
                ON issues_files.issue_id = issues.id
                WHERE volume_id = ?
            );
            """,
            (volume_id,)
        )
        return

    @staticmethod
    def delete_issue_linked_files(issue_id: int) -> None:
        get_db().execute(
            """
            DELETE FROM files
            WHERE id in (
                SELECT DISTINCT file_id
                FROM issues_files
                WHERE issue_id = ?
            );
            """,
            (issue_id,)
        )

    @staticmethod
    def delete_unmatched_files() -> None:
        get_db().execute("""
            WITH ids AS (
                SELECT file_id
                FROM issues_files
                UNION
                SELECT file_id
                FROM volume_files
            )
            DELETE FROM files
            WHERE id NOT IN ids;
            """
        )
        return


class GeneralFilesDB:
    @staticmethod
    def fetch(volume_id: int) -> List[GeneralFileData]:
        result: List[GeneralFileData] = get_db().execute("""
            SELECT f.id, filepath, size, file_type
            FROM files f
            INNER JOIN volume_files vf
            ON f.id = vf.file_id
            WHERE volume_id = ?;
            """,
            (volume_id,)
        ).fetchalldict() # type: ignore

        return result

    @staticmethod
    def delete_linked_files(volume_id: int) -> None:
        get_db().execute(
            """
            DELETE FROM files
            WHERE id IN (
                SELECT DISTINCT file_id
                FROM volume_files
                WHERE volume_id = ?
            );
            """,
            (volume_id,)
        )
        return
