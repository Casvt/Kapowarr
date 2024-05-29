#-*- coding: utf-8 -*-

"""
General "helper" functions and classes
"""

from multiprocessing.pool import Pool
from os import symlink
from os.path import exists, join
from sys import base_exec_prefix, executable, platform, version_info
from threading import current_thread
from typing import (Any, Dict, Generator, Iterable, Iterator, List, Mapping,
                    Sequence, Tuple, TypedDict, TypeVar, Union)
from urllib.parse import unquote

from bencoding import bdecode

from backend.logging import LOGGER

T = TypeVar("T")
U = TypeVar("U")


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
			'The minimum python version required is python3.8 ' +
			'(currently ' + str(version_info.major) + '.' + str(version_info.minor) + '.' + str(version_info.micro) + ').'
		)
		return False
	return True


def get_python_exe() -> str:
	"""Get the path to the python executable.

	Returns:
		str: The python executable path.
	"""
	if platform.startswith('darwin'):
		bundle_path = join(base_exec_prefix, "Resources", "Python.app", "Contents", "MacOS", "Python")
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
		yield l[ndx : ndx+n]


def reversed_tuples(i: Iterable[Tuple[T, U]]) -> Generator[Tuple[U, T], Any, Any]:
	"""Yield sub-tuples in reversed order.

	Args:
		i (Iterable[Tuple[T, U]]): Iterator.

	Yields:
		Generator[Tuple[U, T], Any, Any]: Sub-tuple with reversed order.
	"""
	for entry_1, entry_2 in i:
		yield entry_2, entry_1


def get_first_of_range(
	n: Union[T, Sequence[T]]
) -> T:
	"""Get the first element from a variable that could potentially be a range,
	but could also be a single value. In the case of a single value, the value
	is returned.

	Args:
		n (Union[T, Sequence[T]]): The range or single value.

	Returns:
		T: The first element or single value.
	"""
	if isinstance(n, Sequence):
		return n[0]
	else:
		return n


def create_range(
	n: Union[T, Sequence[T]]
) -> Sequence[T]:
	"""Create range if input isn't already.

	Args:
		n (Union[T, Sequence[T]]): The value or range.

	Returns:
		Sequence[T]: The range.
	"""
	if isinstance(n, Sequence):
		return n
	else:
		return (n, n)


def normalize_string(s: str) -> str:
	"""Fix some common stuff in strings coming from online sources. Parses
	html escapes (`%20` -> ` `), fixing encoding errors (`_28` -> `(`), and
	replaces unicode chars by standard chars (`’` -> `'`).

	Args:
		s (str): Input string.

	Returns:
		str: Normilized string.
	"""
	return (unquote(s)
		.replace('_28','(')
		.replace('_29',')')
		.replace('–', '-')
		.replace('’', "'")
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


class CVFileMapping(TypedDict):
	id: int
	filepath: str


class DownloadGroup(TypedDict):
	web_sub_title: str
	info: FilenameData
	links: Dict[str, List[str]]


class ClientTestResult(TypedDict):
	success: bool
	description: Union[None, str]


class Singleton(type):
	_instances = {}
	def __call__(cls, *args, **kwargs):
		c = str(cls)
		if c not in cls._instances:
			cls._instances[c] = super().__call__(*args, **kwargs)

		return cls._instances[c]


class DB_ThreadSafeSingleton(type):
	_instances = {}
	def __call__(cls, *args, **kwargs):
		i = f'{cls}{current_thread()}'
		if (i not in cls._instances
		or cls._instances[i].closed):
			cls._instances[i] = super().__call__(*args, **kwargs)

		return cls._instances[i]


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
		if not key in self:
			self[key] = default

		return self[key]

	def __contains__(self, key: Mapping) -> bool:
		return super().__contains__(
			self.__convert_dict(key)
		)

	def keys(self) -> Iterator[Any]:
		return (v[0] for v in super().values())

	def values(self) -> Iterator[Any]:
		return (v[1] for v in super().values())

	def items(self) -> Iterator[Tuple[Any, Any]]:
		return zip(self.keys(), self.values())


class _ContextKeeper(metaclass=Singleton):
	def __init__(self, log_level: int) -> None:
		from backend.server import setup_process
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
	def __init__(self, processes = None) -> None:
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

	def apply_async(self, func, args = (), kwds = {}, callback = None, error_callback = None):
		new_args = (func, args)
		new_func = pool_apply_func
		return super().apply_async(new_func, new_args, kwds, callback, error_callback)

	def map(self, func, iterable, chunksize=None):
		new_iterable = ((func, i) for i in iterable)
		new_func = pool_map_func

		return super().map(new_func, new_iterable, chunksize)

	def imap(self, func, iterable, chunksize = 1):
		new_iterable = ((func, i) for i in iterable)
		new_func = pool_map_func
		return super().imap(new_func, new_iterable, chunksize)

	def imap_unordered(self, func, iterable, chunksize = 1):
		new_iterable = ((func, i) for i in iterable)
		new_func = pool_map_func
		return super().imap_unordered(new_func, new_iterable, chunksize)

	def map_async(self, func, iterable, chunksize = None, callback = None, error_callback = None):
		new_iterable = ((func, i) for i in iterable)
		new_func = pool_map_func
		return super().map_async(new_func, new_iterable, chunksize, callback, error_callback)

	def starmap(self, func, iterable, chunksize=None):
		new_iterable = ((func, *i) for i in iterable)
		new_func = pool_starmap_func
		return super().starmap(new_func, new_iterable, chunksize)

	def starmap_async(self, func, iterable, chunksize = None, callback = None, error_callback = None):
		new_iterable = ((func, *i) for i in iterable)
		new_func = pool_starmap_func
		return super().starmap_async(new_func, new_iterable, chunksize, callback, error_callback)
