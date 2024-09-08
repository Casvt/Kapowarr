# -*- coding: utf-8 -*-

"""
Background tasks and their handling
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from threading import Thread, Timer
from time import sleep, time
from typing import TYPE_CHECKING, Dict, List, Tuple, Type, Union

from backend.conversion import mass_convert
from backend.custom_exceptions import (InvalidComicVineApiKey,
                                       TaskNotDeletable, TaskNotFound)
from backend.db import get_db
from backend.helpers import Singleton
from backend.logging import LOGGER
from backend.naming import mass_rename
from backend.search import auto_search
from backend.server import WebSocket
from backend.volumes import Issue, Volume, refresh_and_scan

if TYPE_CHECKING:
    from flask import Flask

    from backend.download_queue import DownloadHandler


class Task(ABC):
    stop: bool
    message: str
    action: str
    display_title: str
    category: str

    @property
    @abstractmethod
    def volume_id(self) -> Union[int, None]:
        ...

    @property
    @abstractmethod
    def issue_id(self) -> Union[int, None]:
        ...

    @abstractmethod
    def __init__(self, **kwargs) -> None:
        ...

    @abstractmethod
    def run(self) -> Union[None, List[Tuple[str, int, Union[int, None]]]]:
        """Run the task

        Returns:
            Union[None, List[Tuple[str, int, Union[int, None]]]]:
            Either `None` if the task has no result or
            `List[Tuple[str, int, Union[int, None]]]` if the task returns
            search results.
        """
        ...

# =====================
# Issue tasks
# =====================


class AutoSearchIssue(Task):
    "Do an automatic search for an issue"

    stop = False
    message = ''
    action = 'auto_search_issue'
    display_title = 'Auto Search'
    category = 'download'

    @property
    def volume_id(self) -> int:
        return self._volume_id

    @property
    def issue_id(self) -> int:
        return self._issue_id

    def __init__(self, volume_id: int, issue_id: int) -> None:
        """Create the task

        Args:
            volume_id (int): The id of the volume in which the issue is
            issue_id (int): The id of the issue to search for
        """
        self._volume_id = volume_id
        self._issue_id = issue_id
        return

    def run(self) -> List[Tuple[str, int, Union[int, None]]]:
        volume = Volume(self._volume_id)
        issue = Issue(self._issue_id)
        self.message = f'Searching for {volume["title"]} #{issue["issue_number"]}'
        WebSocket().update_task_status(self)

        # Get search results and download them
        results = auto_search(self._volume_id, self._issue_id)
        if results:
            return [
                (result['link'], self._volume_id, self._issue_id)
                for result in results
            ]
        return []


class MassRenameIssue(Task):
    "Trigger a mass rename for an issue"

    stop = False
    message = ''
    action = 'mass_rename_issue'
    display_title = 'Mass Rename'
    category = ''

    @property
    def volume_id(self) -> int:
        return self._volume_id

    @property
    def issue_id(self) -> int:
        return self._issue_id

    def __init__(
        self,
        volume_id: int,
        issue_id: int,
        filepath_filter: Union[List[str], None] = []
    ) -> None:
        """Create the task

        Args:
            volume_id (int): The ID of the volume for which to perform the task.
            issue_id (int): The ID of the issue for which to perform the task.
            filepath_filter (Union[List[str], None], optional): Only rename
            files in this list.
                Defaults to [].
        """
        self._volume_id = volume_id
        self._issue_id = issue_id
        self.filepath_filter = filepath_filter
        return

    def run(self) -> None:
        volume = Volume(self._volume_id)
        issue = Issue(self._issue_id)
        self.message = f'Renaming files for {volume["title"]} #{issue["issue_number"]}'
        WebSocket().update_task_status(self)

        mass_rename(
            self._volume_id,
            self._issue_id,
            filepath_filter=self.filepath_filter,
            update_websocket=True
        )

        return


class MassConvertIssue(Task):
    "Trigger a mass convert for an issue"

    stop = False
    message = ''
    action = 'mass_convert_issue'
    display_title = 'Mass Convert'
    category = ''

    @property
    def volume_id(self) -> int:
        return self._volume_id

    @property
    def issue_id(self) -> int:
        return self._issue_id

    def __init__(
        self,
        volume_id: int,
        issue_id: int,
        filepath_filter: Union[List[str], None] = []
    ) -> None:
        """Create the task

        Args:
            volume_id (int): The ID of the volume for which to perform the task.
            issue_id (int): The ID of the issue for which to perform the task.
            filepath_filter (Union[List[str], None], optional): Only rename
            files in this list.
                Defaults to [].
        """
        self._volume_id = volume_id
        self._issue_id = issue_id
        self.filepath_filter = filepath_filter
        return

    def run(self) -> None:
        volume = Volume(self._volume_id)
        issue = Issue(self._issue_id)
        self.message = f'Converting files for {volume["title"]} #{issue["issue_number"]}'
        WebSocket().update_task_status(self)

        mass_convert(
            self._volume_id,
            self._issue_id,
            filepath_filter=self.filepath_filter,
            update_websocket=True
        )

        return

# =====================
# Volume tasks
# =====================


class AutoSearchVolume(Task):
    "Do an automatic search for a volume"

    stop = False
    message = ''
    action = 'auto_search'
    display_title = 'Auto Search'
    category = 'download'

    @property
    def volume_id(self) -> int:
        return self._volume_id

    @property
    def issue_id(self) -> None:
        return None

    def __init__(self, volume_id: int) -> None:
        """Create the task

        Args:
            volume_id (int): The id of the volume to search for
        """
        self._volume_id = volume_id
        return

    def run(self) -> List[Tuple[str, int, Union[int, None]]]:
        self.message = f'Searching for {Volume(self._volume_id)["title"]}'
        WebSocket().update_task_status(self)

        # Get search results and download them
        results = auto_search(self._volume_id)
        if results:
            return [
                (result['link'], self._volume_id, None)
                for result in results
            ]
        return []


class RefreshAndScanVolume(Task):
    "Trigger a refresh and scan for a volume"

    stop = False
    message = ''
    action = 'refresh_and_scan'
    display_title = 'Refresh And Scan'
    category = ''

    @property
    def volume_id(self) -> int:
        return self._volume_id

    @property
    def issue_id(self) -> None:
        return None

    def __init__(self, volume_id: int) -> None:
        """Create the task

        Args:
            volume_id (int): The id of the volume for which to perform the task
        """
        self._volume_id = volume_id
        return

    def run(self) -> None:
        self.message = f'Updating info on {Volume(self._volume_id)["title"]}'
        WebSocket().update_task_status(self)

        try:
            refresh_and_scan(self._volume_id)
        except InvalidComicVineApiKey:
            pass

        return


class MassRenameVolume(Task):
    "Trigger a mass rename for a volume"

    stop = False
    message = ''
    action = 'mass_rename'
    display_title = 'Mass Rename'
    category = ''

    @property
    def volume_id(self) -> int:
        return self._volume_id

    @property
    def issue_id(self) -> None:
        return None

    def __init__(
        self,
        volume_id: int,
        filepath_filter: Union[List[str], None] = []
    ) -> None:
        """Create the task

        Args:
            volume_id (int): The ID of the volume for which to perform the task.
            filepath_filter (Union[List[str], None], optional): Only rename
            files in this list.
                Defaults to [].
        """
        self._volume_id = volume_id
        self.filepath_filter = filepath_filter
        return

    def run(self) -> None:
        self.message = f'Renaming files for {Volume(self._volume_id)["title"]}'
        WebSocket().update_task_status(self)

        mass_rename(
            self._volume_id,
            filepath_filter=self.filepath_filter,
            update_websocket=True
        )

        return


class MassConvertVolume(Task):
    "Trigger a mass convert for a volume"

    stop = False
    message = ''
    action = 'mass_convert'
    display_title = 'Mass Convert'
    category = ''

    @property
    def volume_id(self) -> int:
        return self._volume_id

    @property
    def issue_id(self) -> None:
        return None

    def __init__(
        self,
        volume_id: int,
        filepath_filter: Union[List[str], None] = []
    ) -> None:
        """Create the task

        Args:
            volume_id (int): The ID of the volume for which to perform the task.
            filepath_filter (Union[List[str], None], optional): Only convert
            files in this list.
                Defaults to [].
        """
        self._volume_id = volume_id
        self.filepath_filter = filepath_filter
        return

    def run(self) -> None:
        self.message = f'Converting files for {Volume(self._volume_id)["title"]}'
        WebSocket().update_task_status(self)

        mass_convert(
            self._volume_id,
            filepath_filter=self.filepath_filter,
            update_websocket=True
        )

        return

# =====================
# Library tasks
# =====================


class UpdateAll(Task):
    "Trigger a refresh and scan for each volume in the library"

    stop = False
    message = ''
    action = 'update_all'
    display_title = 'Update All'
    category = ''

    @property
    def volume_id(self) -> None:
        return None

    @property
    def issue_id(self) -> None:
        return None

    def __init__(self, allow_skipping: bool = False) -> None:
        """Create the task

        Args:
            allow_skipping (bool, optional): Skip volumes that have been updated in the last 24 hours.
                Defaults to False.
        """
        self.allow_skipping = allow_skipping
        return

    def run(self) -> None:
        self.message = f'Updating info on all volumes'
        WebSocket().update_task_status(self)

        try:
            refresh_and_scan(
                update_websocket=True,
                allow_skipping=self.allow_skipping
            )
        except InvalidComicVineApiKey:
            pass

        return


class SearchAll(Task):
    "Trigger an automatic search for each volume in the library"

    stop = False
    message = ''
    action = 'search_all'
    display_title = 'Search All'
    category = 'download'

    @property
    def volume_id(self) -> None:
        return None

    @property
    def issue_id(self) -> None:
        return None

    def __init__(self) -> None:
        return

    def run(self) -> List[Tuple[str, int, Union[int, None]]]:
        cursor = get_db(force_new=True)
        cursor.execute(
            "SELECT id, title FROM volumes WHERE monitored = 1;"
        )
        downloads: List[Tuple[str, int, Union[int, None]]] = []
        ws = WebSocket()
        for volume_id, volume_title in cursor:
            if self.stop:
                break
            self.message = f'Searching for {volume_title}'
            ws.update_task_status(self)
            # Get search results and download them
            results = auto_search(volume_id)
            if results:
                downloads += [
                    (result['link'], volume_id, None)
                    for result in results
                ]
        return downloads


# =====================
# Task handling
# =====================
# Maps action attr to class for all tasks
# Only works for classes that directly inherit from Task
task_library: Dict[str, Type[Task]] = {
    c.action: c
    for c in Task.__subclasses__()
}


class TaskHandler(metaclass=Singleton):
    "Note: Singleton"

    queue: List[dict] = []
    task_interval_waiter: Union[Timer, None] = None

    def __init__(
        self,
        context: Flask,
        download_handler: DownloadHandler
    ) -> None:
        """Setup the handler

        Args:
            context (Flask): A Flask app instance
            download_handler (DownloadHandler): An instance of
            `download.DownloadHandler`
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
        LOGGER.debug(f'Running task {task.display_title}')
        with self.context():
            socket = WebSocket()
            try:
                result = task.run()
                cursor = get_db()

                # Note in history
                cursor.execute(
                    "INSERT INTO task_history VALUES (?,?,?);",
                    (task.action, task.display_title, round(time()))
                )

                if not task.stop:
                    if task.category == 'download' and result:
                        cursor.connection.commit()
                        for download in result:
                            self.download_handler.add(*download)
                            # add() does a write to db so commit in-between
                            # to avoid locking up the db
                            cursor.connection.commit()

                    LOGGER.info(f'Finished task {task.display_title}')

            except Exception:
                LOGGER.exception(
                    'An error occured while trying to run a task: ')
                task.message = 'AN ERROR OCCURED'
                socket.update_task_status(task)
                sleep(1.5)

            finally:
                if not task.stop:
                    socket.send_task_ended(task)
                    self.queue.pop(0)
                    self._process_queue()

        return

    def _process_queue(self) -> None:
        """
        Handle the queue. In the case that there is something in the queue and
        it isn't already running, start the task. This can safely be called
        multiple times while a task is going or while there is nothing in the queue.
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
        LOGGER.debug(f'Adding task to queue: {task.display_title}')
        id = self.queue[-1]['id'] + 1 if self.queue else 1
        task_data = {
            'task': task,
            'id': id,
            'status': 'queued',
            'thread': Thread(
                target=self.__run_task,
                args=(task,),
                name="Task Handler"
            )
        }
        self.queue.append(task_data)
        LOGGER.info(f'Added task: {task.display_title} ({id})')
        WebSocket().send_task_added(task)
        self._process_queue()
        return id

    @staticmethod
    def task_for_volume_running(volume_id: int) -> bool:
        """Whether or not there is a task in the queue that targets the volume.

        Args:
            volume_id (int): The volume ID to check for.

        Returns:
            bool: Whether or not a task is in the queue targeting the volume.
        """
        return any(
            t
            for t in TaskHandler.queue
            if (isinstance(t['task'], (UpdateAll, SearchAll))
                or t['task'].volume_id == volume_id)
        )

    def __check_intervals(self) -> None:
        "Check if any interval task needs to be run and add to queue if so"
        LOGGER.debug('Checking task intervals')
        with self.context():
            current_time = time()

            cursor = get_db()
            interval_tasks = cursor.execute(
                "SELECT task_name, interval, next_run FROM task_intervals;"
            ).fetchall()
            LOGGER.debug(f'Task intervals: {list(map(dict, interval_tasks))}')
            for task in interval_tasks:
                if task['next_run'] <= current_time:
                    # Add task to queue
                    task_class = task_library[task['task_name']]
                    if task_class is UpdateAll:
                        inst = task_class(allow_skipping=True)
                    else:
                        inst = task_class()
                    self.add(inst)

                    # Update next_run
                    next_run = round(current_time + task['interval'])
                    cursor.execute(
                        "UPDATE task_intervals SET next_run = ? WHERE task_name = ?;",
                        (next_run, task['task_name']))

        self.handle_intervals()
        return

    def handle_intervals(self) -> None:
        "Find next time an interval task needs to be run"
        with self.context():
            next_run = get_db().execute(
                "SELECT MIN(next_run) FROM task_intervals"
            ).fetchone()[0]
        timedelta = next_run - round(time()) + 1
        LOGGER.debug(f'Next interval task is in {timedelta} seconds')

        # Create sleep thread for that time and that will run
        # self.__check_intervals.
        self.task_interval_waiter = Timer(timedelta, self.__check_intervals)
        self.task_interval_waiter.start()
        return

    def stop_handle(self) -> None:
        "Stop the task handler"
        LOGGER.debug('Stopping task thread')

        if self.task_interval_waiter:
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
            List[dict]: A list with all tasks in the queue.
                Formatted using `self.__format_entry()`.
        """
        return [self.__format_entry(t) for t in self.queue]

    def get_one(self, task_id: int) -> dict:
        """Get one task from the queue based on it's id

        Args:
            task_id (int): The id of the task to get from the queue

        Raises:
            TaskNotFound: The id doesn't match with any task in the queue

        Returns:
            dict: The info of the task in the queue.
                Formatted using `self.__format_entry()`.
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
        LOGGER.info(f'Removed task: {task["task"].display_name} ({task_id})')
        WebSocket().send_task_ended(task['task'])
        return


def get_task_history(offset: int = 0) -> List[dict]:
    """Get the task history in blocks of 50.

    Args:
        offset (int, optional): The offset of the list.
            The higher the number, the deeper into history you go.

            Defaults to 0.

    Returns:
        List[dict]: The history entries.
    """
    result = get_db().execute(
        """
        SELECT
            task_name, display_title, run_at
        FROM task_history
        ORDER BY run_at DESC
        LIMIT 50
        OFFSET ?;
        """,
        (offset * 50,)
    ).fetchalldict()
    return result


def delete_task_history() -> None:
    "Delete the complete task history"
    LOGGER.info(f'Deleting task history')
    get_db().execute("DELETE FROM task_history;")
    return


def get_task_planning() -> List[dict]:
    """Get the planning of each interval task (interval, next run and last run)

    Returns:
        List[dict]: List of interval tasks and their planning
    """
    tasks = get_db().execute(
        """
        SELECT
            i.task_name, interval, next_run, run_at AS last_run
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
    ).fetchalldict()

    for t in tasks:
        t['display_name'] = task_library[t['task_name']].display_title

    return tasks
