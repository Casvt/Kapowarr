# -*- coding: utf-8 -*-

from __future__ import annotations

from abc import abstractmethod
from time import sleep, time
from typing import TYPE_CHECKING, Any, Dict, List, Tuple, Type, TypeVar, Union

from backend.base.custom_exceptions import (InvalidKeyValue,
                                            TaskNotDeletable, TaskNotFound)
from backend.base.definitions import QueuedTaskData, Task
from backend.base.helpers import Singleton
from backend.base.logging import LOGGER
from backend.features.download_queue import DownloadHandler
from backend.features.search import auto_search
from backend.implementations.conversion import mass_convert
from backend.implementations.naming import mass_rename
from backend.implementations.volumes import Volume, refresh_and_scan
from backend.internals.db import get_db
from backend.internals.server import (Server, TaskAddedEvent, TaskEndedEvent,
                                      TaskStatusEvent, WebSocket)

if TYPE_CHECKING:
    from threading import Timer


# region Task Handler
TaskType = TypeVar(
    "TaskType",
    bound=Task
)


class TaskHandler(metaclass=Singleton):
    tasks: Dict[str, Type[Task]] = {}

    queue: List[QueuedTaskData] = []
    task_interval_waiter: Union[Timer, None] = None

    @classmethod
    def register_task(cls, identifier: str):
        """Register a task.

        ```
        @TaskHandler.register_task("my_task")
        class MyTask(Task):
            ...
        ```

        Args:
            identifier (str): The string identifier for the task.

        Raises:
            RuntimeError: A task for the given identifier is already registered.
        """
        def wrapper(action: Type[TaskType]) -> Type[TaskType]:
            if identifier in cls.tasks:
                raise RuntimeError(
                    f"Task with {identifier=} registered multiple times"
                )
            action.action = identifier
            cls.tasks[identifier] = action
            return action
        return wrapper

    @classmethod
    def get_task_class(cls, identifier: str) -> Type[Task]:
        """Get a task implementation based on its identifier.

        Args:
            identifier (str): The identifer of the class.

        Raises:
            TaskNotFound: No task implementation found with the given identifier.

        Returns:
            Type[Task]: The task implementation.
        """
        try:
            return cls.tasks[identifier]
        except KeyError:
            raise TaskNotFound(identifier)

    def __run_task(self, task: Task) -> None:
        """Run a task.

        Args:
            task (Task): The task to run.
        """
        LOGGER.debug(f'Running task {task.display_title}')

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
                if isinstance(task, DownloadTask) and result:
                    DownloadHandler().add_multiple(
                        (link, indexer_id, volume_id, issue_id, False)
                        for link, indexer_id, volume_id, issue_id in result
                    )

                LOGGER.info(f'Finished task {task.display_title}')

        except Exception:
            LOGGER.exception(
                'An error occured while trying to run a task: ')
            task.message = 'AN ERROR OCCURED'
            socket.emit(TaskStatusEvent(task.message))
            sleep(1.5)

        finally:
            if not task.stop:
                socket.emit(TaskEndedEvent(task))
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
        if not first_entry['thread'].is_alive():
            first_entry['thread'].start()

        return

    def add(self, task: Task) -> int:
        """Add a task to the queue.

        Args:
            task (Task): The task to add to the queue.

        Returns:
            int: The ID of the entry in the queue.
        """
        LOGGER.debug(f'Adding task to queue: {task.display_title}')
        id = self.queue[-1]['id'] + 1 if self.queue else 1
        task_data: QueuedTaskData = {
            'id': id,
            'task': task,
            'thread': Server().get_db_thread(
                target=self.__run_task,
                name=f"TaskThread-{id}",
                args=(task,)
            )
        }
        self.queue.append(task_data)
        LOGGER.info(f'Added task: {task.display_title} ({id})')
        WebSocket().emit(TaskAddedEvent(task))
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
            if (
                isinstance(t['task'], LibraryTask)
                or t['task'].volume_id == volume_id
            )
        )

    def __check_intervals(self) -> None:
        "Check if any interval task needs to be run and add to queue if so"
        LOGGER.debug('Checking task intervals')
        current_time = time()

        cursor = get_db()
        interval_tasks = cursor.execute(
            "SELECT task_name, interval, next_run FROM task_intervals;"
        ).fetchall()
        LOGGER.debug(f'Task intervals: {list(map(dict, interval_tasks))}')
        for task in interval_tasks:
            if task['next_run'] <= current_time:
                # Add task to queue
                TaskClass = self.tasks[task['task_name']]
                if TaskClass is UpdateAll:
                    inst = TaskClass(allow_skipping=True)
                else:
                    inst = TaskClass()
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
        next_run: int = get_db().execute(
            "SELECT MIN(next_run) FROM task_intervals"
        ).fetchone()[0]
        timedelta = next_run - round(time()) + 1
        LOGGER.debug(f'Next interval task is in {timedelta} seconds')

        self.task_interval_waiter = Server().get_db_timer_thread(
            interval=timedelta,
            target=self.__check_intervals,
            name="TaskIntervalThread"
        )
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

    def __format_entry(self, task: QueuedTaskData) -> Dict[str, Any]:
        """Format a queue entry for API response.

        Args:
            task (QueuedTaskData): The queue entry.

        Returns:
            Dict[str, Any]: The formatted queue entry.
        """
        return {
            'id': task['id'],
            'action': task['task'].action,
            'display_title': task['task'].display_title,
            'running': task['thread'].is_alive(),
            'message': task['task'].message,
            'volume_id': task['task'].volume_id,
            'issue_id': task['task'].issue_id
        }

    def get_all(self) -> List[Dict[str, Any]]:
        """Get all tasks in the queue.

        Returns:
            List[Dict[str, Any]]: A list with all tasks in the queue.
        """
        return [self.__format_entry(t) for t in self.queue]

    def get_one(self, task_id: int) -> Dict[str, Any]:
        """Get one task from the queue based on its ID.

        Args:
            task_id (int): The ID of the task to get from the queue.

        Raises:
            TaskNotFound: The ID doesn't match with any task in the queue.

        Returns:
            Dict[str, Any]: The info of the task in the queue.
        """
        return self.__format_entry(self.__get_raw_entry(task_id))

    def __get_raw_entry(self, task_id: int) -> QueuedTaskData:
        """Get the raw entry from the queue based on its ID.

        Args:
            task_id (int): The ID of the task to get from the queue.

        Raises:
            TaskNotFound: The ID doesn't match with any task in the queue.

        Returns:
            QueuedTaskData: The raw entry of the task in the queue.
        """
        for entry in self.queue:
            if entry['id'] == task_id:
                return entry
        raise TaskNotFound(task_id)

    def remove(self, task_id: int) -> None:
        """Remove a task from the queue.

        Args:
            task_id (int): The ID of the task to delete from the queue.

        Raises:
            TaskNotDeletable: The task is not allowed to be deleted from the queue.
            TaskNotFound: The id doesn't map to any task in the queue.
        """
        # Get task and check if id exists
        # Raises TaskNotFound if the id isn't found
        task = self.__get_raw_entry(task_id)

        # Check if task is allowed to be deleted
        if self.queue[0] == task:
            raise TaskNotDeletable(task_id)

        task['task'].stop = True
        task['thread'].join()
        self.queue.remove(task)
        LOGGER.info(f'Removed task: {task["task"].display_title} ({task_id})')
        WebSocket().emit(TaskEndedEvent(task['task']))
        return

    def get_task_planning(self) -> List[Dict[str, Any]]:
        """Get the planning of each interval task (interval, next run and last run).

        Returns:
            List[Dict[str, Any]]: List of interval tasks and their planning.
        """
        tasks = get_db().execute(
            """
            SELECT
                i.task_name, interval, next_run, run_at AS last_run
            FROM task_intervals i
            LEFT JOIN (
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
            t['display_name'] = self.tasks[t['task_name']].display_title

        return tasks


# region History
def get_task_history(offset: int = 0) -> List[dict]:
    """Get the task history in blocks of 50.

    Args:
        offset (int, optional): The offset of the list. The higher the number,
            the deeper into history you go.
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


# region Task types
class LibraryTask(Task):
    """
    Tasks that inherit from this class signify that they don't work
    on one specific volume or issue
    """


class DownloadTask(Task):
    """
    Tasks that inherit from this class signify that they return downloads
    """

    @abstractmethod
    def run(self) -> List[Tuple[str, int, int, Union[int, None]]]:
        ...


# region Issue tasks
@TaskHandler.register_task('auto_search_issue')
class AutoSearchIssue(DownloadTask):
    "Do an automatic search for an issue"

    stop = False
    message = ''
    display_title = 'Auto Search'

    @property
    def volume_id(self) -> int:
        return self._volume_id

    @property
    def issue_id(self) -> int:
        return self._issue_id

    def __init__(self, volume_id: int, issue_id: int) -> None:
        """Create the task

        Args:
            volume_id (int): The ID of the volume in which the issue is.
            issue_id (int): The ID of the issue to search for.
        """
        self._volume_id = volume_id
        self._issue_id = issue_id
        return

    def run(self):
        volume = Volume(self._volume_id)
        volume_title = volume.vd.title
        issue_number = volume.get_issue(self._issue_id).get_data().issue_number
        self.message = f'Searching for {volume_title} #{issue_number}'
        WebSocket().emit(TaskStatusEvent(self.message))

        # Get search results and download them
        results = auto_search(self._volume_id, self._issue_id)
        downloads: List[Tuple[str, int, int, Union[int, None]]] = [
            (result['link'], result["indexer_id"], self._volume_id, self._issue_id)
            for result in results
        ]
        return downloads


@TaskHandler.register_task('mass_rename_issue')
class MassRenameIssue(Task):
    "Trigger a mass rename for an issue"

    stop = False
    message = ''
    display_title = 'Mass Rename'

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
        filepath_filter: List[str] = []
    ) -> None:
        """Create the task.

        Args:
            volume_id (int): The ID of the volume for which to perform the task.
            issue_id (int): The ID of the issue for which to perform the task.
            filepath_filter (List[str], optional): Only rename files in this
                list.
                Defaults to [].
        """
        self._volume_id = volume_id
        self._issue_id = issue_id
        self.filepath_filter = filepath_filter
        return

    def run(self) -> None:
        volume = Volume(self._volume_id)
        volume_title = volume.vd.title
        issue_number = volume.get_issue(self._issue_id).get_data().issue_number
        self.message = f'Renaming files for {volume_title} #{issue_number}'
        WebSocket().emit(TaskStatusEvent(self.message))

        mass_rename(
            self._volume_id,
            self._issue_id,
            filepath_filter=self.filepath_filter,
            update_websocket=True
        )

        return


@TaskHandler.register_task('mass_convert_issue')
class MassConvertIssue(Task):
    "Trigger a mass convert for an issue"

    stop = False
    message = ''
    display_title = 'Mass Convert'

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
        filepath_filter: List[str] = []
    ) -> None:
        """Create the task

        Args:
            volume_id (int): The ID of the volume for which to perform the task.
            issue_id (int): The ID of the issue for which to perform the task.
            filepath_filter (List[str], optional): Only rename files in this
                list.
                Defaults to [].
        """
        self._volume_id = volume_id
        self._issue_id = issue_id
        self.filepath_filter = filepath_filter
        return

    def run(self) -> None:
        volume = Volume(self._volume_id)
        volume_title = volume.vd.title
        issue_number = volume.get_issue(self._issue_id).get_data().issue_number
        self.message = f'Converting files for {volume_title} #{issue_number}'
        WebSocket().emit(TaskStatusEvent(self.message))

        mass_convert(
            self._volume_id,
            self._issue_id,
            filepath_filter=self.filepath_filter,
            update_websocket_progress=True,
            update_websocket_files=True
        )

        return


# region Volume tasks
@TaskHandler.register_task('auto_search')
class AutoSearchVolume(DownloadTask):
    "Do an automatic search for a volume"

    stop = False
    message = ''
    display_title = 'Auto Search'

    @property
    def volume_id(self) -> int:
        return self._volume_id

    @property
    def issue_id(self) -> None:
        return None

    def __init__(self, volume_id: int) -> None:
        """Create the task.

        Args:
            volume_id (int): The ID of the volume to search for.
        """
        self._volume_id = volume_id
        return

    def run(self):
        volume_title = Volume(self._volume_id).vd.title
        self.message = f'Searching for {volume_title}'
        WebSocket().emit(TaskStatusEvent(self.message))

        # Get search results and download them
        results = auto_search(self._volume_id)
        downloads: List[Tuple[str, int, int, Union[int, None]]] = [
            (result["link"], result["indexer_id"], self._volume_id, None)
            for result in results
        ]
        return downloads


@TaskHandler.register_task('refresh_and_scan')
class RefreshAndScanVolume(Task):
    "Trigger a refresh and scan for a volume"

    stop = False
    message = ''
    display_title = 'Refresh And Scan'

    @property
    def volume_id(self) -> int:
        return self._volume_id

    @property
    def issue_id(self) -> None:
        return None

    def __init__(self, volume_id: int) -> None:
        """Create the task.

        Args:
            volume_id (int): The ID of the volume for which to refresh and scan.
        """
        self._volume_id = volume_id
        return

    def run(self) -> None:
        volume_title = Volume(self._volume_id).vd.title
        self.message = f'Updating info on {volume_title}'
        WebSocket().emit(TaskStatusEvent(self.message))

        try:
            refresh_and_scan(self._volume_id, update_websocket=True)
        except InvalidKeyValue:
            # API key invalid
            pass

        return


@TaskHandler.register_task('mass_rename')
class MassRenameVolume(Task):
    "Trigger a mass rename for a volume"

    stop = False
    message = ''
    display_title = 'Mass Rename'

    @property
    def volume_id(self) -> int:
        return self._volume_id

    @property
    def issue_id(self) -> None:
        return None

    def __init__(
        self,
        volume_id: int,
        filepath_filter: List[str] = []
    ) -> None:
        """Create the task

        Args:
            volume_id (int): The ID of the volume for which to perform the task.
            filepath_filter (List[str], optional): Only rename files in this
                list.
                Defaults to [].
        """
        self._volume_id = volume_id
        self.filepath_filter = filepath_filter
        return

    def run(self) -> None:
        volume_title = Volume(self._volume_id).vd.title
        self.message = f'Renaming files for {volume_title}'
        WebSocket().emit(TaskStatusEvent(self.message))

        mass_rename(
            self._volume_id,
            filepath_filter=self.filepath_filter,
            update_websocket=True
        )

        return


@TaskHandler.register_task('mass_convert')
class MassConvertVolume(Task):
    "Trigger a mass convert for a volume"

    stop = False
    message = ''
    display_title = 'Mass Convert'

    @property
    def volume_id(self) -> int:
        return self._volume_id

    @property
    def issue_id(self) -> None:
        return None

    def __init__(
        self,
        volume_id: int,
        filepath_filter: List[str] = []
    ) -> None:
        """Create the task

        Args:
            volume_id (int): The ID of the volume for which to perform the task.
            filepath_filter (List[str], optional): Only convert files in this
                list.
                Defaults to [].
        """
        self._volume_id = volume_id
        self.filepath_filter = filepath_filter
        return

    def run(self) -> None:
        volume_title = Volume(self._volume_id).vd.title
        self.message = f'Converting files for {volume_title}'
        WebSocket().emit(TaskStatusEvent(self.message))

        mass_convert(
            self._volume_id,
            filepath_filter=self.filepath_filter,
            update_websocket_progress=True,
            update_websocket_files=True
        )

        return


# region Library tasks
@TaskHandler.register_task('update_all')
class UpdateAll(LibraryTask):
    "Trigger a refresh and scan for each volume in the library"

    stop = False
    message = ''
    display_title = 'Update All'

    @property
    def volume_id(self) -> None:
        return None

    @property
    def issue_id(self) -> None:
        return None

    def __init__(self, allow_skipping: bool = False) -> None:
        """Create the task.

        Args:
            allow_skipping (bool, optional): Skip volumes that have been updated
                in the last 24 hours.
                Defaults to False.
        """
        self.allow_skipping = allow_skipping
        return

    def run(self) -> None:
        self.message = f'Updating info on all volumes'
        WebSocket().emit(TaskStatusEvent(self.message))

        try:
            refresh_and_scan(
                update_websocket=True,
                allow_skipping=self.allow_skipping
            )

        except InvalidKeyValue:
            # API key invalid
            pass

        return


@TaskHandler.register_task('search_all')
class SearchAll(LibraryTask, DownloadTask):
    "Trigger an automatic search for each volume in the library"

    stop = False
    message = ''
    display_title = 'Search All'

    @property
    def volume_id(self) -> None:
        return None

    @property
    def issue_id(self) -> None:
        return None

    def __init__(self) -> None:
        return

    def run(self):
        cursor = get_db(force_new=True)
        cursor.execute(
            "SELECT id, title FROM volumes WHERE monitored = 1;"
        )
        downloads: List[Tuple[str, int, int, Union[int, None]]] = []
        ws = WebSocket()
        for volume_id, volume_title in cursor:
            if self.stop:
                break
            self.message = f'Searching for {volume_title}'
            ws.emit(TaskStatusEvent(self.message))
            # Get search results and download them
            results = auto_search(volume_id)
            if results:
                downloads += [
                    (result['link'], result["indexer_id"], volume_id, None)
                    for result in results
                ]
        return downloads
