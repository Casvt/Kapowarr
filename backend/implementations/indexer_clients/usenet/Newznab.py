# -*- coding: utf-8 -*-

from datetime import datetime
from html import unescape
from typing import Any, List, Union
from urllib.parse import unquote
from xml.etree import ElementTree

from requests import RequestException

from backend.base.custom_exceptions import ClientNotWorking, CredentialInvalid
from backend.base.definitions import (BrokenClientReason, DownloadType,
                                      IndexerClientField as ICF, QueryResult,
                                      SearchQuery, SearchResultData)
from backend.base.file_extraction import extract_filename_data
from backend.base.helpers import AsyncSession, Session
from backend.implementations.indexer_client_manager import (BaseIndexerClient,
                                                            IndexerClients)

PAGE_SIZE = 100

NEWZNAB_NS = "{http://www.newznab.com/DTD/2010/feeds/attributes/}"

NEWZNAB_AUTH_ERRORS = ("100", "101", "102")
"""
Newznab error codes for incorrect user credentials, account suspended and
insufficient privileges
"""


@IndexerClients.register_client(
    DownloadType.USENET, 'Newznab',
    (
        ICF.TITLE, ICF.ENABLED, ICF.URL,
        ICF.API_PATH, ICF.API_KEY, ICF.CATEGORIES
    ),
    allow_multiple_instances=True
)
class NewznabIndexer(BaseIndexerClient):
    def __init__(self, indexer_id: int) -> None:
        super().__init__(indexer_id)
        self.session: Union[AsyncSession, None] = None
        return

    def __process_item(
        self,
        item: ElementTree.Element
    ) -> Union[SearchResultData, None]:
        newznab_keys = {
            tor_key.attrib["name"].lower(): tor_key.attrib["value"]
            for tor_key in item.findall(f"{NEWZNAB_NS}attr")
            if "name" in tor_key.attrib and "value" in tor_key.attrib
        }

        # Title
        title = item.findtext("title")
        if not title:
            return None

        # Link
        link = item.findtext("link")
        enclosure = item.find("enclosure")
        if enclosure is not None and enclosure.get("url"):
            link = enclosure.get("url") or link
        if not link:
            return None
        link = unquote(unescape(link))

        comments = item.findtext("comments") or ""
        web_link = comments if comments.startswith("http") else None

        # Size
        size = newznab_keys.get("size", "")
        if (
            not size
            and enclosure is not None
            and enclosure.attrib.get("length")
        ):
            size = enclosure.attrib.get("length", "")
        if not size:
            size = item.findtext("size") or ""
        if size.isdigit():
            parsed_size = int(size)
        else:
            parsed_size = -1

        return {
            **extract_filename_data(
                title,
                assume_volume_number=False,
                fix_year=True
            ),
            "link": link,
            "web_link": web_link,
            "display_title": title,
            "size": parsed_size,
            "indexer_id": self._id,
            "indexer_title": self._title,
            "seeders": None,
            "leechers": None
        }

    async def search(self, query: SearchQuery) -> QueryResult:
        if not self.session:
            self.session = AsyncSession()

        offset = (query['page'] - 1) * PAGE_SIZE
        response = await self.session.get_text(
            self._url + (self._api_path or ''),
            params={
                't': 'search',
                'q': query['query'],
                'cat': str(self._categories or []),
                'offset': offset,
                'limit': PAGE_SIZE,
                'extended': 1,
                'apikey': self._api_key
            },
            quiet_fail=True
        )
        if not response:
            return QueryResult([], next_page_available=False)

        root = ElementTree.XML(response)
        channel = root.find('channel')
        if channel is None:
            return QueryResult([], next_page_available=False)

        response_offset, total = None, None
        response = channel.find(f'{NEWZNAB_NS}response')
        if response is not None:
            try:
                response_offset = int(response.get('offset') or 0)
                total = int(response.get('total') or 0)
            except ValueError:
                pass

        formatted_results: List[SearchResultData] = []
        result_count = 0
        for item in root.iter("item"):
            result_count += 1
            processed_item = self.__process_item(item)
            if processed_item is not None:
                formatted_results.append(processed_item)

        if total is not None:
            next_page_available = (
                (response_offset or offset) + result_count < total
            )
        else:
            next_page_available = result_count >= PAGE_SIZE

        return QueryResult(
            formatted_results,
            next_page_available=next_page_available
        )

    async def discover(self, last_check: datetime) -> List[SearchResultData]:
        if not self.session:
            self.session = AsyncSession()

        response = await self.session.get_text(
            self._url + (self._api_path or ''),
            params={
                't': 'search',
                'q': '',
                'cat': str(self._categories or []),
                'limit': PAGE_SIZE,
                'extended': 1,
                'apikey': self._api_key
            },
            quiet_fail=True
        )
        if not response:
            return []

        formatted_results: List[SearchResultData] = []
        for item in ElementTree.XML(response).iter("item"):
            processed_item = self.__process_item(item)
            if processed_item is None:
                continue

            date_el = item.find('pubDate')
            if date_el is None:
                continue
            date = date_el.text or ''
            if not date:
                continue
            parsed_date = (
                datetime
                .strptime(date, "%a, %d %b %Y %H:%M:%S %z")
                .replace(tzinfo=None)
            )
            if last_check > parsed_date:
                continue

            formatted_results.append(processed_item)

        return formatted_results

    async def shutdown(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None
        return

    @classmethod
    def test(cls, url: str, **extra_fields: Any) -> None:
        api_path: str = extra_fields[ICF.API_PATH.value]
        api_key: str = extra_fields[ICF.API_KEY.value]
        categories: str = extra_fields[ICF.CATEGORIES.value]

        with Session() as session:
            try:
                # Searching instead of asking for the capabilities, because
                # some indexers allow t=caps without (valid) API key.
                response = session.get(
                    url + (api_path or ''),
                    params={
                        't': 'search',
                        'q': 'test',
                        'cat': categories,
                        'limit': 1,
                        'apikey': api_key
                    }
                )

            except RequestException:
                raise ClientNotWorking(BrokenClientReason.CONNECTION_ERROR)

        if response.status_code in (401, 403):
            raise CredentialInvalid

        if not response.ok:
            raise ClientNotWorking(BrokenClientReason.CONNECTION_ERROR)

        if response.headers["Content-Type"].split(";")[0] not in (
            "application/xml",
            "application/rss",
            "application/rss+xml"
        ):
            raise ClientNotWorking(BrokenClientReason.NOT_CLIENT_INSTANCE)

        root = ElementTree.XML(response.text)
        if (
            root.tag == "error"
            and 100 <= int(root.attrib.get("code") or -1) <= 107
        ):
            raise CredentialInvalid

        if root.tag != 'rss':
            raise ClientNotWorking(BrokenClientReason.NOT_CLIENT_INSTANCE)

        return
