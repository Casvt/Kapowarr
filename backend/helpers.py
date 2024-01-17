#-*- coding: utf-8 -*-

"""
General "helper" functions and classes
"""

from __future__ import annotations

import logging
from sys import version_info
from threading import current_thread
from typing import TYPE_CHECKING, Iterable, List, Tuple, TypeVar, Union

from flask_socketio import SocketIO

from backend.enums import SocketEvent

if TYPE_CHECKING:
	from backend.tasks import Task
	from backend.download_general import Download

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
		logging.critical(
			'The minimum python version required is python3.8 ' + 
			'(currently ' + version_info.major + '.' + version_info.minor + '.' + version_info.micro + ').'
		)
		return False
	return True

def batched(l: list, n: int):
	"""Iterate over list (or tuple, set, etc.) in batches

	Args:
		l (list): The list to iterate over
		n (int): The batch size

	Yields:
		A batch of size n from l
	"""
	for ndx in range(0, len(l), n):
		yield l[ndx : ndx+n]

def reversed_tuples(i: Tuple[Tuple[T, U]]) -> Tuple[Tuple[U, T]]:
	"""Yield sub-tuples in reversed order.

	Args:
		i (Tuple[Tuple[T, U]]): Iterator.

	Yields:
		Iterator[Tuple[Tuple[U, T]]]: Sub-tuple with reversed order.
	"""
	for entry_1, entry_2 in i:
		yield entry_2, entry_1

def get_first_of_range(
	n: Union[T, Tuple[T, T], List[T]]
) -> T:
	"""Get the first element from a variable that could potentially be a range,
	but could also be a single value. In the case of a single value, the value
	is returned.

	Args:
		n (Union[T, Tuple[T, T], List[T]]): The range or single value.

	Returns:
		T: The first element or single value.
	"""
	if isinstance(n, (list, tuple)):
		return n[0]
	else:
		return n

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

def first_of_column(
	columns: Tuple[Tuple[T]]
) -> List[T]:
	"""Get the first element of each sub-array.

	Args:
		columns (Tuple[Tuple[T]]): List of sub-arrays.

	Returns:
		List[T]: List with first value of each sub-array.
	"""
	return [e[0] for e in columns]

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

# It's more logical to have this class in the server.py file,
# but then we have an import loop so this is the second-best file...
class WebSocket(SocketIO, metaclass=Singleton):
	def request_disconnect(self) -> None:
		"Request the clients to disconnect"
		self.emit(
			SocketEvent.DISCONNECT.value
		)
		return

	def send_task_added(self, task: Task) -> None:
		"""Send a message stating a task that has been added
		to the queue.

		Args:
			task (Task): The task that has been added.
		"""
		self.emit(
			SocketEvent.TASK_ADDED.value,
			{
				'action': task.action,
				'volume_id': task.volume_id,
				'issue_id': task.issue_id
			}
		)
		return

	def send_task_ended(self, task: Task) -> None:
		"""Send a message stating a task that has been removed
		from the queue. Either because it's finished or canceled.

		Args:
			task (Task): The task that has been removed.
		"""
		self.emit(
			SocketEvent.TASK_ENDED.value,
			{
				'action': task.action,
				'volume_id': task.volume_id,
				'issue_id': task.issue_id
			}
		)
		return

	def update_task_status(self, task: Task) -> None:
		"""Send a message with the new task queue status.

		Args:
			task (Task): The task instance to send the status of.
		"""
		self.emit(
			SocketEvent.TASK_STATUS.value,
			{
				'message': task.message
			}
		)
		return

	def send_queue_added(self, download: Download) -> None:
		"""Send a message stating a download that has been added
		to the queue.

		Args:
			download (Download): The download that has been added.
		"""
		self.emit(
			SocketEvent.QUEUE_ADDED.value,
			{
				'id': download.id,
				'status': download.state.value,
				'title': download.title,
				'page_link': download.page_link,
				'source': download.source,
				'size': download.size,
				'speed': download.speed,
				'progress': download.progress
			}
		)
		return

	def send_queue_ended(self, download: Download) -> None:
		"""Send a message stating a download that has been removed
		from the queue. Either because it's finished or canceled.

		Args:
			download (Download): The download that has been removed.
		"""
		self.emit(
			SocketEvent.QUEUE_ENDED.value,
			{
				'id': download.id
			}
		)
		return

	def update_queue_status(self, download: Download) -> None:
		"""Send a message with the new download queue status.

		Args:
			download (Download): The download instance to send the status of.
		"""
		self.emit(
			SocketEvent.QUEUE_STATUS.value,
			{
				'id': download.id,
				'status': download.state.value,
				'size': download.size,
				'speed': download.speed,
				'progress': download.progress
			}
		)
		return

