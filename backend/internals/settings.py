# -*- coding: utf-8 -*-

from dataclasses import _MISSING_TYPE, asdict, dataclass, field
from functools import lru_cache

try:
    from grp import getgrgid, getgrnam
except ImportError:
    getgrgid = None
    getgrnam = None

from logging import INFO
from os import urandom
from os.path import abspath, isdir, join, sep
from secrets import token_bytes
from typing import Any, Dict, Mapping

from backend.base.custom_exceptions import (ClientNotWorking,
                                            CredentialInvalid,
                                            FolderNotFound, InvalidKeyValue,
                                            InvalidSettingModification,
                                            KeyNotFound)
from backend.base.definitions import (BaseEnum, Constants, DateType,
                                      FileDate, GCDownloadSource, OSType,
                                      ProxyType, SeedingHandling)
from backend.base.files import (are_folders_colliding, folder_path,
                                uppercase_drive_letter)
from backend.base.helpers import (CommaList, Singleton, build_proxy_url,
                                  can_run_64bit_executable, force_suffix,
                                  get_os_type, get_python_version,
                                  get_version_from_pyproject, hash_credential,
                                  normalise_base_url, test_proxy_url)
from backend.base.logging import LOGGER, set_log_level
from backend.internals.db import DBConnection, commit, get_db
from backend.internals.db_migration import DatabaseMigrationHandler


class System:
    os_type = get_os_type()
    "What the OS of the system is"

    runs_64bit = can_run_64bit_executable()
    "Whether an external 64bit executable can be run"


@lru_cache(1)
def get_about_data() -> Dict[str, Any]:
    """Get data about the application and its environment.

    Raises:
        RuntimeError: Application version not found in pyproject file.

    Returns:
        Dict[str, Any]: The information.
    """
    return {
        "version": get_version_from_pyproject(folder_path("pyproject.toml")),
        "python_version": get_python_version(),
        "database_version": DatabaseMigrationHandler.latest_db_version(),
        "database_location": DBConnection.file,
        "data_folder": folder_path(),
        "os": System.os_type.value,
        "runs_64bit": System.runs_64bit
    }


@dataclass(frozen=True)
class PublicSettingsValues:
    """All settings that are exposed to the user"""
    log_level: int = INFO
    auth_username: str = ''
    auth_password: str = ''

    comicvine_api_key: str = ''
    api_key: str = ''
    flaresolverr_base_url: str = ''

    host: str = '0.0.0.0'
    port: int = 5656
    url_base: str = ''

    proxy_type: ProxyType = ProxyType.NONE
    proxy_host: str = ''
    proxy_port: int = 8080
    proxy_username: str = ''
    proxy_password: str = ''
    proxy_ignored_addresses: CommaList = field(
        default_factory=lambda: CommaList(['localhost', '127.0.0.1'])
    )

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
    change_file_date: FileDate = FileDate.NONE
    chmod_folder: str = ''
    chown_group: str = ''

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

    def todict(self, to_public: bool = True) -> Dict[str, Any]:
        """Convert the dataclass to a dictionary.

        Args:
            to_public (bool, optional): Whether to prepare the values to be
                shown to the public.
                Defaults to True.

        Returns:
            Dict[str, Any]: The keys and values.
        """
        result = asdict(self)

        if not to_public:
            return result

        for k, v in result.items():
            if k in ("auth_username", "auth_password", "proxy_password") and v:
                result[k] = Constants.CREDENTIAL_REPLACEMENT

            if isinstance(v, BaseEnum):
                result[k] = v.value

        return result


@dataclass(frozen=True)
class SettingsValues(PublicSettingsValues):
    """All settings including privates"""
    database_version: int = DatabaseMigrationHandler.latest_db_version()
    auth_salt: bytes = token_bytes()

    backup_host: str = '0.0.0.0'
    backup_port: int = 5656
    backup_url_base: str = ''


task_intervals = {
    # If there are tasks that should be run at the same time,
    # but per se after each other, put them in that order in the dict.
    'update_all': 3600, # every hour
    'search_all': 86400 # every day
}


class Settings(metaclass=Singleton):
    def __init__(self) -> None:
        self._insert_missing_settings()
        return

    def _insert_missing_settings(self) -> None:
        """Insert any missing keys from the settings into the database"""
        get_db().executemany(
            "INSERT OR IGNORE INTO config(key, value) VALUES (?, ?);",
            SettingsValues().todict(to_public=False).items()
        )
        commit()
        return

    @lru_cache(1)
    def get_settings(self) -> SettingsValues:
        """Get the settings, including internal ones.

        Returns:
            SettingsValues: The settings.
        """
        db_values = {
            k: v
            for k, v in get_db().execute(
                "SELECT key, value FROM config;"
            )
            if k in SettingsValues.__dataclass_fields__
        }

        # Database type for value is BLOB,
        # so manually convert types
        for key, value in db_values.items():
            key_type = SettingsValues.__dataclass_fields__[key].type
            if key_type is bool:
                db_values[key] = bool(value)

            if key_type is CommaList:
                db_values[key] = CommaList(db_values[key])

            if issubclass(key_type, BaseEnum):
                db_values[key] = key_type(value)

        return SettingsValues(**db_values)

    @lru_cache(1)
    def get_public_settings(self) -> PublicSettingsValues:
        """Get the public settings, so excluding internal ones.

        Returns:
            PublicSettingsValues: The public settings.
        """
        return PublicSettingsValues(
            **{
                k: v
                for k, v in self.get_settings().todict().items()
                if k in PublicSettingsValues.__dataclass_fields__
            }
        )

    def clear_cache(self) -> None:
        """Clear the cache of the settings"""
        self.get_settings.cache_clear()
        self.get_public_settings.cache_clear()
        return

    # Alias, better in one-liners
    # sv = Settings Values
    @property
    def sv(self) -> SettingsValues:
        """Get the settings, including internal ones.

        Returns:
            SettingsValues: The settings.
        """
        return self.get_settings()

    def update(
        self,
        data: Mapping[str, Any],
        from_public: bool = False
    ) -> None:
        """Change the settings, in a `dict.update()` type of way.

        Args:
            data (Mapping[str, Any]): The keys and their new values.

            from_public (bool, optional): If True, only allow public settings to
                be changed.
                Defaults to False.

        Raises:
            KeyNotFound: Key is not a setting.
            InvalidKeyValue: Value of the key is not allowed.
            InvalidSettingModification: Key can not be modified this way.
            FolderNotFound: Folder not found.
        """
        from backend.implementations.naming import (NAMING_MAPPING,
                                                    check_mock_filename)

        formatted_data = {}
        for key, value in data.items():
            formatted_data[key] = self.__format_value(key, value, from_public)

        if any(
            key in formatted_data
            for key in NAMING_MAPPING
        ):
            # Changes to naming schemes
            check_mock_filename(**{
                key: formatted_data.get(key)
                for key in NAMING_MAPPING
            })

        # Check whether setting combinations are valid
        self.__validate_settings(formatted_data)

        old_settings = self.get_settings()

        get_db().executemany(
            "UPDATE config SET value = ? WHERE key = ?;",
            ((v, k) for k, v in formatted_data.items())
        )

        if (
            'log_level' in data
            and formatted_data['log_level'] != old_settings.log_level
        ):
            set_log_level(formatted_data['log_level'])

        self.clear_cache()

        LOGGER.info(f'Settings changed: {formatted_data}')

        return

    def get_default_value(self, key: str) -> Any:
        """Get the default value of a setting.

        Args:
            key (str): The key of the setting.

        Returns:
            Any: The default value.
        """
        if not isinstance(
            SettingsValues.__dataclass_fields__[key].default_factory,
            _MISSING_TYPE
        ):
            return SettingsValues.__dataclass_fields__[key].default_factory()

        else:
            return SettingsValues.__dataclass_fields__[key].default

    def reset(self, key: str, from_public: bool) -> None:
        """Reset the value of the key to the default value.

        Args:
            key (str): The key of which to reset the value.
            from_public (bool): If True, only allow public settings to
                be reset.

        Raises:
            KeyNotFound: Key is not a setting.
            InvalidSettingModification: Key can not be modified this way.
        """
        LOGGER.debug(f'Setting reset: {key}')

        self.update({key: self.get_default_value(key)}, from_public=from_public)

        return

    def generate_api_key(self) -> None:
        """Generate a new api key"""
        LOGGER.debug('Generating new api key')

        api_key = urandom(16).hex()
        self.update({"api_key": api_key}, from_public=False)
        self.clear_cache()

        LOGGER.info(f'Setting api key regenerated: {api_key}')
        return

    def backup_hosting_settings(self) -> None:
        """Backup the hosting settings in the database"""
        s = self.get_settings()
        backup_settings = {
            'backup_host': s.host,
            'backup_port': s.port,
            'backup_url_base': s.url_base
        }
        self.update(backup_settings)
        return

    def restore_hosting_settings(self) -> None:
        """Restore the hosting settings from the database"""
        s = self.get_settings()
        restore_settings = {
            'host': s.backup_host,
            'port': s.backup_port,
            'url_prefix': s.backup_url_base
        }
        self.update(restore_settings)
        return

    def __format_value(self, key: str, value: Any, from_public: bool) -> Any:
        """Check if the value of a setting is allowed and convert if needed.

        Args:
            key (str): Key of setting.
            value (Any): Value of setting.
            from_public (bool): If True, only allow public settings
                to be changed.

        Raises:
            KeyNotFound: Key is not a setting.
            InvalidKeyValue: Value of the key is not allowed.
            InvalidSettingModification: Key can not be modified this way.
            FolderNotFound: Folder not found.

        Returns:
            Any: (Converted) Setting value.
        """
        KeyCollection = PublicSettingsValues if from_public else SettingsValues

        # Confirm that key exists
        if key not in KeyCollection.__dataclass_fields__:
            raise KeyNotFound(key)

        if key == 'api_key' and from_public:
            # Request generation of new key instead of setting value
            raise InvalidSettingModification(key, 'POST /settings/api_key')

        key_data = KeyCollection.__dataclass_fields__[key]

        # Convert type to special type
        if key_data.type is CommaList and isinstance(value, list):
            if not all(isinstance(e, str) for e in value):
                raise InvalidKeyValue(key, value)

            # Convert list to CommaList
            value = CommaList(value)

        elif issubclass(key_data.type, BaseEnum):
            # Convert string to Enum value
            try:
                value = key_data.type(value)
            except ValueError:
                raise InvalidKeyValue(key, value)

        # Confirm data type of submitted value
        if not isinstance(value, key_data.type):
            raise InvalidKeyValue(key, value)

        # Do key-specific checks and formatting
        converted_value = value

        if key == 'auth_username':
            if value == Constants.CREDENTIAL_REPLACEMENT:
                converted_value = self.sv.auth_username

            elif value:
                converted_value = hash_credential(
                    self.sv.auth_salt,
                    value
                )

        elif key == 'auth_password':
            if value == Constants.CREDENTIAL_REPLACEMENT:
                converted_value = self.sv.auth_password

            elif value:
                converted_value = hash_credential(
                    self.sv.auth_salt,
                    value
                )

        elif key in ('port', 'proxy_port') and not 0 < value <= 65_535:
            raise InvalidKeyValue(key, value)

        elif key == 'url_base':
            if value:
                converted_value = ('/' + value.lstrip('/')).rstrip('/')

        elif key == 'proxy_password':
            if value == Constants.CREDENTIAL_REPLACEMENT:
                converted_value = self.sv.proxy_password

        elif key == 'comicvine_api_key':
            from backend.implementations.comicvine import ComicVine
            converted_value = value.strip()
            if converted_value and not ComicVine(converted_value).test_key():
                raise InvalidKeyValue(key, value)

        elif key == 'download_folder':
            from backend.implementations.root_folders import RootFolders

            if not isdir(value):
                raise FolderNotFound(value)

            converted_value = uppercase_drive_letter(
                force_suffix(abspath(value))
            )

            if are_folders_colliding(
                converted_value,
                RootFolders().get_folder_list()
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

        elif key == 'chmod_folder':
            if System.os_type == OSType.WINDOWS:
                raise InvalidKeyValue(key, value)

            if value.startswith('0'):
                converted_value = value[1:]

            if converted_value and len(converted_value) != 3:
                raise InvalidKeyValue(key, value)

            for permission_target in converted_value:
                if permission_target not in (
                    '0', '1', '2', '3', '4', '5', '6', '7'
                ):
                    raise InvalidKeyValue(key, value)

            converted_value = (converted_value
                .replace('2', '3')
                .replace('4', '5')
                .replace('6', '7')
            )

        elif key == 'chown_group':
            # We can't change existing group to a group that the running user
            # isn't a part of. If that's needed, we need to be root.
            if value:
                if not (
                    System.os_type != OSType.WINDOWS
                    and getgrgid is not None # type: ignore
                    and getgrnam is not None
                ):
                    raise InvalidKeyValue(key, value)

                try:
                    getgrgid(int(value))
                except (TypeError, ValueError, KeyError):
                    try:
                        getgrnam(value)
                    except KeyError:
                        # Value is neither GID or group name
                        raise InvalidKeyValue(key, value)

        elif key == 'format_preference':
            from backend.implementations.converters import ConvertersManager

            available = ConvertersManager.get_available_formats()
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

        else:
            from backend.implementations.naming import (NAMING_MAPPING,
                                                        check_format)
            if key in NAMING_MAPPING:
                # Check naming formats
                converted_value = value.strip().strip(sep)
                if not check_format(converted_value, key):
                    raise InvalidKeyValue(key, value)

        return converted_value

    def __validate_settings(self, formatted_data: Mapping[str, Any]) -> None:
        """Validate a combination of setting values, NOT individual setting
        values. E.g. NOT validating individual proxy fields, but checking that
        there is a working connection based on all proxy fields together.

        Args:
            formatted_data (Mapping[str, Any]): The supplied changes to the
                settings, after having their fields validated and formatted
                by `__format_value()`. These values are overlapped over the
                existing values.

        Raises:
            InvalidKeyValue: Value of the key is not allowed.
        """
        settings_after_update = SettingsValues(**{
            **self.get_settings().todict(),
            **formatted_data
        })

        if settings_after_update.proxy_type != ProxyType.NONE:
            if not settings_after_update.proxy_host:
                raise InvalidKeyValue(
                    'proxy_host', settings_after_update.proxy_host
                )

            # Check whether proxy works
            proxy_url = build_proxy_url(
                settings_after_update.proxy_type,
                settings_after_update.proxy_host,
                settings_after_update.proxy_port,
                settings_after_update.proxy_username,
                settings_after_update.proxy_password,
            )
            if proxy_url:
                try:
                    test_proxy_url(
                        proxy_url,
                        settings_after_update.proxy_ignored_addresses
                    )

                except ClientNotWorking:
                    raise InvalidKeyValue(
                        'proxy_host', settings_after_update.proxy_host
                    )

                except CredentialInvalid:
                    raise InvalidKeyValue(
                        'proxy_username', settings_after_update.proxy_username
                    )

        return
