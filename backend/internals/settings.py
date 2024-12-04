# -*- coding: utf-8 -*-

from dataclasses import _MISSING_TYPE, asdict, dataclass, field
from json import dump, load
from logging import INFO
from os import urandom
from os.path import abspath, isdir, join, sep
from typing import Any, Dict, Mapping

from backend.base.custom_exceptions import (FolderNotFound, InvalidSettingKey,
                                            InvalidSettingModification,
                                            InvalidSettingValue)
from backend.base.definitions import (BaseEnum, GCDownloadSource,
                                      RestartVersion, SeedingHandling)
from backend.base.files import (folder_is_inside_folder,
                                folder_path, uppercase_drive_letter)
from backend.base.helpers import (CommaList, Singleton, force_suffix,
                                  get_python_version, reversed_tuples)
from backend.base.logging import LOGGER, set_log_level
from backend.internals.db import commit, get_db
from backend.internals.db_migration import get_latest_db_version


@dataclass(frozen=True)
class SettingsValues:
    database_version: int = get_latest_db_version()
    log_level: int = INFO
    auth_password: str = ''
    comicvine_api_key: str = ''
    api_key: str = ''

    host: str = '0.0.0.0'
    port: int = 5656
    url_base: str = ''
    backup_host: str = '0.0.0.0'
    backup_port: int = 5656
    backup_url_base: str = ''

    rename_downloaded_files: bool = True
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

    service_preference: CommaList = field(default_factory=lambda: CommaList(
        (s.value for s in GCDownloadSource._member_map_.values())
    ))
    download_folder: str = folder_path('temp_downloads')
    seeding_handling: SeedingHandling = SeedingHandling.COPY
    delete_completed_torrents: bool = True

    convert: bool = False
    extract_issue_ranges: bool = False
    format_preference: CommaList = field(default_factory=lambda: CommaList(''))

    flaresolverr_base_url: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            k: v if not isinstance(v, BaseEnum) else v.value
            for k, v in self.__dict__.items()
            if not k.startswith('backup_')
        }


about_data = {
    'version': 'alpha-32',
    'python_version': get_python_version(),
    'database_version': get_latest_db_version(),
    'database_location': None, # Get's filled in by db.set_db_location()
    'data_folder': folder_path()
}


task_intervals = {
    # If there are tasks that should be run at the same time,
    # but per se after each other, put them in that order in the dict.
    'update_all': 3600, # every hour
    'search_all': 86400 # every day
}


credential_sources = ('mega',)


class Settings(metaclass=Singleton):
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

        for cl_key in ('format_preference', 'service_preference'):
            db_values[cl_key] = CommaList(db_values[cl_key])

        for en_key, en in (
            ('seeding_handling', SeedingHandling),
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
            InvalidSettingKey: Key is not allowed or unknown.
            InvalidSettingValue: Value of the key is not allowed.
            InvalidSettingModification: Key can not be modified this way.
            FolderNotFound: Folder not found.
        """
        from backend.implementations.naming import (NAMING_MAPPING,
                                                    check_mock_filename)

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

        if hosting_changes:
            self.backup_hosting_settings()

        get_db().executemany(
            "UPDATE config SET value = ? WHERE key = ?;",
            reversed_tuples(formatted_data.items())
        )

        for key, handler in (
            ('url_base', update_manifest),
            ('log_level', set_log_level)
        ):
            if (
                key in data
                and formatted_data[key] != getattr(self.get_settings(), key)
            ):
                handler(formatted_data[key])

        self._fetch_settings()

        LOGGER.info(f'Settings changed: {formatted_data}')

        if hosting_changes:
            from backend.internals.server import SERVER
            SERVER.restart(
                RestartVersion.HOSTING_CHANGES
            )

        return

    def __setitem__(self, __name: str, __value: Any) -> None:
        """Change the value of a setting.

        Args:
            __name (str): The key of the setting.
            __value (Any): The new value.

        Raises:
            InvalidSettingKey: Key is not allowed or unknown.
            InvalidSettingValue: Value of the key is not allowed.
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
            InvalidSettingKey: The key is not valid or unknown.
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
            InvalidSettingKey: Key is invalid or unknown.
            InvalidSettingValue: Value is not allowed.
            InvalidSettingModification: Key can not be modified this way.
            FolderNotFound: Folder not found.

        Returns:
            Any: (Converted) Setting value.
        """
        converted_value = value

        if key not in SettingsValues.__dataclass_fields__:
            raise InvalidSettingKey(key)

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
                raise InvalidSettingValue(key, value)

        if not isinstance(value, SettingsValues.__dataclass_fields__[key].type):
            raise InvalidSettingValue(key, value)

        if key == 'port' and not 0 < value <= 65_535:
            raise InvalidSettingValue(key, value)

        elif key == 'url_base':
            if value:
                converted_value = ('/' + value.lstrip('/')).rstrip('/')

        elif key == 'comicvine_api_key':
            from backend.implementations.comicvine import ComicVine
            converted_value = value.strip()
            if not ComicVine(converted_value).test_token():
                raise InvalidSettingValue(key, value)

        elif key == 'download_folder':
            from backend.implementations.root_folders import RootFolders

            if not isdir(value):
                raise FolderNotFound

            converted_value = uppercase_drive_letter(
                force_suffix(abspath(value))
            )

            for rf in RootFolders().get_all():
                if (
                    folder_is_inside_folder(rf.folder, converted_value)
                    or folder_is_inside_folder(converted_value, rf.folder)
                ):
                    raise InvalidSettingValue(key, value)

        elif key == 'volume_padding' and not 1 <= value <= 3:
            raise InvalidSettingValue(key, value)

        elif key == 'issue_padding' and not 1 <= value <= 4:
            raise InvalidSettingValue(key, value)

        elif key == 'format_preference':
            from backend.implementations.conversion import \
                get_available_formats

            available = get_available_formats()
            for entry in value:
                if entry not in available:
                    raise InvalidSettingValue(key, value)

            converted_value = value

        elif key == 'service_preference':
            available = [
                s.value
                for s in GCDownloadSource._member_map_.values()
            ]
            for entry in value:
                if entry not in available:
                    raise InvalidSettingValue(key, value)
            for entry in available:
                if entry not in value:
                    raise InvalidSettingValue(key, value)

            converted_value = value

        elif key == 'flaresolverr_base_url':
            from backend.implementations.flaresolverr import FlareSolverr

            fs = FlareSolverr()

            converted_value = value.rstrip("/")
            if not converted_value and fs.base_url:
                # Disable FS, it was running before.
                fs.disable_flaresolverr()

            elif converted_value and not fs.base_url:
                # Enable FS, it wasn't running before.
                if not fs.enable_flaresolverr(converted_value):
                    raise InvalidSettingValue(key, value)

            elif (
                converted_value
                and fs.base_url
                and converted_value != fs.base_url
            ):
                # Enable FS, it was running before but on a different instance.
                old_value = fs.base_url
                fs.disable_flaresolverr()
                if not fs.enable_flaresolverr(converted_value):
                    fs.enable_flaresolverr(old_value)
                    raise InvalidSettingValue(key, value)

        else:
            from backend.implementations.naming import (NAMING_MAPPING,
                                                        check_format)
            if key in NAMING_MAPPING:
                converted_value = value.strip().strip(sep)
                if not check_format(converted_value, key):
                    raise InvalidSettingValue(key, value)

        return converted_value


def update_manifest(url_base: str) -> None:
    """Update the url's in the manifest file.
    Needs to happen when url base changes.

    Args:
        url_base (str): The url base to use in the file.
    """
    filename = folder_path('frontend', 'static', 'json', 'pwa_manifest.json')

    with open(filename, 'r') as f:
        manifest = load(f)
        manifest['start_url'] = url_base + '/'
        manifest['icons'][0]['src'] = f'{url_base}/static/img/favicon.svg'

    with open(filename, 'w') as f:
        dump(manifest, f, indent=4)

    return
