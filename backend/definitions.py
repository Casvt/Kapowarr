# -*- coding: utf-8 -*-

"""
Definitions of basic types, abstract classes, enums, etc.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Tuple, TypedDict, TypeVar, Union

# region Types
T = TypeVar("T")
U = TypeVar("U")


# region Constants
class Constants:
    SUB_PROCESS_TIMEOUT = 20.0

    HOSTING_THREADS = 10
    HOSTING_TIMER_DURATION = 60.0 # seconds

    DB_FOLDER = ("db",)
    DB_NAME = "Kapowarr.db"
    DB_TIMEOUT = 10.0 # seconds

    LOGGER_NAME = "Kapowarr"
    LOGGER_FILENAME = "Kapowarr.log"

    ARCHIVE_EXTRACT_FOLDER = '.archive_extract'

    DEFAULT_USERAGENT = "Kapowarr"
    TOTAL_RETRIES = 5
    BACKOFF_FACTOR_RETRIES = 0.1
    STATUS_FORCELIST_RETRIES = (500, 502, 503, 504)

    CV_SITE_URL = "https://comicvine.gamespot.com"
    CV_API_URL = "https://comicvine.gamespot.com/api"
    CV_BRAKE_TIME = 10.0 # seconds

    GC_SITE_URL = "https://getcomics.org"

    MF_SITE_URL = "https://www.mediafire.com"

    FS_API_BASE = "/v1"

    TORRENT_UPDATE_INTERVAL = 5 # seconds
    TORRENT_TAG = "kapowarr"


FS_URLS = (
    Constants.GC_SITE_URL,
    Constants.MF_SITE_URL
)

# region Enums


class BaseEnum(Enum):
    def __eq__(self, other: object) -> bool:
        return self.value == other

    def __hash__(self) -> int:
        return id(self.value)


class RestartVersion(BaseEnum):
    NORMAL = 131
    HOSTING_CHANGES = 132


class SeedingHandling(BaseEnum):
    COMPLETE = 'complete'
    "Let torrent complete (finish seeding) and then move all files"

    COPY = 'copy'
    "Copy the files while the torrent is seeding, then delete original files"


class BlocklistReasonID(BaseEnum):
    LINK_BROKEN = 1
    SOURCE_NOT_SUPPORTED = 2
    NO_WORKING_LINKS = 3
    ADDED_BY_USER = 4


class BlocklistReason(BaseEnum):
    LINK_BROKEN = 'Link broken'

    SOURCE_NOT_SUPPORTED = 'Source not supported'

    NO_WORKING_LINKS = 'No supported or working links'

    ADDED_BY_USER = 'Added by user'


class SpecialVersion(BaseEnum):
    TPB = 'tpb'

    ONE_SHOT = 'one-shot'

    HARD_COVER = 'hard-cover'

    VOLUME_AS_ISSUE = 'volume-as-issue'
    "Volume where each issue is named `Volume N`"

    COVER = 'cover'
    "Image file is cover of either issue or volume. Overrules over SV's."

    NORMAL = None
    "Normal volume, so not a special version"


short_sv_mapping: Dict[SpecialVersion, str] = dict((
    (SpecialVersion.HARD_COVER, 'HC'),
    (SpecialVersion.ONE_SHOT, 'OS'),
    (SpecialVersion.TPB, 'TPB')
))
full_sv_mapping: Dict[SpecialVersion, str] = dict((
    (SpecialVersion.HARD_COVER, 'Hard-Cover'),
    (SpecialVersion.ONE_SHOT, 'One-Shot'),
    (SpecialVersion.TPB, 'TPB')
))


class DownloadState(BaseEnum):
    QUEUED_STATE = 'queued'
    DOWNLOADING_STATE = 'downloading'
    SEEDING_STATE = 'seeding'
    IMPORTING_STATE = 'importing'

    FAILED_STATE = 'failed'
    "Download was unsuccessful"
    CANCELED_STATE = 'canceled'
    "Download was removed from queue"
    SHUTDOWN_STATE = 'shutting down'
    "Download was stopped because Kapowarr is shutting down"


class SocketEvent(BaseEnum):
    TASK_ADDED = 'task_added'
    TASK_STATUS = 'task_status'
    TASK_ENDED = 'task_ended'

    QUEUE_ADDED = 'queue_added'
    QUEUE_STATUS = 'queue_status'
    QUEUE_ENDED = 'queue_ended'


class FailReason(BaseEnum):
    BROKEN = 'GetComics page unavailable'
    NO_WORKING_LINKS = 'No working download links on page'
    LIMIT_REACHED = 'Download limit reached for service'
    NO_MATCHES = 'No links found that match to volume and are not blocklisted'


class GeneralFileType(BaseEnum):
    METADATA = 'metadata'
    COVER = 'cover'


class GCDownloadSource(BaseEnum):
    MEGA = 'Mega'
    MEDIAFIRE = 'MediaFire'
    WETRANSFER = 'WeTransfer'
    PIXELDRAIN = 'Pixeldrain'
    GETCOMICS = 'GetComics'
    GETCOMICS_TORRENT = 'GetComics (torrent)'


download_source_versions: Dict[GCDownloadSource, Tuple[str, ...]] = dict((
    (GCDownloadSource.MEGA, ('mega', 'mega link')),
    (GCDownloadSource.MEDIAFIRE, ('mediafire', 'mediafire link')),
    (GCDownloadSource.WETRANSFER,
        ('wetransfer', 'we transfer', 'wetransfer link', 'we transfer link')),
    (GCDownloadSource.PIXELDRAIN,
        ('pixeldrain', 'pixel drain', 'pixeldrain link', 'pixel drain link')),
    (GCDownloadSource.GETCOMICS,
        ('getcomics', 'download now', 'main download', 'main server', 'main link',
       'mirror download', 'mirror server', 'mirror link', 'link 1', 'link 2')),
    (GCDownloadSource.GETCOMICS_TORRENT,
        ('getcomics (torrent)', 'torrent', 'torrent link', 'magnet',
        'magnet link')),
))
"""
GCDownloadSource to strings that can be found in the button text for the
service on the GC page.
"""


# Future proofing. In the future, there'll be sources like 'torrent' and
# 'usenet'. In part of the code, we want access to all download sources,
# and in the other part we only want the GC services. So in preparation
# of the torrent and usenet sources coming, we're already making the
# distinction here.
class DownloadSource(BaseEnum):
    MEGA = 'Mega'
    MEDIAFIRE = 'MediaFire'
    WETRANSFER = 'WeTransfer'
    PIXELDRAIN = 'Pixeldrain'
    GETCOMICS = 'GetComics'
    GETCOMICS_TORRENT = 'GetComics (torrent)'


class MonitorScheme(BaseEnum):
    ALL = "all"
    MISSING = "missing"
    NONE = "none"


# region TypedDicts
class FilenameData(TypedDict):
    series: str
    year: Union[int, None]
    volume_number: Union[int, Tuple[int, int], None]
    special_version: Union[str, None]
    issue_number: Union[float, Tuple[float, float], None]
    annual: bool


class SearchResultData(FilenameData):
    link: str
    display_title: str
    source: str


class SearchResultMatchData(TypedDict):
    match: bool
    match_issue: Union[str, None]


class MatchedSearchResultData(
    SearchResultMatchData,
    SearchResultData,
    total=False
):
    _issue_number: Union[float, Tuple[float, float]]


class CVFileMapping(TypedDict):
    id: int
    filepath: str


class DownloadGroup(TypedDict):
    web_sub_title: str
    info: FilenameData
    links: Dict[GCDownloadSource, List[str]]


class ClientTestResult(TypedDict):
    success: bool
    description: Union[None, str]


# region Abstract Classes
class DBMigrator(ABC):
    start_version: int

    @abstractmethod
    def run(self) -> None:
        ...
