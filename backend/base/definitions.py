# -*- coding: utf-8 -*-

"""
Definitions of basic types, abstract classes, enums, etc.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from enum import Enum
from threading import Event, Thread
from typing import (TYPE_CHECKING, Any, Dict, List, Mapping,
                    Sequence, Tuple, TypedDict, TypeVar, Union)

if TYPE_CHECKING:
    from backend.base.helpers import AsyncSession

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
    ZIP_MIN_MOD_TIME = 315619200
    RAR_EXECUTABLES = {
        'linux': 'rar_linux_64',
        'darwin': 'rar_bsd_64',
        'win32': 'rar_windows_64.exe'
    }

    DEFAULT_USERAGENT = "Kapowarr"
    TOTAL_RETRIES = 5
    BACKOFF_FACTOR_RETRIES = 0.1
    STATUS_FORCELIST_RETRIES = (500, 502, 503, 504)

    CV_SITE_URL = "https://comicvine.gamespot.com"
    CV_API_URL = "https://comicvine.gamespot.com/api"
    CV_BRAKE_TIME = 10.0 # seconds

    GC_SITE_URL = "https://getcomics.org"
    GC_SOURCE_TERM = "GetComics"

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
    PAUSED_STATE = 'paused'
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


class CredentialSource(BaseEnum):
    MEGA = "mega"


class DownloadType(BaseEnum):
    DIRECT = 1
    TORRENT = 2


query_formats: Dict[str, Tuple[str, ...]] = {
    "TPB": (
        '{title} Vol. {volume_number} ({year}) TPB',
        '{title} ({year}) TPB',
        '{title} Vol. {volume_number} TPB',
        '{title} Vol. {volume_number}',
        '{title}'
    ),
    "VAI": (
        '{title} ({year})',
        '{title}'
    ),
    "Volume": (
        '{title} Vol. {volume_number} ({year})',
        '{title} ({year})',
        '{title} Vol. {volume_number}',
        '{title}'
    ),
    "Issue": (
        '{title} #{issue_number} ({year})',
        '{title} Vol. {volume_number} #{issue_number}',
        '{title} #{issue_number}',
        '{title}'
    )
}
"""
Volume Special Version to query formats used when searching
"""


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


@dataclass
class CredentialData:
    id: int
    source: CredentialSource
    username: Union[str, None]
    email: Union[str, None]
    password: Union[str, None]
    api_key: Union[str, None]

    def as_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['source'] = self.source.value
        return result


# region Abstract Classes
class DBMigrator(ABC):
    start_version: int

    @abstractmethod
    def run(self) -> None:
        ...


class MassEditorAction(ABC):
    identifier: str
    "The string used in the API to refer to the action."

    def __init__(self, volume_ids: List[int]) -> None:
        """Ready a mass editor action.

        Args:
            volume_ids (List[int]): The volume IDs to work on.
        """
        self.volume_ids = volume_ids
        return

    @abstractmethod
    def run(self, **kwargs) -> None:
        """Run the mass editor action."""
        ...


class FileConverter(ABC):
    source_format: str
    target_format: str

    @staticmethod
    @abstractmethod
    def convert(file: str) -> List[str]:
        """Convert a file from source_format to target_format.

        Args:
            file (str): Filepath to the source file, should be in source_format.

        Returns:
            List[str]: The resulting files or directories, in target_format.
        """
        ...


class SearchSource(ABC):
    def __init__(self, query: str) -> None:
        """Prepare the search source.

        Args:
            query (str): The query to search for.
        """
        self.query = query
        return

    @abstractmethod
    async def search(self, session: AsyncSession) -> List[SearchResultData]:
        """Search for the query.

        Args:
            session (AsyncSession): The session to use for the search.

        Returns:
            List[SearchResultData]: The search results.
        """
        ...


class ExternalDownloadClient(ABC):
    client_type: str
    "What name the external client has, like 'qBittorrent'."

    download_type: DownloadType
    "What type of download it is, e.g. a torrent."

    required_tokens: Sequence[str]
    """The keys the client needs or could need for operation
    (mostly whether it's username + password or api_token)"""

    @property
    @abstractmethod
    def id(self) -> int:
        ...

    @property
    @abstractmethod
    def title(self) -> str:
        ...

    @property
    @abstractmethod
    def base_url(self) -> str:
        ...

    @property
    @abstractmethod
    def username(self) -> Union[str, None]:
        ...

    @property
    @abstractmethod
    def password(self) -> Union[str, None]:
        ...

    @property
    @abstractmethod
    def api_token(self) -> Union[str, None]:
        ...

    @abstractmethod
    def __init__(self, client_id: int) -> None:
        """Create a connection with a client.

        Args:
            client_id (int): The ID of the client.
        """
        ...

    @abstractmethod
    def get_client_data(self) -> Dict[str, Any]:
        """Get info about the client.

        Returns:
            Dict[str, Any]: The info about the client.
        """
        ...

    @abstractmethod
    def update_client(self, data: Mapping[str, Any]) -> None:
        """Edit the client.

        Args:
            data (Mapping[str, Any]): The keys and their new values for
            the client settings.

        Raises:
            ClientDownloading: There is a download in the queue using the
            client.
            ExternalClientNotWorking: Failed to connect to the client.
            KeyNotFound: A required key was not found.
            InvalidKeyValue: One of the parameters has an invalid argument.
        """
        ...

    @abstractmethod
    def delete_client(self) -> None:
        """Delete the client.

        Raises:
            ClientDownloading: There is a download in the queue using the
            client.
        """
        ...

    @abstractmethod
    def add_download(
        self,
        download_link: str,
        target_folder: str,
        download_name: Union[str, None]
    ) -> str:
        """Add a download to the client.

        Args:
            download_link (str): The link to the download (e.g. magnet link).
            target_folder (str): The folder to download in.
            download_name (Union[str, None]): The name of the downloaded folder
            or file. Set to `None` to keep original name.

        Raises:
            ExternalClientNotWorking: Can't connect to client.

        Returns:
            str: The ID/hash of the entry in the download client.
        """
        ...

    @abstractmethod
    def get_download(self, download_id: str) -> Union[dict, None]:
        """Get the information/status of a download.

        Args:
            download_id (str): The ID/hash of the download to get info of.

        Raises:
            ExternalClientNotWorking: Can't connect to client.

        Returns:
            Union[dict, None]: The status of the download,
            empty dict if download is not found
            and `None` if client deleted the download.
        """
        ...

    @abstractmethod
    def delete_download(self, download_id: str, delete_files: bool) -> None:
        """Remove the download from the client.

        Raises:
            ExternalClientNotWorking: Can't connect to client.

        Args:
            download_id (str): The ID/hash of the download to delete.
            delete_files (bool): Whether to delete the downloaded files.
        """
        ...

    @staticmethod
    @abstractmethod
    def test(
        base_url: str,
        username: Union[str, None],
        password: Union[str, None],
        api_token: Union[str, None]
    ) -> Union[str, None]:
        """Check if a download client is working.

        Args:
            base_url (str): The base url on which the client is running.
            username (Union[str, None]): The username to access the client, if set.
            password (Union[str, None]): The password to access the client, if set.
            api_token (Union[str, None]): The api token to access the client, if set.

        Returns:
            Union[str, None]: If it's a fail, the reason for failing. If it's
            a success, `None`.
        """
        ...

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}; ID {self.id}; {id(self)}>'


class Download(ABC):
    type: str

    @property
    @abstractmethod
    def id(self) -> int:
        ...

    @id.setter
    @abstractmethod
    def id(self, value: int) -> None:
        ...

    @property
    @abstractmethod
    def volume_id(self) -> int:
        ...

    @property
    @abstractmethod
    def issue_id(self) -> Union[int, None]:
        ...

    @property
    @abstractmethod
    def covered_issues(self) -> Union[float, Tuple[float, float], None]:
        ...

    @property
    @abstractmethod
    def web_link(self) -> Union[str, None]:
        """Link to webpage for download"""
        ...

    @property
    @abstractmethod
    def web_title(self) -> Union[str, None]:
        """Title of webpage (or release) for download"""
        ...

    @property
    @abstractmethod
    def web_sub_title(self) -> Union[str, None]:
        """
        Title of sub-section that download falls under (e.g. GC group name)
        """
        ...

    @property
    @abstractmethod
    def download_link(self) -> str:
        """The link to the download or service page (e.g. link to MF page)"""
        ...

    @property
    @abstractmethod
    def pure_link(self) -> str:
        """
        The pure link to download from (e.g. pixeldrain API link or MF folder ID)
        """
        ...

    @property
    @abstractmethod
    def source_type(self) -> DownloadSource:
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """
        The display name of the source. E.g. source_type is Torrent,
        source_name is indexer name.
        """
        ...

    @property
    @abstractmethod
    def files(self) -> List[str]:
        """List of folders/files that were 'produced' by this download"""
        ...

    @files.setter
    @abstractmethod
    def files(self, value: List[str]) -> None:
        ...

    @property
    @abstractmethod
    def filename_body(self) -> str:
        """
        The body of the file/folder name that the downloaded file(s) should
        be named as at their (almost) final destination.
        """
        ...

    @property
    @abstractmethod
    def title(self) -> str:
        """Display title of download"""
        ...

    @property
    @abstractmethod
    def size(self) -> int:
        ...

    @property
    @abstractmethod
    def state(self) -> DownloadState:
        ...

    @state.setter
    @abstractmethod
    def state(self, value: DownloadState) -> None:
        ...

    @property
    @abstractmethod
    def progress(self) -> float:
        ...

    @property
    @abstractmethod
    def speed(self) -> float:
        ...

    @property
    @abstractmethod
    def download_thread(self) -> Union[Thread, None]:
        ...

    @download_thread.setter
    @abstractmethod
    def download_thread(self, value: Thread) -> None:
        ...

    @property
    @abstractmethod
    def download_folder(self) -> str:
        ...

    @abstractmethod
    def __init__(
        self,
        download_link: str,

        volume_id: int,
        covered_issues: Union[float, Tuple[float, float], None],

        source_type: DownloadSource,
        source_name: str,

        web_link: Union[str, None],
        web_title: Union[str, None],
        web_sub_title: Union[str, None],

        force_original_name: bool = False
    ) -> None:
        """Create the download instance.

        Args:
            download_link (str): The link to the download.
                Could be direct download link, mega link, magnet link, etc.

            volume_id (int): The ID of the volume that the download is for.

            covered_issues (Union[float, Tuple[float, float], None]):
            The calculated issue number (range) that the download covers,
            or None if download is for special version.

            source_type (DownloadSource): The source type of the download.

            source_name (str): The display name of the source.
            E.g. indexer name.

            web_link (Union[str, None]): Link to webpage for download.

            web_title (Union[str, None]): Title of webpage (or release) for download.

            web_sub_title (Union[str, None]): Title of sub-section that download
            falls under (e.g. GC group name).

            force_original_name (bool, optional): Whether to keep the original
            name of the download instead of possibly generating one (based on
            the rename_downloaded_files setting).
                Defaults to False.

        Raises:
            LinkBroken: The link doesn't work
        """
        ...

    @abstractmethod
    def run(self) -> None:
        """Start the download."""
        ...

    @abstractmethod
    def stop(
        self,
        state: DownloadState = DownloadState.CANCELED_STATE
    ) -> None:
        """Interrupt the download.

        Args:
            state (DownloadState, optional): The state to set for the download.
                Defaults to DownloadState.CANCELED_STATE.
        """
        ...

    @abstractmethod
    def todict(self) -> Dict[str, Any]:
        """Get a dict representing the download.

        Returns:
            Dict[str, Any]: The dict with all information.
        """
        ...


class ExternalDownload(Download):
    @property
    @abstractmethod
    def external_client(self) -> ExternalDownloadClient:
        ...

    @external_client.setter
    @abstractmethod
    def external_client(self, value: ExternalDownloadClient) -> None:
        ...

    @property
    @abstractmethod
    def external_id(self) -> Union[str, None]:
        """The ID/hash of the download in the external client."""
        ...

    @property
    @abstractmethod
    def sleep_event(self) -> Event:
        """A threading.Event to use for sleeping the download thread."""
        ...

    @abstractmethod
    def __init__(
        self,
        download_link: str,

        volume_id: int,
        covered_issues: Union[float, Tuple[float, float], None],

        source_type: DownloadSource,
        source_name: str,

        web_link: Union[str, None],
        web_title: Union[str, None],
        web_sub_title: Union[str, None],

        force_original_name: bool = False,
        external_client: Union[ExternalDownloadClient, None] = None
    ) -> None:
        """Create the download instance.

        Args:
            download_link (str): The link to the download.
                Could be direct download link, mega link, magnet link, etc.

            volume_id (int): The ID of the volume that the download is for.

            covered_issues (Union[float, Tuple[float, float], None]):
            The calculated issue number (range) that the download covers,
            or None if download is for special version.

            source_type (DownloadSource): The source type of the download.

            source_name (str): The display name of the source.
            E.g. indexer name.

            web_link (Union[str, None]): Link to webpage for download.

            web_title (Union[str, None]): Title of webpage (or release) for download.

            web_sub_title (Union[str, None]): Title of sub-section that download
            falls under (e.g. GC group name).

            force_original_name (bool, optional): Whether to keep the original
            name of the download instead of possibly generating one (based on
            the rename_downloaded_files setting).
                Defaults to False.

            external_client (Union[ExternalDownloadClient, None], optional):
            Force an external client instead of letting the download choose one.
                Defaults to None.

        Raises:
            LinkBroken: The link doesn't work
        """
        ...

    @abstractmethod
    def update_status(self) -> None:
        """
        Update the various variables about the state/progress
        of the torrent download.
        """
        ...

    @abstractmethod
    def remove_from_client(self, delete_files: bool) -> None:
        """Remove the download from the client.

        Args:
            delete_files (bool): Delete downloaded files.
        """
        ...
