# -*- coding: utf-8 -*-

from asyncio import run
from functools import reduce
from os.path import basename, dirname
from typing import Dict, List, Set, Union

from backend.base.definitions import ExtendedIssueFileMetadata, FileConstants
from backend.base.helpers import PortablePool
from backend.base.logging import LOGGER
from backend.implementations.comicvine import ComicVine
from backend.implementations.file_matching import scan_files
from backend.implementations.metadata_formats import (
    export_issue_metadata, export_volume_cover_file,
    export_volume_metadata_file, get_issue_metadata_contents)
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
    settings = Settings().sv
    if not settings.export_issue_metadata:
        return

    LOGGER.info(f"Exporting issue metadata for volume {volume_id} ({force=})")
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

            files_to_issues.setdefault(filepath, set()).add(issue.id)

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


def export_volume_metadata(volume_id: int) -> None:
    """Export the metadata of a volume. Handles both the exporting of the
    metadata to a file and the cover to an image file, based on the settings.

    Args:
        volume_id (int): The ID of the volume to export for.
    """
    settings = Settings().sv
    if not settings.export_volume_metadata and not settings.export_volume_cover:
        return

    LOGGER.info(f"Exporting volume metadata for volume {volume_id}")
    volume = Volume(volume_id)
    volume_data = volume.get_data()
    issue_data = volume.get_issues(_skip_files=True)

    if settings.export_volume_metadata:
        export_volume_metadata_file(volume_data, issue_data)

    if settings.export_volume_cover:
        cover = volume.get_cover().getvalue()
        if cover:
            export_volume_cover_file(cover, volume_data.folder)

    scan_files(volume_id)

    return
