# -*- coding: utf-8 -*-

from asyncio import run
from functools import reduce
from os.path import basename, dirname, splitext
from typing import Dict, List, Set, Union

from backend.base.definitions import ExtendedIssueFileMetadata, FileConstants
from backend.base.helpers import PortablePool
from backend.base.logging import LOGGER
from backend.implementations.comicvine import ComicVine
from backend.implementations.metadata_formats import (
    export_issue_metadata, get_issue_metadata_contents)
from backend.implementations.volumes import Volume
from backend.internals.settings import Settings


def export_issues_metadata(
    volume_id: int,
    force: bool,
    filepath_filter: Union[List[str], None] = None
) -> None:
    """Export the metadata for issues of a volume.

    Args:
        volume_id (int): The ID of the volume to export for.
        force (bool): Whether to _not_ skip files that already have a metadata
            file.
        filepath_filter (Union[List[str], None], optional): Only process files
            that are in the list.
            Defaults to None.
    """
    filepath_filter_set = set(filepath_filter or [])
    volume = Volume(volume_id)
    issues = {i.id: i for i in volume.get_issues()}

    # Build mapping from (filtered) files to the issues they cover
    files_to_issues: Dict[str, Set[int]] = {}
    for issue in issues.values():
        for file_data in issue.files:
            filepath = file_data["filepath"]

            if (
                basename(filepath) in FileConstants.METADATA_FILES
                or (filepath_filter_set and filepath not in filepath_filter_set)
            ):
                continue

            if filepath.endswith(FileConstants.IMAGE_EXTENSIONS):
                filepath = dirname(filepath)

            elif splitext(filepath)[1].lower() not in (
                ".zip", ".cbz", ".rar", ".cbr",
            ):
                continue

            files_to_issues.setdefault(filepath, set()).add(issue.id)

    settings = Settings().sv
    if not force:
        # Filter out files that already have metadata
        files_to_issues = {
            file: issues
            for file, issues in files_to_issues.items()
            if not (
                any(
                    key in ExtendedIssueFileMetadata.__annotations__
                    and value is not None
                    for key, value in (
                        get_issue_metadata_contents(file) or {}
                    ).items()
                )
                if settings.export_extended_metadata else
                get_issue_metadata_contents(file) is not None
            )
        }

    # Export metadata for each file
    LOGGER.debug(f"Exporting metadata for files: {list(files_to_issues)}")
    if not files_to_issues:
        return

    extended_issue_datas = {}
    if settings.export_extended_metadata:
        extended_issue_datas = run(ComicVine().fetch_extended_metadata_issues(
            tuple(map(
                lambda i: issues[i].comicvine_id,
                reduce(lambda s1, s2: s1.union(s2), files_to_issues.values())
            ))
        ))

    volume_data = volume.get_data()
    with PortablePool(max_processes=len(files_to_issues)) as pool:
        pool.starmap(
            export_issue_metadata,
            (
                (
                    file,
                    volume_data,
                    [issues[issue_id] for issue_id in issue_ids],
                    extended_issue_datas
                )
                for file, issue_ids in files_to_issues.items()
            )
        )

    return
