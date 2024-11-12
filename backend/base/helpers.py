# -*- coding: utf-8 -*-

"""
General "helper" functions and classes
"""

from __future__ import annotations

from asyncio import sleep
from multiprocessing.pool import Pool
from os import sep, symlink
from os.path import exists, join
from sys import base_exec_prefix, executable, platform, version_info
from typing import (Any, Collection, Dict, Generator, Iterable,
                    Iterator, List, Mapping, Sequence, Tuple, Union)
from urllib.parse import unquote

from aiohttp import ClientError, ClientSession
from bencoding import bdecode
from requests import Session as RSession
from requests.adapters import HTTPAdapter, Retry

from backend.base.definitions import Constants, T, U
from backend.base.logging import LOGGER


def get_python_version() -> str:
    """Get python version as string

    Returns:
        str: The python version
    """
    return ".".join(
        str(i) for i in list(version_info)
    )


def check_python_version() -> bool:
    """Check if the python version that is used is a minimum version.

    Returns:
        bool: Whether or not the python version is version 3.8 or above or not.
    """
    if not (version_info.major == 3 and version_info.minor >= 8):
        LOGGER.critical(
            'The minimum python version required is python3.8 '
            '(currently '
            + str(version_info.major) + '.' + str(version_info.minor) + '.' + str(version_info.micro) + # noqa
            ').'
        ) # noqa
        return False
    return True


def get_python_exe() -> str:
    """Get the path to the python executable.

    Returns:
        str: The python executable path.
    """
    if platform.startswith('darwin'):
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
            python_path = join(mkdtemp(), "python")
            symlink(bundle_path, python_path)

            return python_path

    return executable


def batched(l: Sequence[T], n: int) -> Generator[Sequence[T], Any, Any]:
    """Iterate over l in batches.

    Args:
        l (Sequence[T]): The list to iterate over.
        n (int): The batch size.

    Yields:
        Generator[Sequence[T], Any, Any]: A batch of size n from l
    """
    for ndx in range(0, len(l), n):
        yield l[ndx: ndx + n]


def reversed_tuples(
    i: Iterable[Tuple[T, U]]
) -> Generator[Tuple[U, T], Any, Any]:
    """Yield sub-tuples in reversed order.

    Args:
        i (Iterable[Tuple[T, U]]): Iterator.

    Yields:
        Generator[Tuple[U, T], Any, Any]: Sub-tuple with reversed order.
    """
    for entry_1, entry_2 in i:
        yield entry_2, entry_1


def get_first_of_range(
    n: Union[T, Tuple[T, ...], List[T]]
) -> T:
    """Get the first element from a variable that could potentially be a range,
    but could also be a single value. In the case of a single value, the value
    is returned.

    Args:
        n (Union[T, Tuple[T, ...], List[T]]): The range or single value.

    Returns:
        T: The first element or single value.
    """
    if isinstance(n, (Tuple, List)):
        return n[0]
    else:
        return n


def create_range(
    n: Union[T, Tuple[T, ...], List[T]]
) -> Sequence[T]:
    """Create range if input isn't already.

    Args:
        n (Union[T, Tuple[T, ...], List[T]]): The value or range.

    Returns:
        Sequence[T]: The range.
    """
    if isinstance(n, (Tuple, List)):
        return n
    else:
        return (n, n)


def force_suffix(source: str, suffix: str = sep) -> str:
    """Add `suffix` to `source`, but only if it's not already there.

    Args:
        source (str): The string to process.
        suffix (str, optional): The suffix to apply. Defaults to sep.

    Returns:
        str: The resulting string with suffix applied.
    """
    if source.endswith(suffix):
        return source
    else:
        return source + suffix


def check_filter(element: T, collection: Collection[T]) -> bool:
    """Check if `element` is in `collection`, but only if `collection` has
    content, otherwise return True. Useful as filtering where an empty filter
    is possible.

    Args:
        element (T): The element to check for.
        collection (Collection[T]): The collection. If empty, True is returned.

    Returns:
        bool: Whether the element is in the collection if the collection has
        content, otherwise True.
    """
    return True if not collection else (element in collection)


def filtered_iter(
    elements: Iterable[T],
    collection: Collection[T]
) -> Generator[T, Any, Any]:
    """Yields elements from `elements` but an element is only yielded if
    `collection` is empty or if the element is in `collection`. Useful as
    applying the filter `collection` to elements where an empty filter is
    possible.

    Args:
        elements (Iterable[T]): The elements to iterate over and yield.
        collection (Collection[T]): The collection. If empty, all elements of
        `elements` are returned.

    Yields:
        Generator[T, Any, Any]: All elements in `elements` if `collection` is
        empty, otherwise only elements that are in `collection`.
    """
    for el in elements:
        if check_filter(el, collection):
            yield el
    return


def normalize_string(s: str) -> str:
    """Fix some common stuff in strings coming from online sources. Parses
    html escapes (`%20` -> ` `), fixing encoding errors (`_28` -> `(`),
    removing surrounding whitespace and replaces unicode chars by standard
    chars (`’` -> `'`).

    Args:
        s (str): Input string.

    Returns:
        str: Normilized string.
    """
    return (unquote(s)
        .replace('_28', '(')
        .replace('_29', ')')
        .replace('–', '-')
        .replace('’', "'")
        .strip()
    )


def normalize_number(s: str) -> str:
    """Turn user-entered numbers (in string form) into more handable versions.
    Handles locale, unknown numbers, trailing chars, surrounding whitespace,
    etc.

    Args:
        s (str): Input string representing a(n) (issue) number.

    Returns:
        str: Normilized string.
    """
    return (s
        .replace(',', '.')
        .replace('?', '0')
        .rstrip('.')
        .strip()
        .lower()
    )


def extract_year_from_date(
    date: Union[str, None],
    default: T = None
) -> Union[int, T]:
    """Get the year from a date in the format YYYY-MM-DD

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


def check_overlapping_issues(
    issues_1: Union[float, Tuple[float, float]],
    issues_2: Union[float, Tuple[float, float]]
) -> bool:
    """Check if two issues overlap. Both can be single issues or ranges.

    Args:
        issues_1 (Union[float, Tuple[float, float]]): First issue or range.
        issues_2 (Union[float, Tuple[float, float]]): Second issue or range.

    Returns:
        bool: Whether or not they overlap.
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


def first_of_column(
    columns: Iterable[Sequence[T]]
) -> List[T]:
    """Get the first element of each sub-array.

    Args:
        columns (Iterable[Sequence[T]]): List of sub-arrays.

    Returns:
        List[T]: List with first value of each sub-array.
    """
    return [e[0] for e in columns]


def fix_year(year: int) -> int:
    """Fix year numbers that are probably a typo.
    E.g. 2204 -> 2024, 1890 -> 1980, 2010 -> 2010

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


def get_torrent_info(torrent: bytes) -> Dict[bytes, Any]:
    """Get the info from the contents of a torrent file.

    Args:
        torrent (bytes): The contents of a torrent file.

    Returns:
        Dict[bytes, Any]: The info.
    """
    return bdecode(torrent)[b"info"] # type: ignore


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        c = str(cls)
        if c not in cls._instances:
            cls._instances[c] = super().__call__(*args, **kwargs)

        return cls._instances[c]


class CommaList(list):
    """
    Normal list but init can also take a string with comma seperated values:
        `'blue,green,red'` -> `['blue', 'green', 'red']`.
    Using str() will convert it back to a string with comma seperated values.
    """

    def __init__(self, value: Union[str, Iterable]):
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


class Session(RSession):
    """
    Inherits from `requests.Session`. Adds retries, sets user agent and handles
    CloudFlare blockages using FlareSolverr.
    """

    def __init__(self) -> None:
        from backend.implementations.flaresolverr import FlareSolverr

        super().__init__()

        self.fs = FlareSolverr()

        retries = Retry(
            total=Constants.TOTAL_RETRIES,
            backoff_factor=Constants.BACKOFF_FACTOR_RETRIES, # type: ignore
            status_forcelist=Constants.STATUS_FORCELIST_RETRIES
        )
        self.mount('http://', HTTPAdapter(max_retries=retries))
        self.mount('https://', HTTPAdapter(max_retries=retries))

        self.headers.update({'User-Agent': Constants.DEFAULT_USERAGENT})

        return

    def request( # type: ignore
        self,
        method, url: str,
        params=None, data=None, headers: Union[Dict[str, str], None] = None,
        cookies=None, files=None, auth=None,
        timeout=None, allow_redirects=True,
        proxies=None, hooks=None,
        stream=None, verify=None,
        cert=None, json=None
    ):
        for round in range(1, 3):
            ua, cf_cookies = self.fs.get_ua_cookies(url)
            self.headers.update({'User-Agent': ua})
            self.cookies.update(cf_cookies)

            result = super().request(
                method, url, params, data, headers, cookies, files, auth,
                timeout, allow_redirects, proxies, hooks, stream, verify, cert,
                json
            )

            if (
                round == 1
                and result.status_code == 403
            ):
                self.fs.handle_cf_block(url)
                continue

            if 400 <= result.status_code < 500:
                LOGGER.warning(
                    f"{result.request.method} request to {result.request.url} returned with code {result.status_code}"
                )
                LOGGER.debug(
                    f"Request response for {result.request.method} {result.request.url}: {result.text}"
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
            headers={'User-Agent': Constants.DEFAULT_USERAGENT}
        )

        self.fs = FlareSolverr()

        return

    async def _request(self, *args, **kwargs):
        sleep_time = Constants.BACKOFF_FACTOR_RETRIES
        for round in range(1, Constants.TOTAL_RETRIES + 1):
            ua, cf_cookies = self.fs.get_ua_cookies(args[1])
            self.headers.update({'User-Agent': ua})
            self.cookie_jar.update_cookies(cf_cookies)

            try:
                response = await super()._request(*args, **kwargs)

                if response.status in Constants.STATUS_FORCELIST_RETRIES:
                    raise ClientError

            except ClientError as e:
                if round == Constants.TOTAL_RETRIES:
                    raise e

                LOGGER.warning(
                    f"{args[0]} request failed for url {args[1]}. "
                    f"Retrying for round {round + 1}..."
                )

                await sleep(sleep_time)
                sleep_time *= 2
                continue

            if (
                round == 1
                and response.status == 403
            ):
                await self.fs.handle_cf_block_async(self, args[1])
                continue

            if response.status >= 400:
                LOGGER.warning(
                    f"{args[0]} request to {args[1]} returned with code {response.status}"
                )
                LOGGER.debug(
                    f"Request response for {args[0]} {args[1]}: %s", await response.text()
                )

            return response

        raise ClientError

    async def __aenter__(self) -> "AsyncSession":
        return self


class _ContextKeeper(metaclass=Singleton):
    def __init__(self, log_level: Union[int, None] = None) -> None:
        if not log_level:
            return

        from backend.internals.server import setup_process
        self.ctx = setup_process(log_level)
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
    def __init__(self, processes=None) -> None:
        super().__init__(
            processes=processes,
            initializer=_ContextKeeper,
            initargs=(LOGGER.root.level,)
        )
        return

    def apply(self, func, args=(), kwds={}):
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
        return super().apply_async(new_func, new_args, kwds, callback, error_callback)

    def map(self, func, iterable, chunksize=None):
        new_iterable = ((func, i) for i in iterable)
        new_func = pool_map_func

        return super().map(new_func, new_iterable, chunksize)

    def imap(self, func, iterable, chunksize=1):
        new_iterable = ((func, i) for i in iterable)
        new_func = pool_map_func
        return super().imap(new_func, new_iterable, chunksize)

    def imap_unordered(self, func, iterable, chunksize=1):
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

    def starmap(self, func, iterable, chunksize=None):
        new_iterable = ((func, *i) for i in iterable)
        new_func = pool_starmap_func
        return super().starmap(new_func, new_iterable, chunksize)

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
