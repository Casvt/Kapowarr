# Kapowarr AI Agent Instructions

## Architecture Overview

Kapowarr is a Flask-based comic book library manager with a clear separation between backend logic and frontend presentation. The application follows the *arr suite conventions with a focus on automated downloading, renaming, and organizing comic book files.

**Core Components:**
- `backend/`: All business logic, database operations, and external integrations
- `frontend/`: Flask blueprints (`api.py` for REST endpoints, `ui.py` for HTML rendering)
- `Kapowarr.py`: Main entry point that initializes the application via multiprocessing

**Key Singletons** (access via `ClassName()` with no instantiation):
- `Settings()`: Application configuration and user settings
- `DownloadHandler()`: Manages download queue and direct/torrent/usenet downloads
- `TaskHandler()`: Background task scheduler and executor
- `WebSocket()`: Real-time event broadcasting to frontend clients
- `Server()`: Flask app wrapper with custom threading dispatcher

## Database Patterns

**Always use `get_db()` for database access** - returns a thread-safe `KapowarrCursor`:
```python
from backend.internals.db import get_db, commit

cursor = get_db()
cursor.execute("SELECT * FROM volumes WHERE id = ?", (volume_id,))
result = cursor.fetchonedict()  # Returns dict or None
commit()  # Must call manually after writes
```

**Connection Management:**
- One connection per thread (managed by `DBConnectionManager` metaclass)
- Use `commit()` explicitly after write operations
- Use `iter_commit(iterable)` for batch operations that commit after each iteration
- Database models in `backend/internals/db_models.py` provide higher-level abstractions (e.g., `FilesDB`, `GeneralFilesDB`)

## Type Hints & Import Patterns

**Python 3.8+ compatibility is mandatory**. Use `typing_extensions` for backports.

**Avoid circular imports with `TYPE_CHECKING`:**
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.features.tasks import Task
    from flask.ctx import AppContext
```

**Use type hints extensively** - mypy runs with strict checking enabled. See `.vscode/settings.json` for configuration.

## Code Styling & Formatting

**Automated tooling** (use task "Format All" or individual commands):
- `isort .` - organizes imports (groups: stdlib, third-party, local)
- `autopep8 --in-place -r .` - formats code (80 char line limit preferred, not strict)
- `mypy --explicit-package-bases .` - type checking

**Docstring requirements:**
```python
def example_function(volume_id: int, check: bool = False) -> VolumeData:
    """Brief description of what the function does.

    Args:
        volume_id (int): The ID of the volume to fetch.
        check (bool, optional): Whether to validate existence.
            Defaults to False.

    Raises:
        VolumeNotFound: When volume doesn't exist and check is True.

    Returns:
        VolumeData: The volume data dictionary.
    """
```

## Custom Exceptions & Error Handling

**All custom exceptions inherit from `KapowarrException`** and define an `api_response` property:
```python
from backend.base.custom_exceptions import VolumeNotFound, InvalidKeyValue

# Exceptions automatically convert to API responses in routes
raise VolumeNotFound(volume_id)  # Returns {"code": 404, "error": "VolumeNotFound", ...}
```

See `backend/base/custom_exceptions.py` for the complete exception hierarchy.

## File Extraction & Naming

**The filename parsing system is complex** - `backend/base/file_extraction.py` contains regex-heavy logic for extracting volume numbers, issue numbers, years, and special versions from filenames. This module has become "a bit of a box of black magic" (per CONTRIBUTING.md). If modifying `extract_filename_data()`, proceed carefully or consult the original author.

**Naming configuration** uses format strings with placeholders:
- `{series_name}`, `{volume_number}`, `{issue_number}`, `{year}`, `{special_version}`
- Configured via Settings: `volume_folder_naming`, `file_naming`, `file_naming_special_version`, etc.

## WebSocket Events

**Real-time updates** use Flask-SocketIO for broadcasting state changes:
```python
from backend.internals.server import WebSocket, TaskStatusEvent, QueueStatusEvent

ws = WebSocket()
ws.emit(TaskStatusEvent("Searching for Volume #1"))  # Updates task progress
ws.emit(QueueStatusEvent(download))  # Updates download queue status
```

Event types defined in `backend/base/definitions.py` as dataclasses.

## Testing & Development

**Running tests:**
```bash
python3 -m unittest discover -s ./tests -p '*.py'
```

Tests are minimal - focus on manual verification of changes. The test suite uses a schema validator (`tests/Tbackend/db_schema.py`) to ensure database integrity.

## Docker & Deployment

**Base image:** `lsiobase/debian:bookworm` (see `Dockerfile`)
- Python 3 application, not containerized Python
- Uses `waitress` WSGI server with custom thread dispatcher (`ThreadedTaskDispatcher`)
- Default port: 5656
- Data persists in `/app` with volume folders managed by user configuration

## Key Conventions

1. **4 spaces for indentation** (no tabs)
2. **Use `folder_path()` helper** for building absolute paths relative to application directory
3. **Singleton access pattern:** Call class as function, no manual instantiation
4. **Explicit commits:** Database writes require manual `commit()` calls
5. **LRU caching:** Used sparingly for expensive lookups (e.g., `@lru_cache(1)` on settings)
6. **Foreign key constraints enabled:** `PRAGMA foreign_keys = ON` in all connections
7. **Thread-safe operations:** Each request gets its own DB connection, singletons manage concurrency

## Critical Workflows

**Adding a new background task:**
1. Subclass `Task` in `backend/features/tasks.py`
2. Implement `run()`, `volume_id`, `issue_id` properties
3. Register via `TaskHandler().add()` with proper action identifier
4. Emit `TaskStatusEvent` for progress updates

**Adding a new download source:**
1. Subclass `BaseDirectDownload` in `backend/implementations/download_clients.py`
2. Implement `run()` method and set `identifier` class attribute
3. Add to `download_type_to_class` mapping in `backend/features/download_queue.py`
4. Handle state transitions: `QUEUED -> DOWNLOADING -> IMPORTING -> COMPLETED`
