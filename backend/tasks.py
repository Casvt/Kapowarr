#-*- coding: utf-8 -*-

"""This file contains functions regarding background tasks
"""

import logging
from abc import ABC, abstractmethod
from threading import Thread, Timer
from time import sleep, time
from typing import Dict, List, Union

from backend.custom_exceptions import (InvalidComicVineApiKey,
                                       TaskNotDeletable, TaskNotFound)
from backend.db import get_db
from backend.download import DownloadHandler
from backend.post_processing import unzip_volume
from backend.search import auto_search
from backend.volumes import refresh_and_scan


class Task(ABC):
	@property
	@abstractmethod
	def stop(self) -> bool:
		return
	
	@property
	@abstractmethod
	def message(self) -> str:
		return

	@property
	@abstractmethod
	def action(self) -> str:
		return

	@property
	@abstractmethod
	def display_title(self) -> str:
		return

	@property
	@abstractmethod
	def category(self) -> str:
		return

	@property
	@abstractmethod
	def volume_id(self) -> int:
		return
	
	@property
	@abstractmethod
	def issue_id(self) -> int:
		return

	@abstractmethod
	def run(self) -> Union[None, List[tuple]]:
		"""Run the task

		Returns:
			Union[None, List[tuple]]: Either `None` if the task has no result or 
			`List[tuple]` if the task returns search results.
		"""
		return

#=====================
# Issue tasks
#=====================
class AutoSearchIssue(Task):
	"""Do an automatic search for an issue
	"""	
	stop = False
	message = ''
	action = 'auto_search_issue'
	display_title = 'Auto Search'
	category = 'download'
	volume_id = None
	issue_id = None
	
	def __init__(self, volume_id: int, issue_id: int):
		"""Create the task

		Args:
			volume_id (int): The id of the volume in which the issue is
			issue_id (int): The id of the issue to search for
		"""
		self.volume_id = volume_id
		self.issue_id = issue_id
	
	def run(self) -> List[tuple]:
		title = get_db().execute(
			"""
			SELECT
				v.title, i.issue_number
			FROM volumes v
			INNER JOIN issues i
			ON i.volume_id = v.id
			WHERE i.id = ?
			LIMIT 1;
			""",
			(self.issue_id,)
		).fetchone()
		self.message = f'Searching for {title[0]} #{title[1]}'

		# Get search results and download them
		results = auto_search(self.volume_id, self.issue_id)
		if results:
			return [(result['link'], self.volume_id, self.issue_id) for result in results]
		return []

#=====================
# Volume tasks
#=====================
class AutoSearchVolume(Task):
	"""Do an automatic search for a volume
	"""
	stop = False
	message = ''
	action = 'auto_search'
	display_title = 'Auto Search'
	category = 'download'
	volume_id = None
	issue_id = None
	
	def __init__(self, volume_id: int):
		"""Create the task

		Args:
			volume_id (int): The id of the volume to search for
		"""
		self.volume_id = volume_id
	
	def run(self) -> List[tuple]:
		title = get_db().execute(
			"SELECT title FROM volumes WHERE id = ? LIMIT 1",
			(self.volume_id,)
		).fetchone()[0]
		self.message = f'Searching for {title}'

		# Get search results and download them
		results = auto_search(self.volume_id)
		if results:
			return [(result['link'], self.volume_id) for result in results]
		return []

class RefreshAndScanVolume(Task):
	"""Trigger a refresh and scan for a volume
	"""
	stop = False
	message = ''
	action = 'refresh_and_scan'
	display_title = 'Refresh And Scan'
	category = ''
	volume_id = None
	issue_id = None
	
	def __init__(self, volume_id: int):
		"""Create the task

		Args:
			volume_id (int): The id of the volume for which to perform the task
		"""		
		self.volume_id = volume_id

	def run(self) -> None:
		title = get_db().execute(
			"SELECT title FROM volumes WHERE id = ? LIMIT 1", 
			(self.volume_id,)
		).fetchone()[0]
		self.message = f'Updating info on {title}'

		try:
			refresh_and_scan(self.volume_id)
		except InvalidComicVineApiKey:
			pass

		return

class Unzip(Task):
	"""Unzip all zip files for a volume
	"""
	stop = False
	message = ''
	action = 'unzip'
	display_title = 'Unzip'
	category = ''
	volume_id = None
	issue_id = None
	
	def __init__(self, volume_id: int):
		"""Create the task

		Args:
			volume_id (int): The id of the volume for which to perform the task
		"""
		self.volume_id = volume_id
		
	def run(self) -> None:
		title = get_db().execute(
			"SELECT title FROM volumes WHERE id = ? LIMIT 1;",
			(self.volume_id,)
		).fetchone()[0]
		self.message = f'Unzipping for {title}'
		
		unzip_volume(self.volume_id)
		return

#=====================
# Library tasks
#=====================
class UpdateAll(Task):
	"""Trigger a refresh and scan for each volume in the library
	"""
	stop = False
	message = ''
	action = 'update_all'
	display_title = 'Update All'
	category = ''
	volume_id = None
	issue_id = None

	def run(self) -> None:
		self.message = f'Updating info on all volumes'
		try:
			refresh_and_scan()
		except InvalidComicVineApiKey:
			pass

		return

class SearchAll(Task):
	"""Trigger an automatic search for each volume in the library
	"""	
	stop = False
	message = ''
	action = 'search_all'
	display_title = 'Search All'
	category = 'download'
	volume_id = None
	issue_id = None

	def run(self) -> List[tuple]:
		cursor = get_db(temp=True)
		cursor.execute(
			"SELECT id, title FROM volumes WHERE monitored = 1;"
		)
		downloads = []
		for volume_id, volume_title in cursor:
			if self.stop: break
			self.message = f'Searching for {volume_title}'
			# Get search results and download them
			results = auto_search(volume_id)
			if results:
				downloads += [(result['link'], volume_id) for result in results]
		cursor.connection.close()
		return downloads

#=====================
# Task handling
#=====================
# Maps action attr to class for all tasks
# Only works for classes that directly inherit from Task
task_library: Dict[str, Task] = {c.action: c for c in Task.__subclasses__()}

class TaskHandler:
	"""For handling tasks
	"""	
	queue: List[dict] = []
	task_interval_waiter: Timer = None
	def __init__(self, context, download_handler: DownloadHandler) -> None:
		"""Setup the handler

		Args:
			context (Flask): A Flask app instance
			download_handler (DownloadHandler): An instance of the `download.DownloadHandler` class
			to which any download instructions are sent
		"""
		self.context = context.app_context
		self.download_handler = download_handler
		return

	def __run_task(self, task: Task) -> None:
		"""Run a task

		Args:
			task (Task): The task to run
		"""
		logging.debug(f'Running task {task.display_title}')
		with self.context():
			try:
				result = task.run()

				# Note in history
				get_db().execute(
					"INSERT INTO task_history VALUES (?,?,?);",
					(task.action, task.display_title, round(time()))
				)

				if not task.stop:
					if task.category == 'download':
						for download in result:
							self.download_handler.add(*download)

					logging.info(f'Finished task {task.display_title}')

			except Exception:
				logging.exception('An error occured while trying to run a task: ')
				task.message = 'AN ERROR OCCURED'
				sleep(1.5)

			finally:
				if not task.stop:
					self.queue.pop(0)
					self._process_queue()

		return
		
	def _process_queue(self) -> None:
		"""Handle the queue. In the case that there is something in the queue and it isn't already running,
		start the task. This can safely be called multiple times while a task is going or while there is
		nothing in the queue.
		"""
		if not self.queue:
			return

		first_entry = self.queue[0]
		if first_entry['status'] != 'running':
			first_entry['status'] = 'running'
			first_entry['thread'].start()
		return

	def add(self, task: Task) -> int:
		"""Add a task to the queue

		Args:
			task (Task): The task to add to the queue

		Returns:
			int: The id of the entry in the queue
		"""
		logging.debug(f'Adding task to queue: {task.display_title}')
		id = self.queue[-1]['id'] + 1 if self.queue else 1
		task_data = {
			'task': task,
			'id': id,
			'status': 'queued',
			'thread': Thread(target=self.__run_task, args=(task,), name="Task Handler")
		}
		self.queue.append(task_data)
		logging.info(f'Added task: {task.display_title} ({id})')
		self._process_queue()
		return id

	def __check_intervals(self)	-> None:
		"""Check if any interval task needs to be run and add to queue if so
		"""
		logging.debug('Checking task intervals')
		with self.context():
			current_time = time()

			cursor = get_db('dict')
			interval_tasks = cursor.execute(
				"SELECT task_name, interval, next_run FROM task_intervals;"
			).fetchall()
			logging.debug(f'Task intervals: {list(map(dict, interval_tasks))}')
			for task in interval_tasks:
				if task['next_run'] <= current_time:
					# Add task to queue
					task_class = task_library[task['task_name']]
					self.add(task_class())
					
					# Update next_run
					next_run = round(current_time + task['interval'])
					cursor.execute(
						"UPDATE task_intervals SET next_run = ? WHERE task_name = ?;",
						(next_run, task['task_name'])
					)

		self.handle_intervals()
		return

	def handle_intervals(self) -> None:
		"""Find next time an interval task needs to be run
		"""
		with self.context():
			next_run = get_db().execute(
				"SELECT MIN(next_run) FROM task_intervals"
			).fetchone()[0]
		timedelta = next_run - round(time()) + 1
		logging.debug(f'Next interval task is in {timedelta} seconds')
		
		# Create sleep thread for that time and that will run self.__check_intervals.
		self.task_interval_waiter = Timer(timedelta, self.__check_intervals)
		self.task_interval_waiter.start()
		return
	
	def stop_handle(self) -> None:
		"""Stop the task handler
		"""		
		logging.debug('Stopping task thread')
		self.task_interval_waiter.cancel()
		if self.queue:
			self.queue[0]['task'].stop = True
			self.queue[0]['thread'].join()
		return
	
	def __format_entry(self, task: dict) -> dict:
		"""Format a queue entry for API response

		Args:
			t (dict): The queue entry

		Returns:
			dict: The formatted queue entry
		"""
		return {
			'id': task['id'],
			'action': task['task'].action,
			'display_title': task['task'].display_title,
			'status': task['status'],
			'message': task['task'].message,
			'volume_id': task['task'].volume_id,
			'issue_id': task['task'].issue_id
		}

	def get_all(self) -> List[dict]:
		"""Get all tasks in the queue

		Returns:
			List[dict]: A list with all tasks in the queue (formatted using `self.__format_entry()`)
		"""		
		return [self.__format_entry(t) for t in self.queue]

	def get_one(self, task_id: int) -> dict:
		"""Get one task from the queue based on it's id

		Args:
			task_id (int): The id of the task to get from the queue

		Raises:
			TaskNotFound: The id doesn't match with any task in the queue

		Returns:
			dict: The info of the task in the queue (formatted using `self.__format_entry()`)
		"""
		for entry in self.queue:
			if entry['id'] == task_id:
				return self.__format_entry(entry)
		raise TaskNotFound

	def remove(self, task_id: int) -> None:
		"""Remove a task from the queue

		Args:
			task_id (int): The id of the task to delete from the queue

		Raises:
			TaskNotDeletable: The task is not allowed to be deleted from the queue
			TaskNotFound: The id doesn't map to any task in the queue
		"""
		# Get task and check if id exists
		# Raises TaskNotFound if the id isn't found
		task = self.get_one(task_id)
		
		# Check if task is allowed to be deleted
		if self.queue[0] == task:
			raise TaskNotDeletable

		task['task'].stop = True
		task['thread'].join()
		self.queue.remove(task)
		logging.info(f'Removed task: {task["task"].display_name} ({task_id})')
		return

def get_task_history(offset: int=0) -> List[dict]:
	"""Get the task history in blocks of 50.

	Args:
		offset (int, optional): The offset of the list. The higher the number, the deeper into history you go. Defaults to 0.

	Returns:
		List[dict]: The history entries.
	"""	
	result = list(map(
		dict,
		get_db('dict').execute(
			"""
			SELECT
				task_name, display_title, run_at
			FROM task_history
			ORDER BY run_at DESC
			LIMIT 50
			OFFSET ?;
			""",
			(offset * 50,)
		)
	))
	return result

def delete_task_history() -> None:
	"""Delete the complete task history
	"""
	logging.info(f'Deleting task history')
	get_db().execute("DELETE FROM task_history;")
	return

def get_task_planning() -> List[dict]:
	"""Get the planning of each interval task (interval, next run and last run)

	Returns:
		List[dict]: List of interval tasks and their planning
	"""
	cursor = get_db('dict')

	tasks = cursor.execute(
		"""
		SELECT
			i.task_name, interval, run_at, next_run
		FROM task_intervals i
		INNER JOIN (
			SELECT
				task_name,
				MAX(run_at) AS run_at
			FROM task_history
			GROUP BY task_name
		) h
		ON i.task_name = h.task_name;
		"""
	)
	result = [{
		'task_name': task['task_name'],
		'display_name': task_library[task['task_name']].display_title,
		'interval': task['interval'],
		'next_run': task['next_run'],
		'last_run': task['run_at']
	} for task in tasks]
	return result
