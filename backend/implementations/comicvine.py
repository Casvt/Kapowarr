# -*- coding: utf-8 -*-

"""
Search for volumes/issues and fetch metadata for them on ComicVine
"""

from asyncio import create_task, gather, run, sleep
from json import JSONDecodeError
from re import IGNORECASE, compile
from typing import Any, Dict, Iterable, List, Sequence, Union

from aiohttp import ContentTypeError
from aiohttp.client_exceptions import ClientError
from bs4 import BeautifulSoup, Tag

from backend.base.custom_exceptions import (CVRateLimitReached,
                                            InvalidComicVineApiKey,
                                            VolumeNotMatched)
from backend.base.definitions import (Constants, FilenameData, IssueMetadata,
                                      SpecialVersion, T, VolumeMetadata)
from backend.base.file_extraction import (process_issue_number,
                                          process_volume_number, volume_regex)
from backend.base.helpers import (AsyncSession, DictKeyedDict, Session,
                                  batched, create_range, force_suffix,
                                  normalize_string, normalize_year)
from backend.base.logging import LOGGER
from backend.implementations.matching import _match_title, _match_year
from backend.internals.db import get_db
from backend.internals.settings import Settings

translation_regex = compile(
    r'^<p>\s*\w+ publication(\.?</p>$|,\s| \(in the \w+ language\)|, translates )|' +
    r'^<p>\s*published by the \w+ wing of|' +
    r'^<p>\s*\w+ translations? of|' +
    r'from \w+</p>$|' +
    r'^<p>\s*published in \w+|' +
    r'^<p>\s*\w+ language|' +
    r'^<p>\s*\w+ edition of|' +
    r'^<p>\s*\w+ reprint of|' +
    r'^<p>\s*\w+ trade collection of',
    IGNORECASE)
headers = {'h2', 'h3', 'h4', 'h5', 'h6'}
lists = {'ul', 'ol'}


def _clean_description(description: str, short: bool = False) -> str:
    """Reduce size of description (written in html) to only essential
    information.

    Args:
        description (str): The description (written in html) to clean.
        short (bool, optional): Only remove images and fix links.
            Defaults to False.

    Returns:
        str: The cleaned description (written in html).
    """
    if not description:
        return description

    soup = BeautifulSoup(description, 'html.parser')

    # Remove images
    for el in soup.find_all(["figure", "img"]):
        el.decompose()

    if not short:
        # Remove everything after the first title with list
        removed_elements = []
        for el in soup:
            if not isinstance(el, Tag):
                continue
            if el.name is None:
                continue

            if (
                removed_elements
                or el.name in headers
            ):
                removed_elements.append(el)
                continue

            if el.name in lists:
                removed_elements.append(el)
                prev_sib = el.previous_sibling
                if (
                    prev_sib is not None
                    and prev_sib.text.endswith(':')
                ):
                    removed_elements.append(prev_sib)
                continue

            if el.name == 'p':
                children = list(getattr(el, 'children', []))
                if (
                    1 <= len(children) <= 2
                    and children[0].name in ('b', 'i', 'strong')
                ):
                    removed_elements.append(el)

        for el in removed_elements:
            if isinstance(el, Tag):
                el.decompose()

    # Fix links
    for link in soup.find_all('a'):
        link: Tag
        link.attrs = {
            k: v for k, v in link.attrs.items() if not k.startswith('data-')
        }
        link['target'] = '_blank'
        link['href'] = link.attrs.get('href', '').lstrip('.').lstrip('/')
        if not link.attrs.get('href', 'http').startswith('http'):
            link['href'] = (
                Constants.CV_SITE_URL
                + '/'
                + link.attrs.get('href', '')
            )

    result = str(soup)
    return result


def to_number_cv_id(ids: Iterable[Union[str, int]]) -> List[int]:
    """Convert CV ID's into numbers.

    Args:
        ids (Iterable[Union[str, int]]): CV ID's. Can have any common format,
        like 123, "123", "4050-123", "cv:123" and "cv:4050-123".

    Raises:
        VolumeNotMatched: Invalid CV ID.

    Returns:
        List[int]: The converted CV ID's, in format `NNNN`
    """
    result: List[int] = []
    for i in ids:
        if isinstance(i, int):
            result.append(i)
            continue

        if i.startswith('cv:'):
            i = i.partition(':')[2]

        if i.isdigit():
            result.append(int(i))

        elif i.startswith('4050-') and i.replace('-', '').isdigit():
            result.append(int(i.split('4050-')[-1]))

        else:
            raise VolumeNotMatched

    return result


def to_string_cv_id(ids: Iterable[Union[str, int]]) -> List[str]:
    """Convert CV ID's into short strings.

    Args:
        ids (Iterable[Union[str, int]]): CV ID's. Same formats supported as
        `to_number_cv_id()`.

    Returns:
        List[str]: The converted CV ID's, in format `"NNNN"`.
    """
    return [str(i) for i in to_number_cv_id(ids)]


def to_full_string_cv_id(ids: Iterable[Union[str, int]]) -> List[str]:
    """Convert CV ID's into long strings.

    Args:
        ids (Iterable[Union[str, int]]): CV ID's. Same formats supported as
        `to_number_cv_id()`.

    Returns:
        List[str]: The converted CV ID's, in format `"4050-NNNN"`.
    """
    return ["4050-" + str(i) for i in to_number_cv_id(ids)]


class ComicVine:

    volume_field_list = ','.join((
        'aliases',
        'count_of_issues',
        'deck',
        'description',
        'id',
        'image',
        'issues', #
        'name',
        'publisher',
        'site_detail_url',
        'start_year'
    ))
    issue_field_list = ','.join((
        'id',
        'issue_number',
        'name',
        'cover_date',
        'description',
        'volume'
    ))
    search_field_list = ','.join((
        'aliases',
        'count_of_issues',
        'deck',
        'description',
        'id',
        'image',
        'name',
        'publisher',
        'site_detail_url',
        'start_year'
    ))

    one_issue_match = (
        SpecialVersion.TPB,
        SpecialVersion.ONE_SHOT,
        SpecialVersion.HARD_COVER
    )
    """
    If a volume is one of these types, it can only match to CV search results
    with one issue.
    """

    def __init__(self, comicvine_api_key: Union[str, None] = None) -> None:
        """Start interacting with ComicVine.

        Args:
            comicvine_api_key (Union[str, None], optional): Override the API key
            that is used.
                Defaults to None.

        Raises:
            InvalidComicVineApiKey: No ComicVine API key is set in the settings.
        """
        self.api_url = Constants.CV_API_URL
        api_key = comicvine_api_key or Settings().sv.comicvine_api_key
        if not api_key:
            raise InvalidComicVineApiKey

        self.ssn = Session()
        self._params = {'format': 'json', 'api_key': api_key}
        self.ssn.params.update(self._params) # type: ignore
        return

    async def __call_request(
        self,
        session: AsyncSession,
        url: str
    ) -> Union[bytes, None]:
        """Fetch a URL and get it's content async (with error handling).

        Args:
            session (AsyncSession): The aiohttp session to make the request with.
            url (str): The URL to make the request to.

        Returns:
            Union[bytes, None]: The content in bytes.
                `None` in case of error.
        """
        try:
            return await session.get_content(url)
        except ClientError:
            return None

    async def __call_api(
        self,
        session: AsyncSession,
        url_path: str,
        params: Dict[str, Any] = {},
        default: Union[T, None] = None
    ) -> Union[Dict[str, Any], T]:
        """Make an CV API call asynchronously (with error handling).

        Args:
            session (AsyncSession): The aiohttp session to make the request with.

            url_path (str): The path of the url to make the call to (e.g.
            '/volumes').

            params (Dict[str, Any], optional): The URL params that should go
            with the request. Standard params (api key, format, etc.) not
            needed.
                Defaults to {}.

            default (Union[T, None], optional): Return value in case of error,
            instead of raising error.
                Defaults to None.

        Raises:
            CVRateLimitReached: The CV rate limit for this endpoint has been
            reached, and no `default` was supplied.
            InvalidComicVineApiKey: The CV api key is not valid.
            VolumeNotMatched: The volume with the given ID is not found.

        Returns:
            Union[Dict[str, Any], T]: The raw API response or the value of
            `default` on error.
        """
        url_path = force_suffix('/' + url_path.lstrip('/'), '/')

        try:
            response = await session.get(
                self.api_url + url_path,
                params={**self._params, **params}
            )
            result: Dict[str, Any] = await response.json()

            if result['status_code'] == 107:
                raise ClientError
            elif result['status_code'] == 101:
                raise VolumeNotMatched
            elif result['status_code'] == 100:
                raise InvalidComicVineApiKey

            return result

        except (ClientError, ContentTypeError, JSONDecodeError):
            if default is not None:
                return default
            raise CVRateLimitReached

    def __format_volume_output(
        self,
        volume_data: Dict[str, Any]
    ) -> VolumeMetadata:
        """Format the ComicVine API output containing the info
        about the volume.

        Args:
            volume_data (Dict[str, Any]): The ComicVine API output.

        Returns:
            VolumeMetadata: The formatted version.
        """
        result: VolumeMetadata = {
            'comicvine_id': int(volume_data['id']),
            'title': normalize_string(volume_data['name']),
            'year': normalize_year(volume_data.get('start_year', '')),
            'volume_number': 1,
            'cover_link': volume_data['image']['small_url'],
            'cover': None,
            'description': _clean_description(volume_data['description']),
            'site_url': volume_data['site_detail_url'],

            'aliases': [
                a
                for a in (volume_data.get('aliases') or '').split('\r\n')
                if a
            ],

            'publisher': (
                volume_data.get('publisher') or {}
            ).get('name'),

            'issue_count': int(volume_data['count_of_issues']),

            'translated': False,
            'already_added': None, # Only used when searching
            'issues': None # Only used for certain fetches
        }

        if translation_regex.match(
            result['description'] or ''
        ) is not None:
            result['translated'] = True

        volume_result = volume_regex.search(volume_data['deck'] or '')
        if volume_result:
            result['volume_number'] = create_range(process_volume_number(
                volume_result.group(1)
            ))[0] or 1

        return result

    def __format_issue_output(
        self,
        issue_data: Dict[str, Any]
    ) -> IssueMetadata:
        """Format the ComicVine API output containing the info
        about the issue.

        Args:
            issue_data (Dict[str, Any]): The ComicVine API output.

        Returns:
            VolumeMetadata: The formatted version.
        """
        cin = create_range(process_issue_number(
            issue_data['issue_number']
        ))[0]

        result: IssueMetadata = {
            'comicvine_id': int(issue_data['id']),
            'volume_id': int(issue_data['volume']['id']),
            'issue_number': issue_data['issue_number'],
            'calculated_issue_number': cin if cin is not None else 0.0,
            'title': issue_data['name'] or None,
            'date': issue_data['cover_date'] or None,
            'description': _clean_description(
                issue_data['description'],
                short=True
            )
        }
        return result

    def __format_search_output(
        self,
        search_results: List[Dict[str, Any]]
    ) -> List[VolumeMetadata]:
        """Format the search results from the ComicVine API.

        Args:
            search_results (List[Dict[str, Any]]): The unformatted search
            results.

        Returns:
            List[VolumeMetadata]: The formatted search results.
        """
        cursor = get_db()

        formatted_results = [
            self.__format_volume_output(r)
            for r in search_results
        ]

        # Mark entries that are already added
        volume_ids: Dict[int, int] = dict(cursor.execute(f"""
            SELECT comicvine_id, id
            FROM volumes
            WHERE {' OR '.join(
                'comicvine_id = ' + str(r['comicvine_id'])
                for r in formatted_results
            )}
            LIMIT 50;
        """))

        for r in formatted_results:
            r['already_added'] = volume_ids.get(r["comicvine_id"])

        LOGGER.debug(
            f'Searching for volumes with query result: {formatted_results}')
        return formatted_results

    def test_token(self) -> bool:
        """Test if the token works.

        Returns:
            bool: Whether the token works.
        """
        async def _test_token():
            try:
                async with AsyncSession() as session:
                    await self.__call_api(
                        session,
                        '/publisher/4010-31',
                        {'field_list': 'id'}
                    )

            except (CVRateLimitReached, InvalidComicVineApiKey):
                return False

            return True

        return run(_test_token())

    async def fetch_volume(self, cv_id: Union[str, int]) -> VolumeMetadata:
        """Get the metadata of a volume from ComicVine, including it's issues.

        Args:
            cv_id (Union[str, int]): The CV ID of the volume.

        Raises:
            VolumeNotMatched: No volume found with given ID in CV DB.
            CVRateLimitReached: The ComicVine rate limit is reached.

        Returns:
            VolumeMetadata: The metadata of the volume, including issues.
        """
        cv_id = to_full_string_cv_id((cv_id,))[0]
        LOGGER.debug(f'Fetching volume data for {cv_id}')

        async with AsyncSession() as session:
            result = await self.__call_api(
                session,
                f'/volume/{cv_id}',
                {'field_list': self.volume_field_list}
            )

            volume_info = self.__format_volume_output(result['results'])

            LOGGER.debug(f'Fetching issue data for volume {cv_id}')
            volume_info['issues'] = await self.fetch_issues((cv_id,))

            LOGGER.debug(f'Fetching volume data result: {volume_info}')

            volume_info['cover'] = await self.__call_request(
                session,
                volume_info['cover_link']
            )
            return volume_info

    async def fetch_volumes(
        self,
        cv_ids: Sequence[Union[str, int]]
    ) -> List[VolumeMetadata]:
        """Get the metadata of the volumes from ComicVine, without their issues.

        Args:
            cv_ids (Sequence[Union[str, int]]): The CV ID's of the volumes.

        Returns:
            List[VolumeMetadata]: The metadata of the volumes, without issues.
        """
        formatted_cv_ids = to_string_cv_id(cv_ids)
        LOGGER.debug(f'Fetching volume data for {formatted_cv_ids}')

        volume_infos = []
        async with AsyncSession() as session:
            # 10 requests of 100 vol per round
            for request_batch in batched(formatted_cv_ids, 1000):

                if request_batch[0] != formatted_cv_ids[0]:
                    # From second round on
                    LOGGER.debug(
                        f"Waiting {Constants.CV_BRAKE_TIME}s to keep the CV rate limit happy")
                    await sleep(Constants.CV_BRAKE_TIME)

                tasks = [
                    self.__call_api(
                        session,
                        '/volumes',
                        {
                            'field_list': self.volume_field_list,
                            'filter': f'id:{"|".join(id_batch)}'
                        },
                        {'results': []}
                    )
                    for id_batch in batched(request_batch, 100)
                ]
                responses = await gather(*tasks)

                cover_map: Dict[int, Any] = {}
                for batch in responses:
                    for result in batch['results']:
                        volume_info = self.__format_volume_output(result)
                        volume_infos.append(volume_info)

                        cover_map[volume_info['comicvine_id']] = self.__call_request(
                            session, volume_info['cover_link'])

                cover_responses = dict(zip(
                    cover_map.keys(),
                    await gather(*cover_map.values())
                ))
                for vi in volume_infos:
                    vi['cover'] = cover_responses.get(vi['comicvine_id'])

            return volume_infos

    async def fetch_issues(
        self,
        cv_ids: Sequence[Union[str, int]]
    ) -> List[IssueMetadata]:
        """Get the metadata of the issues of volumes from ComicVine.

        Args:
            ids (Sequence[Union[str, int]]): The CV ID's of the volumes.

        Returns:
            List[IssueMetadata]: The metadata of all the issues inside the
            volumes (assuming the rate limit wasn't reached).
        """
        formatted_cv_ids = to_string_cv_id(cv_ids)
        LOGGER.debug(f'Fetching issue data for volumes {formatted_cv_ids}')

        issue_infos = []
        async with AsyncSession() as session:
            for id_batch in batched(formatted_cv_ids, 50):
                try:
                    results = await self.__call_api(
                        session,
                        '/issues',
                        {'field_list': self.issue_field_list,
                        'filter': f'volume:{"|".join(id_batch)}'}
                    )

                except CVRateLimitReached:
                    break

                issue_infos += [
                    self.__format_issue_output(r)
                    for r in results['results']
                ]

                if results['number_of_total_results'] > 100:

                    for offset_batch in batched(
                        range(100, results['number_of_total_results'], 100),
                        10
                    ):

                        if offset_batch[0] != 100:
                            # From second round on
                            LOGGER.debug(
                                f"Waiting {Constants.CV_BRAKE_TIME}s to keep the CV rate limit happy")
                            await sleep(Constants.CV_BRAKE_TIME)

                        tasks = [
                            self.__call_api(
                                session,
                                '/issues',
                                {
                                    'field_list': self.issue_field_list,
                                    'filter': f'volume:{"|".join(id_batch)}',
                                    'offset': offset
                                },
                                {'results': []}
                            )
                            for offset in offset_batch
                        ]
                        responses = await gather(*tasks)

                        for batch in responses:
                            issue_infos += [
                                self.__format_issue_output(r)
                                for r in batch['results']
                            ]

            return issue_infos

    async def search_volumes(
        self,
        query: str
    ) -> List[VolumeMetadata]:
        """Search for volumes in CV.

        Args:
            query (str): The query to use when searching.

        Returns:
            List[VolumeMetadata]: A list with search results.
        """
        LOGGER.debug(f'Searching for volumes with the query {query}')

        try:
            if query.startswith(('4050-', 'cv:')):
                try:
                    query = to_full_string_cv_id((query,))[0]

                except VolumeNotMatched:
                    return []

                if not query:
                    return []

                async with AsyncSession() as session:
                    results = [(await self.__call_api(
                        session,
                        f'/volume/{query}',
                        {'field_list': self.search_field_list}
                    ))['results']]

            else:
                async with AsyncSession() as session:
                    results = (await self.__call_api(
                        session,
                        '/search',
                        {
                            'query': query,
                            'resources': 'volume',
                            'limit': 50,
                            'field_list': self.search_field_list
                        }
                    ))['results']

        except CVRateLimitReached:
            return []

        if not results or results == [[]]:
            return []

        return self.__format_search_output(results)

    async def filenames_to_cvs(self,
        file_datas: Sequence[FilenameData],
        only_english: bool
    ) -> DictKeyedDict:
        """Match filenames to CV volumes.

        Args:
            file_datas (Sequence[FilenameData]): The filename data's to find CV
            volumes for.
            only_english (bool): Only match to english volumes.

        Returns:
            DictKeyedDict: A map of the filename to it's CV match.
        """
        results = DictKeyedDict()

        # If multiple filenames have the same series title, avoid searching for
        # it multiple times. Instead search for all unique titles and then later
        # match the filename back to the title's search results. This makes it
        # one search PER SERIES TITLE instead of one search PER FILENAME.
        titles_to_files: Dict[str, List[FilenameData]] = {}
        for file_data in file_datas:
            (titles_to_files
                .setdefault(file_data['series'].lower(), [])
                .append(file_data)
            )

        # Titles to search results
        responses = await gather(*(
            self.search_volumes(title)
            for title in titles_to_files
        ))

        # Filter for each title: title, only_english
        titles_to_results: Dict[str, List[VolumeMetadata]] = {}
        for title, response in zip(titles_to_files, responses):
            titles_to_results[title] = [
                r for r in response
                if _match_title(title, r['title'])
                and (
                    only_english and not r['translated']
                    or
                    not only_english
                )
            ]

        for title, files in titles_to_files.items():
            for file in files:
                # Filter: SV - issue_count
                filtered_results = [
                    r for r in titles_to_results[title]
                    if file['special_version'] not in self.one_issue_match
                    or r['issue_count'] == 1
                ]

                if not filtered_results:
                    results[file] = {
                        'id': None,
                        'title': None,
                        'issue_count': None,
                        'link': None
                    }
                    continue

                # Pref: exact year (1 point, also matches fuzzy year),
                #       fuzzy year (1 point),
                #       volume number (2 points)
                filtered_results.sort(key=lambda r:
                    int(r['year'] == file['year'])
                    + int(_match_year(r['year'], file['year']))
                    + int(
                        file['volume_number'] is not None
                        and r['volume_number'] == file['volume_number']
                    ) * 2,
                    reverse=True
                )

                matched_result = filtered_results[0]
                results[file] = {
                    'id': matched_result['comicvine_id'],
                    'title': f"{matched_result['title']} ({matched_result['year']})",
                    'issue_count': matched_result['issue_count'],
                    'link': matched_result['site_url']}

        return results
