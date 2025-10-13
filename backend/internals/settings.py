# -*- coding: utf-8 -*

from dataclasses import _MISSING_TYPE, asdict, dataclass, field
from functools import lru_cache
from logging import INFO
from os import urandom, environ
from os.path import abspath, isdir, join, sep
from secrets import token_bytes
import time
from typing import Any, Dict, Literal, Mapping, Optional, TypedDict
from types import MappingProxyType
from cron_converter import Cron

from backend.base.custom_exceptions import (FolderNotFound, InvalidKey,
                                            InvalidKeyValue,
                                            InvalidSettingModification)
from backend.base.definitions import (BaseEnum, Constants,
                                      DateType, GCDownloadSource,
                                      SeedingHandling, StartType, TaskIntervals)
from backend.base.files import (folder_is_inside_folder,
                                folder_path, uppercase_drive_letter)
from backend.base.helpers import (CommaList, Singleton, force_suffix,
                                  get_python_version, hash_password,
                                  normalise_base_url)
from backend.base.logging import LOGGER, set_log_level
from backend.internals.db import DBConnection, KapowarrCursor, commit, get_db
from backend.internals.db_migration import get_latest_db_version


task_intervals: TaskIntervals = {
    # If there are tasks that should be run at the same time,
    # but per se after each other, put them in that order in the dict.
    'update_all': 3600, # every hour
    'search_all': 86400 # every day
}

@dataclass(frozen=True)
class SettingsValues:
    database_version: int = get_latest_db_version()
    log_level: int = INFO
    auth_password: str = ''
    auth_salt: bytes = token_bytes()
    comicvine_api_key: str = ''
    api_key: str = environ.get("API_KEY") or ''
    flaresolverr_base_url: str = ''

    host: str = '0.0.0.0'
    port: int = 5656
    url_base: str = ''
    backup_host: str = '0.0.0.0'
    backup_port: int = 5656
    backup_url_base: str = ''

    rename_downloaded_files: bool = True
    replace_illegal_characters: bool = True
    volume_folder_naming: str = join(
        '{series_name}', 'Volume {volume_number} ({year})'
    )
    file_naming: str = '{series_name} ({year}) Volume {volume_number} Issue {issue_number}'
    file_naming_empty: str = '{series_name} ({year}) Volume {volume_number} Issue {issue_number}'
    file_naming_special_version: str = '{series_name} ({year}) Volume {volume_number} {special_version}'
    file_naming_vai: str = '{series_name} ({year}) Volume {issue_number}'

    long_special_version: bool = False
    volume_padding: int = 2
    issue_padding: int = 3

    create_empty_volume_folders: bool = True
    delete_empty_folders: bool = False

    unmonitor_deleted_issues: bool = False

    convert: bool = False
    extract_issue_ranges: bool = False
    format_preference: CommaList = field(default_factory=lambda: CommaList(''))

    service_preference: CommaList = field(default_factory=lambda: CommaList(
        (s.value for s in GCDownloadSource._member_map_.values())
    ))
    download_folder: str = folder_path('temp_downloads')
    concurrent_direct_downloads: int = 1
    failing_download_timeout: int = 0
    seeding_handling: SeedingHandling = SeedingHandling.COPY
    delete_completed_downloads: bool = True

    date_type: DateType = DateType.COVER_DATE

    #TODO: Support dict-like (object) value type of a key in /settings being dict, currently causes downstream issues if we use a dict as value
    update_all: str = "0 * * * *" # every hour
    search_all: str = "0 0 * * *" # every day

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for k, v in self.__dict__.items():
            if k.startswith('backup_'):
                continue

            if k == 'auth_salt':
                continue

            if k == 'auth_password' and v:
                v = Constants.PASSWORD_REPLACEMENT

            if isinstance(v, BaseEnum):
                result[k] = v.value
            else:
                result[k] = v

        return result


@lru_cache(1)
def get_about_data() -> Dict[str, Any]:
    """Get data about the application and it's environment.

    Raises:
        RuntimeError: If the version is not found in the pyproject.toml file.

    Returns:
        Dict[str, Any]: The information.
    """
    with open(folder_path("pyproject.toml"), "r") as f:
        for line in f:
            if line.startswith("version = "):
                version = "v" + line.split('"')[1]
                break
        else:
            raise RuntimeError("Version not found in pyproject.toml")

    return {
        "version": version,
        "python_version": get_python_version(),
        "database_version": get_latest_db_version(),
        "database_location": DBConnection.file,
        "data_folder": folder_path()
    }



class Settings(metaclass=Singleton):
    restart_on_hosting_changes: bool = True
    "Override this to disable the server restart on hosting changes."

    def __init__(self) -> None:
        self._insert_missing_settings()
        self._fetch_settings()
        return

    def _insert_missing_settings(self) -> None:
        "Insert any missing keys from the settings into the database."
        get_db().executemany(
            "INSERT OR IGNORE INTO config(key, value) VALUES (?, ?);",
            asdict(SettingsValues()).items()
        )
        commit()
        return

    def _fetch_settings(self) -> None:
        "Load the settings from the database into the cache."
        db_values = {
            k: v
            for k, v in get_db().execute(
                "SELECT key, value FROM config;"
            )
            if k in SettingsValues.__dataclass_fields__
        }

        for key, value in db_values.items():
            if SettingsValues.__dataclass_fields__[key].type is bool:
                db_values[key] = bool(value)

        for cl_key in ('format_preference', 'service_preference'):
            db_values[cl_key] = CommaList(db_values[cl_key])

        for en_key, en in (
            ('seeding_handling', SeedingHandling),
            ('date_type', DateType),
        ):
            db_values[en_key] = en[db_values[en_key].upper()]

        self.__cached_values = SettingsValues(**db_values)
        return

    def get_settings(self) -> SettingsValues:
        """Get the settings from the cache.

        Returns:
            SettingsValues: The settings.
        """
        return self.__cached_values

    # Alias, better in one-liners
    # sv = Settings Values
    @property
    def sv(self) -> SettingsValues:
        """Get the settings from the cache.

        Returns:
            SettingsValues: The settings.
        """
        return self.__cached_values

    def __getitem__(self, __name: str) -> Any:
        """Get the value of the given setting key.

        Args:
            __name (str): The key of the setting.

        Raises:
            AttributeError: Key is not a setting key.

        Returns:
            Any: The value of the setting.
        """
        return getattr(self.__cached_values, __name)

    def update(
        self,
        data: Mapping[str, Any]
    ) -> None:
        """Change the settings, in a `dict.update()` type of way.

        Args:
            data (Mapping[str, Any]): The keys and their new values.

        Raises:
            InvalidKey: Key is not allowed or unknown.
            InvalidKeyValue: Value of the key is not allowed.
            InvalidSettingModification: Key can not be modified this way.
            FolderNotFound: Folder not found.
        """
        from backend.implementations.naming import (NAMING_MAPPING,
                                                    check_mock_filename)

        db = get_db()
        formatted_data = {}
        for key, value in data.items():
            formatted_data[key] = self.__format_value(key, value)

        if any(
            key in formatted_data
            for key in NAMING_MAPPING
        ):
            # Changes to naming schemes
            check_mock_filename(**{
                key: formatted_data.get(key)
                for key in NAMING_MAPPING
            })

        hosting_changes = any(
            s in data
            and formatted_data[s] != getattr(self.get_settings(), s)
            for s in ('host', 'port', 'url_base')
        )

        task_interval_changes = any(
            s in data
            and formatted_data[s] != getattr(self.get_settings(), s)
            for s in ('update_all', 'search_all')
        )

        if hosting_changes:
            self.backup_hosting_settings()

        print("formatted_data:", formatted_data)
        if task_interval_changes:
            #INFO: Store original cron strings before they're converted to intervals
            original_cron_strings = {
                k: data[k] for k in ('update_all', 'search_all') if k in data
            }
            self._handle_task_interval_change(db, formatted_data, original_cron_strings)

        db.executemany(
            "UPDATE config SET value = ? WHERE key = ?;",
            ((v, k) for k, v in formatted_data.items())
        )

        if (
            'log_level' in data
            and formatted_data['log_level'] != getattr(
                self.get_settings(), 'log_level'
            )
        ):
            set_log_level(formatted_data['log_level'])

        self._fetch_settings()

        LOGGER.info(f'Settings changed: {formatted_data}')

        if hosting_changes and self.restart_on_hosting_changes:
            from backend.internals.server import SERVER
            SERVER.restart(
                StartType.RESTART_HOSTING_CHANGES
            )

        return

    def __setitem__(self, __name: str, __value: Any) -> None:
        """Change the value of a setting.

        Args:
            __name (str): The key of the setting.
            __value (Any): The new value.

        Raises:
            InvalidKey: Key is not allowed or unknown.
            InvalidKeyValue: Value of the key is not allowed.
            InvalidSettingModification: Key can not be modified this way.
            FolderNotFound: Folder not found.
        """
        self.update({__name: __value})
        return

    def reset(self, key: str) -> None:
        """Reset the value of the key to the default value.

        Args:
            key (str): The key of which to reset the value.

        Raises:
            InvalidKey: The key is not valid or unknown.
        """
        LOGGER.debug(f'Setting reset: {key}')

        if not isinstance(
            SettingsValues.__dataclass_fields__[key].default_factory,
            _MISSING_TYPE
        ):
            self[key] = SettingsValues.__dataclass_fields__[
                key].default_factory()
        else:
            self[key] = SettingsValues.__dataclass_fields__[key].default

        return

    def generate_api_key(self) -> None:
        "Generate a new api key"
        LOGGER.debug('Generating new api key')

        api_key = urandom(16).hex()
        get_db().execute(
            "UPDATE config SET value = ? WHERE key = 'api_key';",
            (api_key,)
        )
        self._fetch_settings()

        LOGGER.info(f'Setting api key regenerated: {api_key}')
        return

    def backup_hosting_settings(self) -> None:
        "Backup the hosting settings in the database."
        s = self.get_settings()
        backup_settings = {
            'backup_host': s.host,
            'backup_port': s.port,
            'backup_url_base': s.url_base
        }
        self.update(backup_settings)
        return

    def __format_value(self, key: str, value: Any) -> Any:
        """Check if the value of a setting is allowed and convert if needed.

        Args:
            key (str): Key of setting.
            value (Any): Value of setting.

        Raises:
            InvalidKey: Key is invalid or unknown.
            InvalidKeyValue: Value is not allowed.
            InvalidSettingModification: Key can not be modified this way.
            FolderNotFound: Folder not found.

        Returns:
            Any: (Converted) Setting value.
        """
        converted_value = value

        if key not in SettingsValues.__dataclass_fields__:
            raise InvalidKey(key)

        if key == 'api_key':
            raise InvalidSettingModification(key, 'POST /settings/api_key')

        if (
            SettingsValues.__dataclass_fields__[key].type is CommaList
            and isinstance(value, list)
        ):
            value = CommaList(value)

        if issubclass(SettingsValues.__dataclass_fields__[key].type, BaseEnum):
            try:
                value = SettingsValues.__dataclass_fields__[key].type(value)
            except ValueError:
                raise InvalidKeyValue(key, value)

        if not isinstance(value, SettingsValues.__dataclass_fields__[key].type):
            raise InvalidKeyValue(key, value)

        if key == 'auth_password':
            if value == Constants.PASSWORD_REPLACEMENT:
                converted_value = self.sv.auth_password

            elif value:
                converted_value = hash_password(
                    self.sv.auth_salt,
                    value
                )

        if key == 'port' and not 0 < value <= 65_535:
            raise InvalidKeyValue(key, value)

        elif key == 'url_base':
            if value:
                converted_value = ('/' + value.lstrip('/')).rstrip('/')

        elif key == 'comicvine_api_key':
            from backend.implementations.comicvine import ComicVine
            converted_value = value.strip()
            if converted_value and not ComicVine(converted_value).test_token():
                raise InvalidKeyValue(key, value)

        elif key == 'download_folder':
            from backend.implementations.root_folders import RootFolders

            if not isdir(value):
                raise FolderNotFound(value)

            converted_value = uppercase_drive_letter(
                force_suffix(abspath(value))
            )

            for rf in RootFolders().get_all():
                if (
                    folder_is_inside_folder(rf.folder, converted_value)
                    or folder_is_inside_folder(converted_value, rf.folder)
                ):
                    raise InvalidKeyValue(key, value)

        elif key == 'concurrent_direct_downloads' and value <= 0:
            raise InvalidKeyValue(key, value)

        elif key == 'failing_download_timeout' and value < 0:
            raise InvalidKeyValue(key, value)

        elif key == 'volume_padding' and not 1 <= value <= 3:
            raise InvalidKeyValue(key, value)

        elif key == 'issue_padding' and not 1 <= value <= 4:
            raise InvalidKeyValue(key, value)

        elif key == 'format_preference':
            from backend.implementations.conversion import \
                FileConversionHandler

            available = FileConversionHandler.get_available_formats()
            for entry in value:
                if entry not in available:
                    raise InvalidKeyValue(key, value)

            converted_value = value

        elif key == 'service_preference':
            available = [
                s.value
                for s in GCDownloadSource._member_map_.values()
            ]
            for entry in value:
                if entry not in available:
                    raise InvalidKeyValue(key, value)
            for entry in available:
                if entry not in value:
                    raise InvalidKeyValue(key, value)

            converted_value = value

        elif key == 'flaresolverr_base_url':
            from backend.implementations.flaresolverr import FlareSolverr

            converted_value = value
            if converted_value:
                converted_value = normalise_base_url(converted_value)

            if (
                converted_value
                and not FlareSolverr.test_flaresolverr(converted_value)
            ):
                raise InvalidKeyValue(key, value)

        elif key == "update_all" or key == "search_all":
            if not isinstance(value, str):
                raise InvalidKeyValue(key, value)

            if value == "":
                return

            converted_value = value
        else:
            from backend.implementations.naming import (NAMING_MAPPING,
                                                        check_format)
            if key in NAMING_MAPPING:
                converted_value = value.strip().strip(sep)
                if not check_format(converted_value, key):
                    raise InvalidKeyValue(key, value)

        return converted_value

    def _handle_task_interval_change(self, db: KapowarrCursor, formatted_data: dict, original_cron_strings: dict):
        new_search_task_interval: Optional[int] = formatted_data.get("search_all")
        new_update_task_interval: Optional[int] = formatted_data.get("update_all")
        cur_time = time.time()

        entry_data = []
        if new_search_task_interval:
            cron_schedule = original_cron_strings.get("search_all", "")
            entry_data.append(self._handle_cron_data(cron_schedule, cur_time, "search_all"))
        if new_update_task_interval:
            cron_schedule = original_cron_strings.get("update_all", "")
            entry_data.append(self._handle_cron_data(cron_schedule, cur_time, "update_all"))

        if entry_data:
            db.executemany("UPDATE task_intervals SET interval = ?, next_run = ? WHERE task_name = ?", entry_data)

    def _handle_cron_data(self, cron_schedule: str, cur_time: float, key: Literal["search_all", "update_all"]):
        parsed_cron_schedule = Cron(cron_schedule).schedule()
        cron_interval = int(parsed_cron_schedule.next().timestamp() - parsed_cron_schedule.prev().timestamp())
        return (cron_interval, int(cur_time + cron_interval), key)


