# -*- coding: utf-8 -*-

from collections import OrderedDict
from datetime import datetime
from html import unescape
from typing import Any, Dict, List, Tuple, Union
from urllib.parse import unquote
from xml.etree import ElementTree

from requests import RequestException

from backend.base.custom_exceptions import ClientNotWorking, CredentialInvalid
from backend.base.definitions import (BrokenClientReason, DownloadType,
                                      IndexerClientField as ICF, QueryResult,
                                      SearchQuery, SearchResultData)
from backend.base.file_extraction import extract_filename_data
from backend.base.helpers import AsyncSession, Session
from backend.base.logging import LOGGER
from backend.implementations.indexer_client_manager import (BaseIndexerClient,
                                                            IndexerClients)

PAGE_SIZE = 100

NEWZNAB_NS = "{http://www.newznab.com/DTD/2010/feeds/attributes/}"

RECENT_TITLES: "OrderedDict[str, str]" = OrderedDict()
"""
NZB link -> release title of recent search results. The download prepper
only gets the link, and the NZB itself doesn't reliably contain the release
name (its meta name is often a raw usenet subject).
"""

NEWZNAB_AUTH_ERRORS = ("100", "101", "102")
"""
Newznab error codes for incorrect user credentials, account suspended and
insufficient privileges
"""


def _remember_title(link: str, title: str) -> None:
    "Remember the release title of an NZB link"
    RECENT_TITLES[link] = title
    RECENT_TITLES.move_to_end(link)
    while len(RECENT_TITLES) > 10_000:
        RECENT_TITLES.popitem(last=False)
    return


def _newznab_error(root: ElementTree.Element) -> Union[Tuple[str, str], None]:
    """Get the Newznab error in a response, if it is one.

    Args:
        root (Element): The root of the XML response.

    Returns:
        Union[Tuple[str, str], None]: The error code and description, or
            `None` if the response isn't an error.
    """
    if root.tag != 'error':
        return None
    return (root.get('code') or '', root.get('description') or '')


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

        _remember_title(link, title)

        return {
            **extract_filename_data(
                title,
                assume_volume_number=False,
                fix_year=True
            ),
            "link": link,
            "display_title": title,
            "size": parsed_size,
            "indexer_id": self._id,
            "indexer_title": self._title,
            "seeders": None,
            "leechers": None
        }

    async def _request(
        self,
        params: Dict[str, Any]
    ) -> Union[ElementTree.Element, None]:
        if not self.session:
            self.session = AsyncSession()

        text = await self.session.get_text(
            self._url + (self._api_path or ''),
            params={
                **params,
                'apikey': self._api_key or '',
                'cat': str(self._categories or [])
            },
            quiet_fail=True
        )
        if not text:
            return None

        root = ElementTree.XML(text)

        error = _newznab_error(root)
        if error:
            LOGGER.warning(
                f"Newznab indexer {self._title} returned error {error[0]}: "
                f"{error[1]}"
            )
            return None

        return root

    async def search(self, query: SearchQuery) -> QueryResult:
        offset = (query['page'] - 1) * PAGE_SIZE
        root = await self._request({
            't': 'search',
            'q': query['query'],
            'offset': offset,
            'limit': PAGE_SIZE,
            'extended': 1
        })
        if root is None:
            return QueryResult([], next_page_available=False)

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
        root = await self._request({
            't': 'search',
            'limit': PAGE_SIZE,
            'extended': 1,
            'q': ''
        })
        if root is None:
            return []

        formatted_results: List[SearchResultData] = []
        for item in root.iter("item"):
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
                # some indexers allow `t=caps` without (valid) API key.
                response = session.get(
                    url + (api_path or ''),
                    params={
                        't': 'search',
                        'q': 'test',
                        'limit': 1,
                        'apikey': api_key or '',
                        'cat': categories
                    }
                )

            except RequestException:
                raise ClientNotWorking(BrokenClientReason.CONNECTION_ERROR)

        if response.status_code in (401, 403):
            # E.g. Prowlarr answers a wrong API key with an empty 401
            raise CredentialInvalid

        if not response.ok:
            raise ClientNotWorking(
                BrokenClientReason.CONNECTION_ERROR
            )

        if response.headers["Content-Type"].split(";")[0] not in (
            "application/xml",
            "application/rss",
            "application/rss+xml"
        ):
            raise ClientNotWorking(
                BrokenClientReason.NOT_CLIENT_INSTANCE
            )

        root = ElementTree.XML(response.text)
        error = _newznab_error(root)
        if error:
            if error[0] in NEWZNAB_AUTH_ERRORS:
                raise CredentialInvalid
            LOGGER.error(
                f"Newznab indexer returned error {error[0]}: {error[1]}"
            )
            raise ClientNotWorking(
                BrokenClientReason.FAILED_PROCESSING_RESPONSE
            )

        if root.tag != 'rss':
            raise ClientNotWorking(BrokenClientReason.NOT_CLIENT_INSTANCE)
        return
