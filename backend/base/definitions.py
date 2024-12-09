# -*- coding: utf-8 -*-

"""
Definitions of basic types, abstract classes, enums, etc.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Tuple, TypedDict, TypeVar, Union

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

    FS_API_BASE = "/v1"
    CF_CHALLENGE_HEADER = ("cf-mitigated", "challenge")

    TORRENT_UPDATE_INTERVAL = 5 # seconds
    TORRENT_TAG = "kapowarr"


class FileConstants:
    IMAGE_EXTENSIONS = ('.png', '.jpeg', '.jpg', '.webp', '.gif',
                        '.PNG', '.JPEG', '.JPG', '.WEBP', '.GIF')
    "Image extensions, with dot-prefix, and with both lowercase and uppercase"

    CONTAINER_EXTENSIONS = (
        '.cbz', '.zip', '.rar', '.cbr', '.tar.gz',
        '.7zip', '.7z', '.cb7', '.cbt', '.epub', '.pdf'
    )
    "Archive/container extensions, with dot-prefix, and only lowercase"

    EXTRACTABLE_EXTENSIONS = (
        '.zip', '.rar',
        '.ZIP', '.RAR'
    )
    """
    Archive extensions that will be considered to be extracted,
    and with both lowercase and uppercase
    """

    METADATA_EXTENSIONS = (
        ".xml", ".json",
        ".XML", ".JSON"
    )
    "Extensions of metadata files, and with both lowercase and uppercase"

    METADATA_FILES = {
        "cvinfo.xml", "comicinfo.xml",
        "series.json"
    }
    "Filenames of metadata files, and only lowercase"


CONTENT_EXTENSIONS = (
    *FileConstants.IMAGE_EXTENSIONS,
    *FileConstants.CONTAINER_EXTENSIONS
)
"Extensions of media files"


SCANNABLE_EXTENSIONS = (
    *CONTENT_EXTENSIONS,
    *FileConstants.METADATA_EXTENSIONS
)
"Extensions of files that we want to scan for"


class CharConstants:
    ALPHABET = (
        'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
        'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z'
    )
    "A tuple of all lowercase letters in the alphabet"

    DIGITS = {
        '0', '1', '2', '3', '4', '5', '6', '7', '8', '9'
    }
    "A set of the numbers 0-9 in string form"

    ROMAN_DIGITS = {
        'i': 1,
        'ii': 2,
        'iii': 3,
        'iv': 4,
        'v': 5,
        'vi': 6,
        'vii': 7,
        'viii': 8,
        'ix': 9,
        'x': 10
    }
    "A map of lowercase roman numerals 1-10 to their int equivalent"


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

    METADATA = 'metadata'
    "Metadata file"

    NORMAL = None
    "Normal volume, so not a special version"


short_sv_mapping: Dict[SpecialVersion, str] = dict((
    (SpecialVersion.HARD_COVER, 'HC'),
    (SpecialVersion.ONE_SHOT, 'OS'),
    (SpecialVersion.TPB, 'TPB'),
    (SpecialVersion.COVER, 'Cover')
))
full_sv_mapping: Dict[SpecialVersion, str] = dict((
    (SpecialVersion.HARD_COVER, 'Hard-Cover'),
    (SpecialVersion.ONE_SHOT, 'One-Shot'),
    (SpecialVersion.TPB, 'TPB'),
    (SpecialVersion.COVER, 'Cover')
))


class LibrarySorting(BaseEnum):
    TITLE = 'title, year, volume_number'
    YEAR = 'year, title, volume_number'
    VOLUME_NUMBER = 'volume_number, title, year'
    RECENTLY_ADDED = 'id DESC, title, year, volume_number'
    PUBLISHER = 'publisher, title, year, volume_number'
    WANTED = ('issues_downloaded_monitored >= issue_count_monitored, '
              'title, year, volume_number')


class LibraryFilters(BaseEnum):
    WANTED = 'WHERE issues_downloaded_monitored < issue_count_monitored'
    MONITORED = 'WHERE monitored = 1'


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


class VolumeMetadata(TypedDict):
    comicvine_id: int
    title: str
    year: Union[int, None]
    volume_number: int
    cover_link: str
    cover: Union[bytes, None]
    description: str
    site_url: str
    aliases: List[str]
    publisher: Union[str, None]
    issue_count: int
    translated: bool
    already_added: Union[int, None]
    issues: Union[List[IssueMetadata], None]


class IssueMetadata(TypedDict):
    comicvine_id: int
    volume_id: int
    issue_number: str
    calculated_issue_number: float
    title: Union[str, None]
    date: Union[str, None]
    description: str


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


class SizeData(TypedDict):
    total: int
    used: int
    free: int


class FileData(TypedDict):
    id: int
    filepath: str
    size: int


class GeneralFileData(FileData):
    file_type: str


# region Dataclasses
@dataclass
class BlocklistEntry:
    id: int
    volume_id: Union[int, None]
    issue_id: Union[int, None]

    web_link: Union[str, None]
    web_title: Union[str, None]
    web_sub_title: Union[str, None]

    download_link: Union[str, None]
    source: Union[str, None]

    reason: BlocklistReason
    added_at: int

    def as_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["reason"] = self.reason.value
        return result


@dataclass
class RootFolder:
    id: int
    folder: str
    size: SizeData

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BaseNamingKeys:
    series_name: str
    clean_series_name: str
    volume_number: str
    comicvine_id: int
    year: Union[int, None]
    publisher: Union[str, None]


@dataclass
class SVNamingKeys(BaseNamingKeys):
    special_version: Union[str, None]


@dataclass
class IssueNamingKeys(SVNamingKeys):
    issue_comicvine_id: int
    issue_number: Union[str, None]
    issue_title: Union[str, None]
    issue_release_date: Union[str, None]
    issue_release_year: Union[int, None]


@dataclass
class IssueData:
    id: int
    volume_id: int
    comicvine_id: int
    issue_number: str
    calculated_issue_number: float
    title: Union[str, None]
    date: Union[str, None]
    description: Union[str, None]
    monitored: bool
    files: List[FileData]

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VolumeData:
    id: int
    comicvine_id: int
    title: str
    alt_title: Union[str, None]
    year: int
    publisher: str
    volume_number: int
    description: str
    site_url: str
    monitored: bool
    root_folder: int
    folder: str
    custom_folder: bool
    special_version: SpecialVersion
    special_version_locked: bool
    last_cv_fetch: int


# region Abstract Classes
class DBMigrator(ABC):
    start_version: int

    @abstractmethod
    def run(self) -> None:
        ...
