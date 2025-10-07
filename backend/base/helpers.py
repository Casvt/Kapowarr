# -*- coding: utf-8 -*-

"""
Generic functions and classes
"""

from __future__ import annotations

from asyncio import sleep
from base64 import urlsafe_b64encode
from collections import deque
from functools import lru_cache
from hashlib import pbkdf2_hmac
from multiprocessing.pool import Pool
from os import cpu_count, sep, symlink
from os.path import basename, dirname, exists, isfile, join
from sys import base_exec_prefix, executable, platform, version_info
from typing import (TYPE_CHECKING, Any, Callable, Collection, Dict, Iterable,
                    Iterator, List, Mapping, Sequence, Tuple, Union)
from urllib.parse import unquote

from aiohttp import ClientError, ClientSession, ClientTimeout
from bencoding import bdecode
from multidict import CIMultiDict, CIMultiDictProxy
from requests import Session as RSession
from requests.adapters import HTTPAdapter, Retry
from requests.structures import CaseInsensitiveDict
from urllib3 import __version__ as urllib3_version
from yarl import URL

from backend.base.definitions import Constants, T, U
from backend.base.logging import LOGGER, get_log_filepath

if TYPE_CHECKING:
    from multiprocessing import SimpleQueue
    from multiprocessing.pool import IMapIterator


# region Python
def get_python_version() -> str:
    """Get python version as string. E.g. `"3.8.10.final.0"`

    Returns:
        str: The python version.
    """
    return ".".join(
        str(i) for i in list(version_info)
    )


def check_min_python_version(
    min_major: int,
    min_minor: int,
    min_micro: int
) -> bool:
    """Check whether the version of Python that is used is equal or higher than
    the version given. Will log a critical error if not.

    ```
    # On Python3.9.1
    >>> check_min_python_version(3, 8, 2)
    True
    >>> check_min_python_version(3, 10, 0)
    False
    ```

    Args:
        min_major (int): The minimum major version.
        min_minor (int): The minimum minor version.
        min_micro (int): The miminum micro version.

    Returns:
        bool: Whether it's equal or higher than the version given or below it.
    """
    min_version = (
        min_major,
        min_minor,
        min_micro
    )
    current_version = (
        version_info.major,
        version_info.minor,
        version_info.micro
    )

    if current_version < min_version:
        LOGGER.critical(
            "The minimum python version required is python"
            + ".".join(map(str, min_version))
            + " (currently " + ".".join(map(str, current_version)) + ")."
        )
        return False

    return True


def get_python_exe() -> Union[str, None]:
    """Get the absolute filepath to the python executable.

    Returns:
        Union[str, None]: The python executable path, or `None` if not found.
    """
    if platform.startswith('darwin'):
        filepath = None
        bundle_path = join(
            base_exec_prefix,
            "Resources",
            "Python.app",
            "Contents",
            "MacOS",
            "Python"
        )
        if exists(bundle_path):
            from tempfile import mkdtemp
            filepath = join(mkdtemp(), "python")
            symlink(bundle_path, filepath)
    else:
        filepath = executable or None

    if filepath and not isfile(filepath):
        filepath = None

    return filepath


# region Helpers
def get_subclasses(
    *classes: type,
    include_self: bool = False,
    recursive: bool = True,
    only_leafs: bool = False
) -> List[type]:
    """Get subclasses of the given classes.

    Args:
        *classes (type): The classes to get subclasses from.

        include_self (bool, optional): Whether to include the classes themselves.
            Defaults to False.

        recursive (bool, optional): Whether to get all subclasses recursively.
            Defaults to True.

        only_leafs (bool, optional): Whether to only return leaf classes.
            Defaults to False.

    Returns:
        List[type]: The subclasses.
    """
    result: List[type] = []
    if include_self:
        result.extend(classes)

    if not recursive:
        result.extend((
            subclass
            for current in classes
            for subclass in current.__subclasses__()
        ))
        return result

    to_do = deque(classes)
    while to_do:
        current = to_do.popleft()
        subclasses = current.__subclasses__()
        if subclasses:
            to_do.extend(subclasses)
            if not only_leafs and current not in classes:
                result.append(current)
        else:
            result.append(current)

    return result


def check_filter(element: T, element_filter: Collection[T]) -> bool:
    """Check if `element` is in `element_filter`, but only if `element_filter`
    has content, otherwise return True. Useful for filtering where an empty
    filter is possible.

    ```
    >>> check_filter(2, [1, 2, 3])
    True
    >>> check_filter(4, [1, 2, 3])
    False
    >>> check_filter(2, [])
    True
    ```

    Args:
        element (T): The element to check for.
        element_filter (Collection[T]): The filter.
            If empty, True is returned.

    Returns:
        bool: Whether the element is in the filter if the filter has
            content, otherwise True.
    """
    return True if not element_filter else (element in element_filter)


def filtered_iter(
    elements: Iterable[T],
    element_filter: Collection[T]
) -> Iterator[T]:
    """Yields elements from `elements` but an element is only yielded if
    `element_filter` is empty or if the element is in `element_filter`. Useful
    for applying the filter `element_filter` to elements where an empty filter
    is possible.

    ```
    >>> list(filtered_iter([1, 2, 3, 4], [2, 4, 5]))
    [2, 4]
    >>> list(filtered_iter([1, 2, 3, 4], []))
    [1, 2, 3, 4]
    ```

    Args:
        elements (Iterable[T]): The elements to iterate over and yield.
        element_filter (Collection[T]): The filter. If empty, all elements of
            `elements` are returned.

    Yields:
        Iterator[T]: All elements in `elements` if `element_filter` is
            empty, otherwise only elements that are in `element_filter`.
    """
    if not element_filter:
        yield from elements
        return

    else:
        for el in elements:
            if el in element_filter:
                yield el
        return


def hash_password(salt: bytes, password: str) -> str:
    """Hash a password.

    Args:
        salt (bytes): The salt to use with the hash.
        password (str): The password the hash.

    Returns:
        str: The resulting hash.
    """
    return urlsafe_b64encode(
        pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    ).decode()


def get_torrent_info(torrent: bytes) -> Dict[bytes, Any]:
    """Get the info from the contents of a torrent file.

    Args:
        torrent (bytes): The contents of a torrent file.

    Returns:
        Dict[bytes, Any]: The info.
    """
    return bdecode(torrent)[b"info"] # type: ignore


# region Sequences
def batched(l: Sequence[T], n: int) -> Iterator[Sequence[T]]:
    """Iterate over `l` in batches.

    ```
    >>> list(batched([1, 2, 3, 4, 5, 6, 7], 2))
    [[1, 2], [3, 4], [5, 6], [7]]
    ```

    Args:
        l (Sequence[T]): The sequence to iterate over.
        n (int): The batch size.

    Yields:
        Iterator[Sequence[T]]: A batch of size `n` from `l`.
    """
    for ndx in range(0, len(l), n):
        yield l[ndx: ndx + n]


def first_of_range(
    n: Union[T, Tuple[T, ...], List[T]]
) -> T:
    """Get the first element from a variable that could potentially be a range,
    but could also be a single value. In the case of a single value, the value
    is returned.

    ```
    >>> first_of_range([1, 2])
    1
    >>> first_of_range(1)
    1
    ```

    Args:
        n (Union[T, Tuple[T, ...], List[T]]): The range or single value.

    Returns:
        T: The first element or single value.
    """
    if isinstance(n, (Tuple, List)):
        return n[0]
    else:
        return n


def first_of_subarrays(
    subarrays: Iterable[Sequence[T]]
) -> List[T]:
    """Get the first element of each sub-array.

    ```
    >>> first_of_subarrays([[1, 2], [3, 4]])
    [1, 3]
    ```

    Args:
        subarrays (Iterable[Sequence[T]]): List of sub-arrays.

    Returns:
        List[T]: List with first value of each sub-array.
    """
    return [e[0] for e in subarrays]


def force_range(
    n: Union[T, Tuple[T, ...], List[T]]
) -> Sequence[T]:
    """Create range if input isn't already.

    ```
    >>> force_range(1)
    (1, 1)
    >>> force_range([1, 2])
    [1, 2]
    ```

    Args:
        n (Union[T, Tuple[T, ...], List[T]]): The value or range.

    Returns:
        Sequence[T]: The range.
    """
    if isinstance(n, (Tuple, List)):
        return n
    else:
        return (n, n)

def get_list_numbers_concat(line_nums):
    seq = []
    final = []
    last = 0

    for index, val in enumerate(line_nums):

        if last + 1 == val or index == 0:
            seq.append(val)
            last = val
        else:
            if len(seq) > 1:
               final.append(str(seq[0]) + '-' + str(seq[len(seq)-1]))
            else:
               final.append(str(seq[0]))
            seq = []
            seq.append(val)
            last = val

        if index == len(line_nums) - 1:
            if len(seq) > 1:
                final.append(str(seq[0]) + '-' + str(seq[len(seq)-1]))
            else:
                final.append(str(seq[0]))

    final_str = ', '.join(map(str, final))
    return final_str


# region Strings
def force_prefix(source: str, prefix: str = sep) -> str:
    """Add `prefix` to the start of `source`,
    but only if it's not already there.

    ```
    >>> force_prefix('example.com', 'http://')
    'http://example.com'
    >>> force_prefix('http://example.com', 'http://')
    'http://example.com'
    ```

    Args:
        source (str): The string to process.
        prefix (str, optional): The prefix to apply.
            Defaults to `os.sep`.

    Returns:
        str: The resulting string with prefix applied.
    """
    if source.startswith(prefix):
        return source
    else:
        return prefix + source


def force_suffix(source: str, suffix: str = sep) -> str:
    """Add `suffix` to `source`, but only if it's not already there.

    ```
    >>> force_suffix('/path/to/folder')
    '/path/to/folder/'
    >>> force_suffix('example.com/index.html', '.html')
    'example.com/index.html'
    ```

    Args:
        source (str): The string to process.
        suffix (str, optional): The suffix to apply.
            Defaults to `os.sep`.

    Returns:
        str: The resulting string with suffix applied.
    """
    if source.endswith(suffix):
        return source
    else:
        return source + suffix


def normalise_string(s: str) -> str:
    """Fix some common stuff in strings coming from online sources. Parses
    html escapes (`%20` -> ` `), fixing encoding errors (`_28` -> `(`),
    removing surrounding whitespace and replaces unicode chars by standard
    chars (`’` -> `'`).

    Args:
        s (str): Input string.

    Returns:
        str: Normalised string.
    """
    return (unquote(s)
        .replace('_28', '(')
        .replace('_29', ')')
        .replace('–', '-')
        .replace('’', "'")
        .strip()
    )


def normalise_number(s: str) -> str:
    """Turn user-entered numbers (in string form) into more handable versions.
    Handles locale, unknown numbers, trailing chars, surrounding whitespace,
    etc.

    Args:
        s (str): Input string representing a(n) (issue) number.

    Returns:
        str: Normalised string.
    """
    return (s
        .replace(',', '.')
        .replace('?', '0')
        .rstrip('.')
        .strip()
        .lower()
    )


def normalise_year(s: str) -> Union[int, None]:
    """Turn user-entered years (in string form) into an int if possible.
    Handles unknown numbers, trailing chars, surrounding whitespace,
    etc.

    Args:
        s (str): Input string representing a year.

    Returns:
        Union[int, None]: The year, or None if it failed to convert the string.
    """
    if not s:
        return None

    s = (s
        .strip()
        .replace('-', '0')
        .replace(',', '/')
        .replace('?', '')
        .replace('>', '')
        .replace('<', '')
        .replace('+', '')
        .replace('.', '')
    )

    if '/' in s:
        for date_part in s.split('/'):
            if len(date_part) == 4:
                s = date_part
                break
        else:
            return None

    if s and s.isdigit():
        return int(s)
    return None


def normalise_base_url(base_url: str) -> str:
    """Turn user-entered base URL's into a standard format. No trailing slash,
    and `http://` prefix applied if no protocol is found.

    Args:
        base_url (str): Input base URL.

    Returns:
        str: Normalised base URL.
    """
    result = base_url.rstrip('/')
    if not result.startswith(("http://", "https://")):
        result = f"http://{result}"
    return result


def extract_year_from_date(
    date: Union[str, None],
    default: T = None
) -> Union[int, T]:
    """Get the year from a date in the format `YYYY-MM-DD`.

    Args:
        date (Union[str, None]): The date.
        default (T, optional): Value if year can't be extracted.
            Defaults to None.

    Returns:
        Union[int, T]: The year or the default value.
    """
    if date:
        try:
            return int(date.split('-')[0])
        except ValueError:
            return default
    else:
        return default


# region Numbers
def to_number_cv_id(ids: Iterable[Union[str, int]]) -> List[int]:
    """Convert CV IDs into numbers.

    Args:
        ids (Iterable[Union[str, int]]): CV IDs. Can have any common format,
            like `123`, `"123"`, `"4050-123"`, `"cv:123"` and `"cv:4050-123"`.

    Raises:
        ValueError: Invalid CV ID.

    Returns:
        List[int]: The converted CV IDs, in format `NNNN`.
    """
    result: List[int] = []
    for i in ids:
        if isinstance(i, int):
            result.append(i)
            continue

        if i.startswith("cv:"):
            i = i.partition(':')[2]

        if i.isdigit():
            result.append(int(i))

        elif i.startswith("4050-") and i.replace('-', '').isdigit():
            result.append(int(i.split("4050-")[-1]))

        else:
            raise ValueError(f"Unable to convert {i} to a CV ID number")

    return result


def to_string_cv_id(ids: Iterable[Union[str, int]]) -> List[str]:
    """Convert CV IDs into short strings.

    Args:
        ids (Iterable[Union[str, int]]): CV IDs. Can have any common format,
            like `123`, `"123"`, `"4050-123"`, `"cv:123"` and `"cv:4050-123"`.

    Raises:
        ValueError: Invalid CV ID.

    Returns:
        List[str]: The converted CV IDs, in format `"NNNN"`.
    """
    return [str(i) for i in to_number_cv_id(ids)]


def to_full_string_cv_id(ids: Iterable[Union[str, int]]) -> List[str]:
    """Convert CV IDs into long strings.

    Args:
        ids (Iterable[Union[str, int]]): CV IDs. Can have any common format,
            like `123`, `"123"`, `"4050-123"`, `"cv:123"` and `"cv:4050-123"`.

    Raises:
        ValueError: Invalid CV ID.

    Returns:
        List[str]: The converted CV IDs, in format `"4050-NNNN"`.
    """
    return ["4050-" + str(i) for i in to_number_cv_id(ids)]


def check_overlapping_issues(
    issues_1: Union[float, Tuple[float, float]],
    issues_2: Union[float, Tuple[float, float]]
) -> bool:
    """Check if two issues overlap. Both can be single issues or ranges.

    ```
    >>> check_overlapping_issues((1.5, 3.0), (3.1, 5.0))
    False
    >>> check_overlapping_issues((1.0, 3.0), (2.0, 4.0))
    True
    >>> check_overlapping_issues(3.0, (3.0, 4.0))
    True
    ```

    Args:
        issues_1 (Union[float, Tuple[float, float]]): First issue (range).
        issues_2 (Union[float, Tuple[float, float]]): Second issue (range).

    Returns:
        bool: Whether they overlap.
    """
    if isinstance(issues_1, (float, int)):
        if isinstance(issues_2, (float, int)):
            return issues_1 == issues_2
        else:
            return issues_2[0] <= issues_1 <= issues_2[1]
    else:
        if isinstance(issues_2, (float, int)):
            return issues_1[0] <= issues_2 <= issues_1[1]
        else:
            return (issues_1[0] <= issues_2[0] <= issues_1[1]
                or issues_1[0] <= issues_2[1] <= issues_1[1])


def check_overlapping_pos(
    established_positions: Sequence[Tuple[int, int]],
    check_positions: Tuple[int, int]
) -> bool:
    """Check whether a position range overlaps with existing position ranges.

    Args:
        established_positions (Sequence[Tuple[int, int]]): The existing position
            ranges.
        check_positions (Tuple[int, int]): The position range to check.

    Returns:
        bool: Whether they overlap.
    """
    return any(
        e_pos[0] <= check_positions[0] < e_pos[1]
        or e_pos[0] < check_positions[1] <= e_pos[1]
        for e_pos in established_positions
    )


def fix_year(year: int) -> int:
    """Fix year numbers that are probably a typo.

    ```
    >>> fix_year(1890)
    1980
    >>> fix_year(2010)
    2010
    >>> fix_year(2204)
    2024
    ```

    Args:
        year (int): The possibly broken year.

    Returns:
        int: The fixed year or input year if not broken.
    """
    if 1900 <= year < 2100:
        return year

    year_str = list(str(year))
    if len(year_str) != 4:
        return year

    return int(year_str[0] + year_str[2] + year_str[1] + year_str[3])


# region Helper Classes
class Singleton(type):
    """
    Make each initialisation of a class return the same instance by setting
    this as the metaclass. Works across threads, but not spawned subprocesses.
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        c_term = cls.__module__ + '.' + cls.__name__

        if c_term not in cls._instances:
            cls._instances[c_term] = super().__call__(*args, **kwargs)

        return cls._instances[c_term]


class CommaList(list):
    """
    Normal list but init can _also_ take a string with comma seperated values.
    Using str() will convert it back to a string with comma seperated values.

    ```
    >>> c = CommaList('blue,green,red')
    >>> c.append('purple')
    >>> str(c)
    'blue,green,red,purple'
    ```
    """

    def __init__(self, value: Union[str, Iterable]):
        """Create an instance.

        Args:
            value (Union[str, Iterable]): Either a string of comma-seperated
            values, or any other standard input to the `list` class.
        """
        if not isinstance(value, str):
            super().__init__(value)
            return

        if not value:
            super().__init__([])
        else:
            super().__init__(value.split(','))
        return

    def __str__(self) -> str:
        return ','.join(self)


class DictKeyedDict(dict):
    """
    Normal dict but key is dict.
    """

    def __convert_dict(self, key: Mapping) -> str:
        converted_key = ','.join(
            sorted(key.keys()) + sorted(map(str, key.values()))
        )
        return converted_key

    def __getitem__(self, key: Mapping) -> Any:
        return super().__getitem__(
            self.__convert_dict(key)
        )[1]

    def get(self, key: Mapping, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __setitem__(self, key: Mapping, value: Any) -> None:
        return super().__setitem__(
            self.__convert_dict(key),
            (key, value)
        )

    def setdefault(self, key: Mapping, default: Any = None) -> Any:
        if key not in self:
            self[key] = default

        return self[key]

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, Mapping):
            return False

        return super().__contains__(
            self.__convert_dict(key)
        )

    def keys(self) -> Iterator[Any]: # type: ignore
        return (v[0] for v in super().values())

    def values(self) -> Iterator[Any]: # type: ignore
        return (v[1] for v in super().values())

    def items(self) -> Iterator[Tuple[Any, Any]]: # type: ignore
        return zip(self.keys(), self.values())


# region Requests
@lru_cache(1)
def _running_urllib3_v2_and_above() -> bool:
    """Detect whether urllib3 version v2.0.0+ is used or not.

    Returns:
        bool: True if v2.0.0+ is used.
    """
    major_version = int(urllib3_version.lower().lstrip('v').split('.')[0])
    return major_version >= 2


def retry(
    total: int,
    method_whitelist: Collection[str],
    status_forcelist: Collection[int],
    backoff_factor: int
) -> Retry:
    """Create a urllib3 Retry object that is compatible with both
    urllib3 v1 and v2.

    Args:
        total (int): Total number of retries to allow.
        method_whitelist (Collection[str]): HTTP methods to retry on.
        status_forcelist (Collection[int]): HTTP status codes to force a retry.
        backoff_factor (int): The backoff factor to apply between attempts.

    Returns:
        Retry: A Retry object that can be used with requests.
    """
    if _running_urllib3_v2_and_above():
        return Retry(
            total=total,
            allowed_methods=frozenset(method_whitelist), # type: ignore
            status_forcelist=status_forcelist,
            backoff_factor=backoff_factor
        )
    else:
        return Retry(
            total=total,
            method_whitelist=frozenset(method_whitelist), # type: ignore
            status_forcelist=status_forcelist,
            backoff_factor=backoff_factor
        )


class Session(RSession):
    """
    Inherits from `requests.Session`. Adds retries, sets user agent and handles
    CloudFlare blockages using FlareSolverr.
    """

    def __init__(self) -> None:
        from backend.implementations.flaresolverr import FlareSolverr

        super().__init__()

        self.fs = FlareSolverr()

        retries = retry(
            total=Constants.TOTAL_RETRIES,
            method_whitelist=[],
            status_forcelist=Constants.STATUS_FORCELIST_RETRIES,
            backoff_factor=Constants.BACKOFF_FACTOR_RETRIES
        )
        self.mount("http://", HTTPAdapter(max_retries=retries))
        self.mount("https://", HTTPAdapter(max_retries=retries))

        self.headers.update({"User-Agent": Constants.DEFAULT_USERAGENT})

        return

    def request( # type: ignore
        self,
        method: str,
        url: str,
        params: Union[Dict[str, Any], None] = None,
        data: Union[list, dict, None] = None,
        headers: Union[Dict[str, str], None] = None,
        cookies=None, files=None, auth=None,
        timeout: Union[int, None] = Constants.REQUEST_TIMEOUT,
        allow_redirects=True,
        proxies=None, hooks=None,
        stream=None, verify=None,
        cert=None, json=None
    ):
        ua, cf_cookies = self.fs.get_ua_cookies(url)
        self.headers.update({"User-Agent": ua})
        self.cookies.update(cf_cookies)

        for round in range(1, 3):
            result = super().request(
                method, url, params, data, headers,
                cookies, files, auth,
                timeout, allow_redirects,
                proxies, hooks,
                stream, verify,
                cert, json
            )

            if (
                round == 1
                and result.status_code == 403
            ):
                fs_result = self.fs.handle_cf_block(result.url, result.headers)

                if not fs_result:
                    # FlareSolverr couldn't solve the problem or it wasn't
                    # needed
                    continue

                result.url = fs_result["url"]
                result.status_code = fs_result["status"]
                result._content = fs_result["response"].encode("utf-8")
                result.headers = CaseInsensitiveDict(fs_result["headers"])

            if 400 <= result.status_code < 500:
                LOGGER.warning(
                    "%s request to %s returned with code %d",
                    result.request.method,
                    result.request.url,
                    result.status_code
                )
                LOGGER.debug(
                    "Request response for %s %s: %s",
                    result.request.method,
                    result.request.url,
                    result.text
                )

            return result


class AsyncSession(ClientSession):
    """
    Inherits from `aiohttp.ClientSession`. Adds retries, sets user agent and
    handles CloudFlare blockages using FlareSolverr.
    """

    def __init__(self) -> None:
        from backend.implementations.flaresolverr import FlareSolverr

        super().__init__(
            headers={"User-Agent": Constants.DEFAULT_USERAGENT},
            timeout=ClientTimeout(
                connect=Constants.REQUEST_TIMEOUT,
                sock_read=Constants.REQUEST_TIMEOUT
            )
        )

        self.fs = FlareSolverr()

        return

    async def _request(self, *args, **kwargs):
        method, url = args[0], args[1]
        sleep_time = Constants.BACKOFF_FACTOR_RETRIES

        ua, cf_cookies = self.fs.get_ua_cookies(url)
        self.headers.update({"User-Agent": ua})
        self.cookie_jar.update_cookies(cf_cookies)

        for round in range(1, Constants.TOTAL_RETRIES + 1):
            try:
                response = await super()._request(*args, **kwargs)
                LOGGER.debug(
                    'Made async request: %s "%s" %d %d',
                    method, response.url,
                    response.status,
                    int(response.headers.get('Content-Length', -1))
                )

                if response.status in Constants.STATUS_FORCELIST_RETRIES:
                    raise ClientError

            except ClientError as e:
                if round == Constants.TOTAL_RETRIES:
                    # Exhausted retries
                    raise e

                LOGGER.warning(
                    "%s request failed for url %s. Retrying for round %d...",
                    method, url, round + 1
                )

                await sleep(sleep_time)
                sleep_time = (
                    Constants.BACKOFF_FACTOR_RETRIES *
                    (2 ** (round - 1))
                )
                continue

            if (
                round == 1
                and response.status == 403
            ):
                fs_result = await self.fs.handle_cf_block_async(
                    self, str(response.url), response.headers
                )

                if not fs_result:
                    # FlareSolverr couldn't solve the problem or it wasn't
                    # needed
                    continue

                response._url = URL(fs_result["url"])
                response.status = fs_result["status"]
                response._body = fs_result["response"].encode("utf-8")
                response._headers = CIMultiDictProxy(CIMultiDict(
                    fs_result["headers"]
                ))

            if 400 <= response.status < 500:
                LOGGER.warning(
                    "%s request to %s returned with code %d",
                    method, url, response.status
                )
                LOGGER.debug(
                    "Request response for %s %s: %s",
                    method, url, await response.text()
                )

            return response

        raise ClientError

    async def __aenter__(self):
        return self

    async def get_text(
        self,
        url: str,
        params: Dict[str, Any] = {},
        headers: Dict[str, Any] = {},
        quiet_fail: bool = False
    ) -> str:
        """Fetch a page and return the body.

        Args:
            url (str): The URL to fetch from.
            params (Dict[str, Any], optional): Any additional params.
                Defaults to {}.
            headers (Dict[str, Any], optional): Any additional headers.
                Defaults to {}.
            quiet_fail (bool, optional): If True, don't raise an exception
                if the request fails. Return an empty string instead.
                Defaults to False.

        Returns:
            str: The body of the response.
        """
        try:
            async with self.get(url, params=params, headers=headers) as response:
                return await response.text()

        except ClientError as e:
            if quiet_fail:
                return ''
            raise e

    async def get_content(
        self,
        url: str,
        params: Dict[str, Any] = {},
        headers: Dict[str, Any] = {},
        quiet_fail: bool = False
    ) -> bytes:
        """Fetch a page and return the content in bytes.

        Args:
            url (str): The URL to fetch from.
            params (Dict[str, Any], optional): Any additional params.
                Defaults to {}.
            headers (Dict[str, Any], optional): Any additional headers.
                Defaults to {}.
            quiet_fail (bool, optional): If True, don't raise an exception
                if the request fails. Return an empty bytestring instead.
                Defaults to False.

        Returns:
            bytes: The content of the response.
        """
        try:
            async with self.get(url, params=params, headers=headers) as response:
                return await response.content.read()

        except ClientError as e:
            if quiet_fail:
                return b''
            raise e


# region Multiprocessing
class _ContextKeeper(metaclass=Singleton):
    """
    Run inside newly spawned process to setup environment and offer a
    Flask application context
    """

    def __init__(
        self,
        log_level: Union[int, None] = None,
        log_folder: Union[str, None] = None,
        log_file: Union[str, None] = None,
        db_folder: Union[str, None] = None,
        ws_queue: Union[SimpleQueue[Dict[str, Any]], None] = None
    ) -> None:
        if not (log_level and ws_queue):
            return

        from backend.internals.server import setup_process
        self.ctx = setup_process(
            log_level, log_folder, log_file,
            db_folder,
            ws_queue
        )
        return


def pool_apply_func(args=(), kwds={}):
    func, value = args
    with _ContextKeeper().ctx():
        return func(*value, **kwds)


def pool_map_func(func_value):
    func, value = func_value
    with _ContextKeeper().ctx():
        return func(value)


def pool_starmap_func(func, *args):
    with _ContextKeeper().ctx():
        return func(*args)


class PortablePool(Pool):
    """
    A multiprocessing pool where the processes run in a proper environment.
    Stuff like logging, the database and websocket are set up, and everything
    is run inside a Flask application context.
    """

    def __init__(
        self,
        max_processes: Union[int, None] = None
    ) -> None:
        """Setup an instance.

        Args:
            max_processes (Union[int, None], optional): The amount of processes
                that the pool should manage. Given value is limited to CPU count.
                Give `None` for default, which is CPU count.
                Defaults to None.
        """
        from backend.internals.db import DBConnection
        from backend.internals.server import WebSocket

        log_file = get_log_filepath()
        super().__init__(
            processes=(
                min(cpu_count() or 1, max_processes)
                if max_processes is not None else
                None
            ),
            initializer=_ContextKeeper,
            initargs=(
                LOGGER.root.level,
                dirname(log_file),
                basename(log_file),
                dirname(DBConnection.file),
                WebSocket().client_manager.queue
            )
        )
        return

    def apply(
        self,
        func: Callable[..., U],
        args: Iterable[Any] = (),
        kwds: Mapping[str, Any] = {}
    ) -> U:
        new_args = (func, args)
        new_func = pool_apply_func
        return super().apply(new_func, new_args, kwds)

    def apply_async(
        self,
        func,
        args=(),
        kwds={},
        callback=None,
        error_callback=None
    ):
        new_args = (func, args)
        new_func = pool_apply_func
        return super().apply_async(
            new_func, new_args, kwds,
            callback, error_callback
        )

    def map(
        self,
        func: Callable[[T], U],
        iterable: Iterable[T],
        chunksize: Union[int, None] = None
    ) -> List[U]:
        new_iterable = ((func, i) for i in iterable)
        new_func = pool_map_func
        return super().map(new_func, new_iterable, chunksize)

    def imap(
        self,
        func: Callable[[T], U],
        iterable: Iterable[T],
        chunksize: Union[int, None] = 1
    ) -> IMapIterator[U]:
        new_iterable = ((func, i) for i in iterable)
        new_func = pool_map_func
        return super().imap(new_func, new_iterable, chunksize)

    def imap_unordered(
        self,
        func: Callable[[T], U],
        iterable: Iterable[T],
        chunksize: Union[int, None] = 1
    ) -> IMapIterator[U]:
        new_iterable = ((func, i) for i in iterable)
        new_func = pool_map_func
        return super().imap_unordered(new_func, new_iterable, chunksize)

    def map_async(
        self,
        func,
        iterable,
        chunksize=None,
        callback=None,
        error_callback=None
    ):
        new_iterable = ((func, i) for i in iterable)
        new_func = pool_map_func
        return super().map_async(
            new_func,
            new_iterable,
            chunksize,
            callback,
            error_callback
        )

    def starmap(
        self,
        func: Callable[..., U],
        iterable: Iterable[Iterable[T]],
        chunksize: Union[int, None] = None
    ) -> List[U]:
        new_iterable = ((func, *i) for i in iterable)
        new_func = pool_starmap_func
        return super().starmap(new_func, new_iterable, chunksize)

    def istarmap_unordered(
        self,
        func: Callable[..., U],
        iterable: Iterable[Iterable[T]],
        chunksize: Union[int, None] = 1
    ) -> IMapIterator[U]:
        "A combination of starmap and imap_unordered."
        new_iterable = ((func, i) for i in iterable)
        new_func = pool_apply_func
        return super().imap_unordered(new_func, new_iterable, chunksize)

    def starmap_async(
        self,
        func,
        iterable,
        chunksize=None,
        callback=None,
        error_callback=None
    ):
        new_iterable = ((func, *i) for i in iterable)
        new_func = pool_starmap_func
        return super().starmap_async(
            new_func,
            new_iterable,
            chunksize,
            callback,
            error_callback
        )
