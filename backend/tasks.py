#-*- coding: utf-8 -*-

"""This file contains functions regarding background tasks
"""

import logging
from abc import ABC, abstractmethod
from threading import Thread
from time import sleep, time
from typing import Dict, List, Union

from backend.custom_exceptions import (InvalidComicVineApiKey,
                                       TaskNotDeletable, TaskNotFound)
from backend.db import get_db
from backend.download import DownloadHandler
from backend.search import auto_search
from backend.volumes import refresh_and_scan_volume

class Task(ABC):
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

	@abstractmethod
	def run(self) -> Union[None, List[tuple]]:
		return

#=====================
# Issue tasks
#=====================
class AutoSearchIssue(Task):
	message = ''
	action = 'auto_search_issue'
	display_title = 'Auto Search'
	category = 'download'
	
	def __init__(self, volume_id: int, issue_id: int):
		self.volume_id = volume_id
		self.id = issue_id
	
	def run(self) -> List[tuple]:
		title = get_db().execute(
			"""
			SELECT
				v.title, i.title
			FROM
				volumes AS v,
				issues AS i
			WHERE
				i.volume_id = v.id
				AND i.id = ?;
			""",
			(self.id,)
		).fetchone()
		self.message = f'Searching for {": ".join(title)}'

		# Get search results and download them
		results = auto_search(self.volume_id, self.id)
		if results:
			return [(result['link'], self.volume_id, self.id) for result in results]
		return []

#=====================
# Volume tasks
#=====================
class AutoSearchVolume(Task):
	message = ''
	action = 'auto_search'
	display_title = 'Auto Search'
	category = 'download'
	
	def __init__(self, volume_id: int):
		self.id = volume_id
	
	def run(self) -> List[tuple]:
		title = get_db().execute(
			"SELECT title FROM volumes WHERE id = ? LIMIT 1",
			(self.id,)
		).fetchone()[0]
		self.message = f'Searching for {title}'

		#get search results and download them
		results = auto_search(self.id)
		if results:
			return [(result['link'], self.id) for result in results]
		return []

class RefreshAndScanVolume(Task):
	message = ''
	action = 'refresh_and_scan'
	display_title = 'Refresh And Scan'
	category = ''
	
	def __init__(self, volume_id: int):
		self.id = volume_id

	def run(self) -> None:
		title = get_db().execute(
			"SELECT title FROM volumes WHERE id = ?", 
			(self.id,)
		).fetchone()[0]
		self.message = f'Updating info on {title}'

		try:
			refresh_and_scan_volume(self.id)
		except InvalidComicVineApiKey:
			pass

		return

#=====================
# Library tasks
#=====================
class UpdateAll(Task):
	message = ''
	action = 'update_all'
	display_title = 'Update All'
	category = ''

	def run(self) -> None:
		volume_ids = get_db().execute(
			"SELECT id, title FROM volumes;"
		).fetchall()
		for volume_id, volume_title in volume_ids:
			self.message = f'Updating info on {volume_title}'
			try:
				refresh_and_scan_volume(volume_id)
			except InvalidComicVineApiKey:
				break

		return

class SearchAll(Task):
	message = ''
	action = 'search_all'
	display_title = 'Search All'
	category = 'download'

	def run(self) -> List[tuple]:
		volume_ids = get_db().execute(
			"SELECT id, title FROM volumes WHERE monitored = 1;"
		).fetchall()
		downloads = []
		for volume_id, volume_title in volume_ids:
			self.message = f'Searching for {volume_title}'
			# Get search results and download them
			results = auto_search(volume_id)
			if results:
				downloads += [(result['link'], volume_id) for result in results]
		return downloads

#=====================
# Task handling
#=====================
# Maps action attr to class of all tasks
# Only works for classes that directly inherit from Task
task_library: Dict[str, Task] = {c.action: c for c in Task.__subclasses__()}

class TaskHandler:
	queue = []
	stop = False
	def __init__(self, context, download_handler: DownloadHandler):
		self.context = context.app_context
		self.download_handler = download_handler
		self.thread = Thread(target=self.handle, name="Task Handler")

	def __run_task(self, task: Task) -> None:
		try:
			with self.context():
				result = task.run()
				# Note in history
				get_db().execute(
					"INSERT INTO task_history VALUES (?,?,?);",
					(task.action, task.display_title, round(time()))
				)

				if task.category == 'download':
					for download in result:
						self.download_handler.add(*download)

		except Exception:
			logging.exception('An error occured while trying to run a task: ')
			
		return

	def handle(self) -> None:
		"""This function is intended to be run in a thread
		"""
		with self.context():
			self.task_intervals = {
				t[0]: {
					'interval': t[1],
					'next_run': t[2]
				}
				for t in get_db().execute(
					"SELECT task_name, interval, next_run FROM task_intervals;"
				).fetchall()
			}
		
		while self.stop == False:
			# Interval tasks
			current_time = time()
			for task, times in self.task_intervals.items():
				if times['next_run'] < current_time:
					# Add task to queue
					task_class = task_library[task]
					self.add(task_class())

					# Update what time task needs to be run next
					next_run = round(time() + times['interval'])
					self.task_intervals[task]['next_run'] = next_run
					with self.context():
						get_db().execute(
							"UPDATE task_intervals SET next_run = ? WHERE task_name = ?",
							(next_run, task)
						)

			# Handle tasks in queue
			if len(self.queue) > 0:
				entry = self.queue[0]
				entry['status'] = 'running'
				logging.info(f'Running task: {entry["task"].display_title} ({entry["id"]})')
				self.__run_task(entry['task'])
				self.queue.pop(0)
			else:
				sleep(0.5)
		return

	def stop_handle(self) -> None:
		logging.debug('Stopping task thread')
		self.stop = True
		self.thread.join()
		return

	def add(self, task: Task) -> int:
		id = next(iter(self.queue[::-1]), {'id': 0})['id'] + 1
		self.queue.append({
			'task': task,
			'id': id,
			'status': 'queued'
		})
		logging.info(f'Added task: {task.display_title} ({id})')
		return id

	def _format_entry(self, t: dict) -> dict:
		return {
			'id': t['id'],
			'action': t['task'].action,
			'display_title': t['task'].display_title,
			'status': t['status'],
			'message': t['task'].message
		}

	def get_all(self) -> List[dict]:
		result = list(map(
			self._format_entry,
			self.queue
		))
		return result

	def get_one(self, task_id: int) -> dict:
		tasks = self.get_all()
		for t in tasks:
			if t['id'] == task_id:
				return self._format_entry(t)
		raise TaskNotFound

	def remove(self, task_id: int) -> None:
		for i, t in enumerate(self.queue[1:]):
			t: Task
			if t['id'] == task_id:
				self.queue.pop(i)
				break
		else:
			if self.queue[0]['id'] == task_id:
				raise TaskNotDeletable
			else:
				raise TaskNotFound

		logging.info(f'Removed task: {t["task"].display_name} ({task_id})')
		return

def get_task_history(offset: int=0) -> List[dict]:
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
			(offset,)
		).fetchall()
	))
	return result

def delete_task_history() -> None:
	get_db().execute("DELETE FROM task_history;")
	logging.info(f'Deleted task history')
	return
