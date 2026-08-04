# -*- coding: utf-8 -*-

from os import sep
from os.path import basename, join, splitext
from re import IGNORECASE, compile
from threading import Thread
from time import perf_counter
from typing import Any, Dict, List, Tuple, Union
from urllib.parse import unquote_plus

from requests import RequestException, Response

from backend.base.custom_exceptions import (DownloadLinkBroken,
                                            DownloadServiceRateLimitReached,
                                            IssueNotFound)
from backend.base.definitions import (Constants, Download,
                                      DownloadService, DownloadState)
from backend.base.helpers import Session
from backend.base.logging import LOGGER
from backend.implementations.naming import generate_issue_name
from backend.implementations.volumes import Volume
from backend.internals.server import QueueStatusEvent, WebSocket
from backend.internals.settings import Settings

# autopep8: off
file_extension_regex = compile(r'(?<=\.|\/)[\w\d]{2,4}(?=$|;|\s|\")', IGNORECASE)
file_name_regex = compile(r'filename(?:=\"|\*=UTF-8\'\')(.*?)\.[a-z]{2,4}\"?$', IGNORECASE)
DOWNLOAD_CHUNK_SIZE = 4194304 # 4MB Chunks
# autopep8: on


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
    def download_service(self) -> DownloadService:
        return self._download_service

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

        download_service: DownloadService,
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
        self._download_service = download_service
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
                self._ssn.close()

        except RequestException as e:
            if (
                e.response is not None
                and e.response.url.startswith(Constants.PIXELDRAIN_API_URL)
                and e.response.status_code == 403
            ):
                # Pixeldrain rate limit because of hotlinking
                # Note: Don't report rate limit because it's on the download
                #   and not the account.
                raise DownloadServiceRateLimitReached(
                    DownloadService.PIXELDRAIN
                )

            raise DownloadLinkBroken(download_link)

        self._size = int(response.headers.get('Content-Length', -1))
        self._supports_range_header = (
            response.headers.get('Accept-Ranges') == 'bytes'
        )

        self._filename_body = ''
        try:
            if isinstance(covered_issues, float):
                self._issue_id = volume.get_issue_from_number(covered_issues).id

            if settings.rename_downloaded_files:
                self._filename_body = generate_issue_name(
                    volume.get_data(),
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

    def _fetch_pure_link(self, start_byte: Union[int, None] = None) -> Response:
        headers = {}
        if start_byte is not None and self._supports_range_header:
            headers["Range"] = f"bytes={start_byte}-"

        return self._ssn.get(self.pure_link, headers=headers, stream=True)

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
        status_event = QueueStatusEvent(self)
        ws.emit(status_event)

        start_time = perf_counter()
        tries_left = Constants.TOTAL_RETRIES
        is_stopped = False
        with open(self.files[0], 'wb') as f:
            while tries_left > 0:
                tries_left -= 1
                if not self._supports_range_header:
                    size_downloaded = 0

                with self._fetch_pure_link(start_byte=size_downloaded) as r:
                    self.__r = r
                    try:
                        for chunk in r.iter_content(
                            chunk_size=DOWNLOAD_CHUNK_SIZE
                        ):
                            if self.state in (
                                DownloadState.CANCELED_STATE,
                                DownloadState.SHUTDOWN_STATE
                            ):
                                is_stopped = True
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
                            ws.emit(status_event)

                        else:
                            # Success
                            break

                        if is_stopped:
                            # Stopping download
                            break

                    except RequestException:
                        # Connection error, packet loss, etc. Just try again
                        pass

                    finally:
                        self.__r = None
            else:
                # Failed to download file
                self._state = DownloadState.FAILED_STATE

        if (
            not is_stopped
            and self.size != -1
            and size_downloaded != self.size
        ):
            # Download completed, but downloaded size is not equal
            # to reported size of file
            self._state = DownloadState.FAILED_STATE

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
            try:
                self.__r.raw._fp.fp.raw._sock.shutdown(2)  # SHUT_RDWR
            except OSError as e:
                if e.errno != 9:
                    raise
        return

    def as_dict(self) -> Dict[str, Any]:
        return {
            'id': self._id,
            'volume_id': self._volume_id,
            'issue_id': self._issue_id,

            'web_link': self._web_link,
            'web_title': self._web_title,
            'web_sub_title': self._web_sub_title,
            'download_link': self._download_link,
            'pure_link': self._pure_link,

            'download_service': self._download_service.value,
            'source_name': self._source_name,
            'type': self.identifier.value,

            'file': self._files[0],
            'title': self._title,
            'download_folder': self._download_folder,

            'size': self._size,
            'status': self._state.value,
            'progress': self._progress,
            'speed': self._speed
        }
