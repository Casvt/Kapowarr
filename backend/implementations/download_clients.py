# -*- coding: utf-8 -*-

"""
All download implementations.
"""

from __future__ import annotations

from base64 import b64encode
from json import loads
from os.path import basename, join, sep, splitext
from re import IGNORECASE, compile
from threading import Event, Thread
from time import perf_counter
from typing import TYPE_CHECKING, Any, Dict, List, Tuple, Type, Union, final
from urllib.parse import unquote_plus

from bs4 import BeautifulSoup, Tag
from requests import RequestException, Response
from websocket import create_connection
from websocket._exceptions import WebSocketBadStatusException

from backend.base.custom_exceptions import (ClientNotWorking,
                                            DownloadLimitReached,
                                            IssueNotFound, LinkBroken)
from backend.base.definitions import (BlocklistReason, Constants,
                                      CredentialSource, Download,
                                      DownloadSource, DownloadState,
                                      DownloadType, ExternalDownload,
                                      ExternalDownloadClient)
from backend.base.helpers import Session, get_first_of_range, get_torrent_info
from backend.base.logging import LOGGER
from backend.implementations.credentials import Credentials
from backend.implementations.direct_clients.mega import (Mega, MegaABC,
                                                         MegaFolder)
from backend.implementations.external_clients import ExternalClients
from backend.implementations.naming import generate_issue_name
from backend.implementations.volumes import Issue, Volume
from backend.internals.server import WebSocket
from backend.internals.settings import Settings

if TYPE_CHECKING:
    from requests import Response


# autopep8: off
file_extension_regex = compile(r'(?<=\.|\/)[\w\d]{2,4}(?=$|;|\s|\")', IGNORECASE)
file_name_regex = compile(r'filename(?:=\"|\*=UTF-8\'\')(.*?)\.[a-z]{2,4}\"?$', IGNORECASE)
extract_mediafire_regex = compile(r'window.location.href\s?=\s?\'https://download\d+\.mediafire.com/.*?(?=\')', IGNORECASE)
DOWNLOAD_CHUNK_SIZE = 4194304 # 4MB Chunks
MEDIAFIRE_FOLDER_LINK = "https://www.mediafire.com/api/1.5/file/zip.php"
WETRANSFER_API_LINK = "https://wetransfer.com/api/v4/transfers/{transfer_id}/download"
# autopep8: on


# region Base Direct Download
class BaseDirectDownload(Download):
    @property
    def id(self) -> int:
        return self._id # type: ignore

    @id.setter
    def id(self, value: int) -> None:
        self._id = value
        return

    @property
    def volume_id(self) -> int:
        return self._volume_id

    @property
    def issue_id(self) -> Union[int, None]:
        return self._issue_id

    @property
    def covered_issues(self) -> Union[float, Tuple[float, float], None]:
        return self._covered_issues

    @property
    def web_link(self) -> Union[str, None]:
        return self._web_link

    @property
    def web_title(self) -> Union[str, None]:
        return self._web_title

    @property
    def web_sub_title(self) -> Union[str, None]:
        return self._web_sub_title

    @property
    def download_link(self) -> str:
        return self._download_link

    @property
    def pure_link(self) -> str:
        return self._pure_link

    @property
    def source_type(self) -> DownloadSource:
        return self._source_type

    @property
    def source_name(self) -> str:
        return self._source_name

    @property
    def files(self) -> List[str]:
        return self._files

    @files.setter
    def files(self, value: List[str]) -> None:
        self._files = value
        return

    @property
    def filename_body(self) -> str:
        return self._filename_body

    @property
    def title(self) -> str:
        return self._title

    @property
    def size(self) -> int:
        return self._size

    @property
    def state(self) -> DownloadState:
        return self._state

    @state.setter
    def state(self, value: DownloadState) -> None:
        self._state = value
        return

    @property
    def progress(self) -> float:
        return self._progress

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def download_thread(self) -> Union[Thread, None]:
        return self._download_thread

    @download_thread.setter
    def download_thread(self, value: Thread) -> None:
        self._download_thread = value
        return

    @property
    def download_folder(self) -> str:
        return self._download_folder

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

        forced_match: bool = False
    ) -> None:
        LOGGER.debug(
            'Creating download: %s',
            download_link
        )

        settings = Settings().sv
        volume = Volume(volume_id)

        self.__r = None
        self._download_link = download_link
        self._volume_id = volume_id
        self._issue_id = None
        self._covered_issues = covered_issues
        self._source_type = source_type
        self._source_name = source_name
        self._web_link = web_link
        self._web_title = web_title
        self._web_sub_title = web_sub_title

        self._id = None
        self._state = DownloadState.QUEUED_STATE
        self._progress = 0.0
        self._speed = 0.0
        self._download_thread = None
        self._download_folder = settings.download_folder

        self._ssn = Session()

        # Create and fetch pure link to extract last info
        # This can fail if the link is broken, so do before other
        # intensive tasks to save time (no need to do intensive tasks when
        # link is broken).
        try:
            self._pure_link = self._convert_to_pure_link()
            with self._fetch_pure_link() as response:
                response.raise_for_status()

        except RequestException as e:
            if (
                e.response is not None
                and e.response.url.startswith(Constants.PIXELDRAIN_API_URL)
                and e.response.status_code == 403
            ):
                # Pixeldrain rate limit because of hotlinking
                raise DownloadLimitReached(DownloadSource.PIXELDRAIN)

            raise LinkBroken(BlocklistReason.LINK_BROKEN)

        self._size = int(response.headers.get('Content-Length', -1))

        self._filename_body = ''
        try:
            if isinstance(covered_issues, float):
                self._issue_id = Issue.from_volume_and_calc_number(
                    volume_id, covered_issues
                ).id

            if settings.rename_downloaded_files:
                self._filename_body = generate_issue_name(
                    volume_id,
                    volume.get_data().special_version,
                    covered_issues
                )

        except IssueNotFound as e:
            if not forced_match:
                raise e

        if not self._filename_body:
            self._filename_body = self._extract_default_filename_body(response)

        self._title = basename(self._filename_body)
        self._files = [self._build_filename(response)]
        return

    def _convert_to_pure_link(self) -> str:
        return self.download_link

    def _fetch_pure_link(self) -> Response:
        return self._ssn.get(self.pure_link, stream=True)

    def _extract_default_filename_body(
        self,
        response: Union[Response, None]
    ) -> str:
        if response and response.headers.get('Content-Disposition'):
            file_result = file_name_regex.search(
                response.headers['Content-Disposition']
            )
            if file_result:
                return unquote_plus(
                    file_result.group(1)
                )

        return splitext(unquote_plus(
            self.pure_link.split('/')[-1].split("?")[0]
        ))[0]

    def _extract_extension(self, response: Union[Response, None]) -> str:
        if not response:
            return ''

        match = file_extension_regex.findall(
            ' '.join((
                response.headers.get('Content-Disposition', ''),
                response.headers.get('Content-Type', ''),
                response.url
            ))
        )
        if match:
            return '.' + match[0]
        return ''

    def _build_filename(self, response: Union[Response, None]) -> str:
        extension = self._extract_extension(response)
        return join(
            self._download_folder,
            '_'.join(self._filename_body.split(sep)) + extension
        )

    def run(self) -> None:
        self._state = DownloadState.DOWNLOADING_STATE
        size_downloaded = 0
        ws = WebSocket()
        ws.update_queue_status(self)

        with \
            self._fetch_pure_link() as r, \
            open(self.files[0], 'wb') as f:

            self.__r = r
            start_time = perf_counter()
            try:
                for chunk in r.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                    if self.state in (
                        DownloadState.CANCELED_STATE,
                        DownloadState.SHUTDOWN_STATE
                    ):
                        break

                    f.write(chunk)

                    # Update progress
                    chunk_size = len(chunk)
                    size_downloaded += chunk_size
                    self._speed = round(
                        chunk_size / (perf_counter() - start_time),
                        2
                    )
                    if self.size == -1:
                        # No file size so progress is amount downloaded
                        self._progress = size_downloaded
                    else:
                        self._progress = round(
                            size_downloaded / self.size * 100,
                            2
                        )

                    start_time = perf_counter()
                    ws.update_queue_status(self)

            except RequestException:
                self._state = DownloadState.FAILED_STATE

            finally:
                self.__r = None

        return

    def stop(self,
        state: DownloadState = DownloadState.CANCELED_STATE
    ) -> None:
        self._state = state
        if (
            self.__r
            and self.__r.raw._fp
            and not isinstance(self.__r.raw._fp, str)
        ):
            self.__r.raw._fp.fp.raw._sock.shutdown(2) # SHUT_RDWR
        return

    def todict(self) -> Dict[str, Any]:
        return {
            'id': self._id,
            'volume_id': self._volume_id,
            'issue_id': self._issue_id,

            'web_link': self._web_link,
            'web_title': self._web_title,
            'web_sub_title': self._web_sub_title,
            'download_link': self._download_link,
            'pure_link': self._pure_link,

            'source_type': self._source_type.value,
            'source_name': self._source_name,
            'type': self.type,

            'file': self._files[0],
            'title': self._title,
            'download_folder': self._download_folder,

            'size': self._size,
            'status': self._state.value,
            'progress': self._progress,
            'speed': self._speed
        }

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}, {self.download_link}, {self.files[0]}, {self.state.value}>'


# region Direct
@final
class DirectDownload(BaseDirectDownload):
    "For downloading a file directly from a link"

    type = 'direct'


# region MediaFire
@final
class MediaFireDownload(BaseDirectDownload):
    "For downloading a MediaFire file"

    type = 'mf'

    def _convert_to_pure_link(self) -> str:
        r = self._ssn.get(
            self.download_link,
            stream=True
        )
        result = extract_mediafire_regex.search(r.text)
        if result:
            return result.group(0).split("'")[-1]

        soup = BeautifulSoup(r.text, 'html.parser')
        button = soup.find('a', {'id': 'downloadButton'})
        if isinstance(button, Tag):
            return get_first_of_range(button['href'])

        # Link is not broken and not a folder
        # but we still can't find the download button...
        raise LinkBroken(BlocklistReason.LINK_BROKEN)


# region MediaFire Folder
@final
class MediaFireFolderDownload(BaseDirectDownload):
    "For downloading a MediaFire folder (for MF file, use MediaFireDownload)"

    type = 'mf_folder'

    def _convert_to_pure_link(self) -> str:
        return self.download_link.split("/folder/")[1].split("/")[0]

    def _fetch_pure_link(self) -> Response:
        return self._ssn.post(
            MEDIAFIRE_FOLDER_LINK,
            files={
                "keys": (None, self.pure_link),
                "meta_only": (None, "no"),
                "allow_large_download": (None, "yes"),
                "response_format": (None, "json")
            },
            stream=True
        )


# region WeTransfer
@final
class WeTransferDownload(BaseDirectDownload):
    "For downloading a file or folder from WeTransfer"

    type = 'wt'

    def _convert_to_pure_link(self) -> str:
        transfer_id, security_hash = self.download_link.split("/")[-2:]
        r = self._ssn.post(
            WETRANSFER_API_LINK.format(transfer_id=transfer_id),
            json={
                "intent": "entire_transfer",
                "security_hash": security_hash
            },
            headers={"x-requested-with": "XMLHttpRequest"}
        )
        if not r.ok:
            raise LinkBroken(BlocklistReason.LINK_BROKEN)

        direct_link = r.json().get("direct_link")

        if not direct_link:
            raise LinkBroken(BlocklistReason.LINK_BROKEN)

        return direct_link


# region PixelDrain
class PixelDrainDownload(BaseDirectDownload):
    "For downloading a file from PixelDrain"

    type = 'pd'

    @staticmethod
    def login(api_key: str) -> int:
        LOGGER.debug('Logging into Pixeldrain with user api key')
        try:
            with Session() as session:
                response = session.get(
                    Constants.PIXELDRAIN_API_URL + '/user/lists',
                    headers={
                        "Authorization": "Basic " + b64encode(
                            f":{api_key}".encode()
                        ).decode()
                    }
                )
                if response.status_code == 401:
                    return -1

            ws = create_connection(
                Constants.PIXELDRAIN_WEBSOCKET_URL + '/file_stats',
                header=["Cookie: pd_auth_key=" + api_key]
            )

        except RequestException:
            raise ClientNotWorking(
                "An unexpected error occured when making contact with Pixeldrain"
            )

        except WebSocketBadStatusException as e:
            if e.status_code == 401:
                return -1

            raise ClientNotWorking(
                "An unexpected error occured when making contact with Pixeldrain"
            )

        ws.send('{"type": "limits"}')
        response = loads(ws.recv())
        ws.close()

        LOGGER.debug(
            f'Pixeldrain account transfer state: {response["limits"]["transfer_limit_used"]}/{response["limits"]["transfer_limit"]}'
        )
        return int(
            response["limits"]["transfer_limit_used"]
            < response["limits"]["transfer_limit"]
        )

    def _convert_to_pure_link(self) -> str:
        self._api_key = None
        self._first_fetch = True
        download_id = self.download_link.rstrip("/").split("/")[-1]
        return Constants.PIXELDRAIN_API_URL + '/file/' + download_id

    def _fetch_pure_link(self) -> Response:
        if self._first_fetch:
            cred = Credentials()
            for pd_cred in cred.get_from_source(CredentialSource.PIXELDRAIN):
                if self.login(pd_cred.api_key or '') == 1:
                    # Key works and has not reached limit
                    self._api_key = pd_cred.api_key
                    break
            self._first_fetch = False

        headers = {}
        if self._api_key:
            headers["Authorization"] = "Basic " + b64encode(
                f":{self._api_key}".encode()
            ).decode()

        return self._ssn.get(
            self.pure_link,
            headers=headers,
            stream=True
        )


# region PixelDrain Folder
@final
class PixelDrainFolderDownload(PixelDrainDownload):
    "For downloading a PixelDrain folder (for PD file, use PixelDrainDownload)"

    type = 'pd_folder'

    def _convert_to_pure_link(self) -> str:
        self._api_key = None
        self._first_fetch = True
        download_id = self.download_link.rstrip("/").split("/")[-1]
        'https://pixeldrain.com/api/list/{download_id}/zip'
        return Constants.PIXELDRAIN_API_URL + '/list/' + download_id + '/zip'


# region Mega
class MegaDownload(BaseDirectDownload):
    "For downloading a file via Mega"

    type = 'mega'
    _mega_class: Type[MegaABC] = Mega

    @property
    def size(self) -> int:
        return self._mega.size

    @property
    def progress(self) -> float:
        return self._mega.progress

    @property
    def speed(self) -> float:
        return self._mega.speed

    @property
    def _size(self) -> int:
        return self._mega.size

    @property
    def _progress(self) -> float:
        return self._mega.progress

    @property
    def _speed(self) -> float:
        return self._mega.speed

    @property
    def _pure_link(self) -> str:
        return self._mega.pure_link

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

        forced_match: bool = False
    ) -> None:
        LOGGER.debug(
            'Creating mega download: %s',
            download_link
        )

        settings = Settings().sv
        volume = Volume(volume_id)

        self._download_link = download_link
        self._volume_id = volume_id
        self._issue_id = None
        self._covered_issues = covered_issues
        self._source_type = source_type
        self._source_name = source_name
        self._web_link = web_link
        self._web_title = web_title
        self._web_sub_title = web_sub_title

        self._id = None
        self._state = DownloadState.QUEUED_STATE
        self._download_thread = None
        self._download_folder = settings.download_folder

        try:
            self._mega = self._mega_class(download_link)
        except ClientNotWorking:
            raise LinkBroken(BlocklistReason.LINK_BROKEN)

        self._filename_body = ''
        try:
            if isinstance(covered_issues, float):
                self._issue_id = Issue.from_volume_and_calc_number(
                    volume_id, covered_issues
                ).id

            if settings.rename_downloaded_files:
                self._filename_body = generate_issue_name(
                    volume_id,
                    volume.get_data().special_version,
                    covered_issues
                )

        except IssueNotFound as e:
            if not forced_match:
                raise e

        if not self._filename_body:
            self._filename_body = self._extract_default_filename_body(
                response=None
            )

        self._title = basename(self._filename_body)
        self._files = [self._build_filename(response=None)]
        return

    def _extract_default_filename_body(
        self,
        response: Union[Response, None]
    ) -> str:
        return splitext(self._mega.mega_filename)[0]

    def _extract_extension(self, response: Union[Response, None]) -> str:
        return splitext(self._mega.mega_filename)[1]

    def run(self) -> None:
        self._state = DownloadState.DOWNLOADING_STATE
        ws = WebSocket()
        try:
            self._mega.download(
                self.files[0],
                lambda: ws.update_queue_status(self)
            )

        except ClientNotWorking:
            self._state = DownloadState.FAILED_STATE

        return

    def stop(self,
        state: DownloadState = DownloadState.CANCELED_STATE
    ) -> None:
        self._state = state
        self._mega.stop()
        return


@final
class MegaFolderDownload(MegaDownload):
    "For downloading a Mega folder (for Mega file, use MegaDownload)"

    type = 'mega_folder'
    _mega_class = MegaFolder


# region Torrent
@final
class TorrentDownload(ExternalDownload, BaseDirectDownload):
    type = 'torrent'

    @property
    def external_client(self) -> ExternalDownloadClient:
        return self._external_client

    @external_client.setter
    def external_client(self, value: ExternalDownloadClient) -> None:
        self._external_client = value
        return

    @property
    def external_id(self) -> Union[str, None]:
        return self._external_id

    @property
    def sleep_event(self) -> Event:
        return self._sleep_event

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

        forced_match: bool = False,
        external_client: Union[ExternalDownloadClient, None] = None
    ) -> None:
        LOGGER.debug(
            'Creating download: %s',
            download_link
        )

        settings = Settings().sv

        self._download_link = self._pure_link = download_link
        self._volume_id = volume_id
        self._issue_id = None
        self._covered_issues = covered_issues
        self._source_type = source_type
        self._source_name = source_name
        self._web_link = web_link
        self._web_title = web_title
        self._web_sub_title = web_sub_title

        self._id = None
        self._state = DownloadState.QUEUED_STATE
        self._progress = 0.0
        self._speed = 0.0
        self._size = -1
        self._download_thread = None
        self._download_folder = settings.download_folder
        self._sleep_event = Event()

        self._original_files: List[str] = []
        self._external_id: Union[str, None] = None
        if external_client:
            self._external_client = external_client
        else:
            self._external_client = ExternalClients.get_least_used_client(
                DownloadType.TORRENT
            )

        try:
            if isinstance(covered_issues, float):
                self._issue_id = Issue.from_volume_and_calc_number(
                    volume_id, covered_issues
                ).id

        except IssueNotFound as e:
            if not forced_match:
                raise e

        # Find name of torrent as that becomes folder that media is
        # downloaded in
        try:
            response = Session().post(
                'https://magnet2torrent.com/upload/',
                data={'magnet': download_link}
            )
            response.raise_for_status()
            if response.headers.get(
                'Content-Type'
            ) != 'application/x-bittorrent':
                raise RequestException

        except RequestException:
            raise LinkBroken(BlocklistReason.LINK_BROKEN)

        torrent_name = get_torrent_info(response.content)[b'name'].decode()

        self._filename_body = ''
        if settings.rename_downloaded_files:
            try:
                self._filename_body = generate_issue_name(
                    volume_id,
                    Volume(volume_id).get_data().special_version,
                    covered_issues
                )

            except IssueNotFound as e:
                if not forced_match:
                    raise e

        if not self._filename_body:
            self._filename_body = splitext(torrent_name)[0]

        self._title = basename(self._filename_body)
        self._files = [join(self._download_folder, torrent_name)]
        return

    def run(self) -> None:
        self._external_id = self.external_client.add_download(
            self.download_link,
            self._download_folder,
            self.title
        )
        return

    def update_status(self) -> None:
        if not self.external_id:
            return

        torrent_status = self.external_client.get_download(self.external_id)
        if not torrent_status:
            if torrent_status is None:
                self._state = DownloadState.CANCELED_STATE
            return

        self._progress = torrent_status['progress']
        self._speed = torrent_status['speed']
        self._size = torrent_status['size']
        if self.state not in (
            DownloadState.CANCELED_STATE,
            DownloadState.SHUTDOWN_STATE
        ):
            self._state = torrent_status['state']

        return

    def remove_from_client(self, delete_files: bool) -> None:
        if not self.external_id:
            return

        self.external_client.delete_download(self.external_id, delete_files)
        return

    def stop(self,
        state: DownloadState = DownloadState.CANCELED_STATE
    ) -> None:
        self._state = state
        self._sleep_event.set()
        return

    def todict(self) -> Dict[str, Any]:
        return {
            **super().todict(),
            'client': self.external_client.id if self._external_client else None
        }

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}, {self.download_link}, {self.files[0]}>'
