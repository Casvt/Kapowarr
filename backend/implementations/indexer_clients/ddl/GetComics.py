from asyncio import run, sleep
from datetime import datetime
from typing import List, Tuple, Union

from aiohttp import ClientError
from bs4 import BeautifulSoup, Tag

from backend.base.custom_exceptions import ClientNotWorking
from backend.base.definitions import (BrokenClientReason, DownloadType,
                                      IndexerClientField as ICF, QueryResult,
                                      SearchQuery, SearchResultData)
from backend.base.file_extraction import extract_filename_data
from backend.base.helpers import AsyncSession, first_of_range, normalise_size
from backend.implementations.indexer_client_manager import (BaseIndexerClient,
                                                            IndexerClients)

ENGLISH_MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December"
]


@IndexerClients.register_client(
    DownloadType.DDL, 'GetComics',
    (
        ICF.TITLE, ICF.ENABLED, ICF.URL,
        ICF.GC_SERVICE_PREFERENCE, ICF.GC_AVOID_LARGE_DOWNLOADS
    ),
    allow_multiple_instances=False
)
class GetComicsIndexer(BaseIndexerClient):
    def __init__(self, indexer_id: int) -> None:
        super().__init__(indexer_id)

        self.session: Union[AsyncSession, None] = None
        self.request_count = 0

        return

    @staticmethod
    def __get_articles(soup: BeautifulSoup) -> List[Tuple[str, str, int]]:
        """From a GC search result page, extract article (single search result)
        data.

        Args:
            soup (BeautifulSoup): The soup of the GC search result page.

        Returns:
            List[Tuple[str, str, int]]: The data of the articles. First string
                is the link, second string is the title, the integer is the byte
                size.
        """
        result: List[Tuple[str, str, int]] = []
        for article in soup.find_all("article", {"class": "post"}):
            title_el = article.find("h1", {"class": "post-title"})
            if not title_el:
                continue

            anchor = title_el.find('a')
            if not anchor:
                continue

            cat_el = article.find("a", {"class": "post-category"})
            if (
                not cat_el
                or cat_el.get_text(strip=True) in ("News", "Sponsored")
            ):
                continue

            title = title_el.get_text(strip=True)
            link: str = first_of_range(anchor.get('href') or '')

            size_container = title_el.next_sibling
            if not isinstance(size_container, Tag):
                size = -1
            else:
                size_p = next(size_container.children, None)
                if not size_p:
                    size = -1
                else:
                    split_size = size_p.get_text().split("Size : ")
                    if len(split_size) != 2:
                        size = -1
                    else:
                        size = normalise_size(split_size[1])

            result.append((link, title, size))

        return result

    async def search(self, query: SearchQuery) -> QueryResult:
        if not self.session:
            self.session = AsyncSession()

        next_page_available = False

        if self.request_count > 5:
            await sleep(1.0)

        page = await self.session.get_text(
            f"{self._url}/page/{query['page']}",
            params={"s": query["query"]},
            quiet_fail=True
        )
        self.request_count += 1
        if not page:
            return QueryResult([], next_page_available=False)

        soup = BeautifulSoup(page, "html.parser")

        page_links = soup.find_all(["a", "span"], {"class": "page-numbers"})
        if page_links and not (
            page_links[-1].name == "span"
            and "current" in (page_links[-1].get("class") or [])
        ):
            next_page_available = True

        # Process the search results on each page
        formatted_results: List[SearchResultData] = [
            {
                **extract_filename_data(
                    article[1],
                    assume_volume_number=False,
                    fix_year=True
                ),
                "link": article[0],
                "display_title": article[1],
                "size": article[2],
                "indexer_id": self._id,
                "indexer_title": self._title
            }
            for article in self.__get_articles(soup)
        ]

        return QueryResult(
            formatted_results,
            next_page_available=next_page_available
        )

    async def discover(self, last_check: datetime) -> List[SearchResultData]:
        if not self.session:
            self.session = AsyncSession()

        last_check = last_check.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )

        page = await self.session.get_text(
            f"{self._url}/sitemap/",
            quiet_fail=True
        )
        if not page:
            return []

        result: List[SearchResultData] = []
        soup = BeautifulSoup(page, "html.parser")
        for entry in soup.select(
            ".post-contents > div:first-of-type ul.lcp_catlist > li"
        ):
            strings = list(entry.stripped_strings)
            if len(strings) != 2:
                continue

            display_title, date = strings
            split_date = date.split()
            parsed_date = datetime(
                int(split_date[2]),
                ENGLISH_MONTHS.index(split_date[0]) + 1,
                int(split_date[1].strip(","))
            )
            if last_check > parsed_date:
                continue

            anchor = entry.find('a')
            if not anchor:
                continue

            link: str = first_of_range(anchor.get('href') or '')

            result.append({
                **extract_filename_data(
                    display_title,
                    assume_volume_number=False,
                    fix_year=True
                ),
                "link": link,
                "display_title": display_title,
                "size": -1,
                "indexer_id": self._id,
                "indexer_title": self._title
            })

        return result

    async def shutdown(self) -> None:
        if self.session:
            await self.session.close()
        return

    @classmethod
    async def __test(cls, url: str) -> None:
        async with AsyncSession() as session:
            try:
                html = await session.get_text(url)
                is_getcomics = "GetComics" in html

                if not is_getcomics:
                    raise ClientNotWorking(
                        BrokenClientReason.NOT_CLIENT_INSTANCE
                    )

            except ClientError:
                raise ClientNotWorking(
                    BrokenClientReason.CONNECTION_ERROR
                )

        return

    @classmethod
    def test(cls, url: str) -> None:
        run(cls.__test(url))
        return
