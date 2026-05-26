# -*- coding: utf-8 -*-

from base64 import b64decode
from re import IGNORECASE, compile
from typing import Union

from bs4 import BeautifulSoup, Tag
from requests import Response

from backend.base.custom_exceptions import DownloadLinkBroken
from backend.base.definitions import DownloadClientIdentifier
from backend.base.helpers import first_of_range
from backend.implementations.download_client_manager import DownloadClients
from backend.implementations.download_clients.base import BaseDirectDownload

# autopep8: off
extract_mediafire_regex = compile(r'window.location.href\s?=\s?\'https://download\d+\.mediafire.com/.*?(?=\')', IGNORECASE)
MEDIAFIRE_FOLDER_LINK = "https://www.mediafire.com/api/1.5/file/zip.php"
# autopep8: on


@DownloadClients.register_client(DownloadClientIdentifier.MEDIAFIRE)
class MediaFireDownload(BaseDirectDownload):
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
        if not isinstance(button, Tag):
            raise DownloadLinkBroken(self.download_link)

        href: str = first_of_range(button['href'])
        if href.startswith('http'):
            return href

        data_scrambled_url = button.get('data-scrambled-url')
        if data_scrambled_url:
            return b64decode(first_of_range(data_scrambled_url)).decode('utf-8')

        raise DownloadLinkBroken(self.download_link)


@DownloadClients.register_client(DownloadClientIdentifier.MEDIAFIRE_FOLDER)
class MediaFireFolderDownload(BaseDirectDownload):
    def _convert_to_pure_link(self) -> str:
        return self.download_link.split("/folder/")[1].split("/")[0]

    def _fetch_pure_link(self, start_byte: Union[int, None] = None) -> Response:
        headers = {}
        if start_byte is not None and self._supports_range_header:
            headers["Range"] = f"bytes={start_byte}-"

        return self._ssn.post(
            MEDIAFIRE_FOLDER_LINK,
            files={
                "keys": (None, self.pure_link),
                "meta_only": (None, "no"),
                "allow_large_download": (None, "yes"),
                "response_format": (None, "json")
            },
            headers=headers,
            stream=True
        )
