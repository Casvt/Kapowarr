# -*- coding: utf-8 -*-

"""
Definitions of exceptions.
"""

from typing import Any, Union

from backend.base.definitions import (ApiResponse, BrokenClientReason,
                                      DownloadSource,
                                      EnqueuingDownloadFailureReason,
                                      KapowarrException)
from backend.base.logging import LOGGER


# region Input/Output
class KeyNotFound(KapowarrException):
    "A key was not found in the input that is required to be given"

    def __init__(self, key: str) -> None:
        self.key = key
        if key != "password":
            LOGGER.warning(
                "This key was not found in the API request, "
                "even though it's required: %s",
                key
            )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 400,
            "error": self.__class__.__name__,
            "result": {
                "key": self.key
            }
        }


class InvalidKey(KapowarrException):
    "The given key is not recognised. E.g. an invalid setting key."

    def __init__(self, key: str) -> None:
        self.key = key
        LOGGER.warning(
            f"The given key is not recognised: {key}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 400,
            "error": self.__class__.__name__,
            "result": {
                "key": self.key
            }
        }


class InvalidKeyValue(KapowarrException):
    "The value of a key is invalid"

    def __init__(self, key: str = '', value: Any = '') -> None:
        self.key = key
        self.value = value
        if value not in ("undefined", "null"):
            # Avoid logging when "null" API key is given by UI
            LOGGER.warning(
                "This key in the API request has an invalid value: "
                "%s = %s",
                key, value
            )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 400,
            "error": self.__class__.__name__,
            "result": {
                "key": self.key,
                "value": self.value
            }
        }


# region Settings
class InvalidSettingModification(KapowarrException):
    "The setting is not allowed to be changed this way"

    def __init__(self, key: str, instead: str):
        self.key = key
        self.instead = instead
        LOGGER.warning(
            f"This setting is not allowed to be changed this way: {key}. "
            f"Instead: {instead}")
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 400,
            "error": self.__class__.__name__,
            "result": {
                "key": self.key,
                "instead": self.instead
            }
        }


# region Folders/Files
class FolderNotFound(KapowarrException):
    "Folder not found"

    def __init__(self, folder: str) -> None:
        self.folder = folder
        LOGGER.warning(
            f"The folder was not found: {folder}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 404,
            "error": self.__class__.__name__,
            "result": {
                "folder": self.folder
            }
        }


class FileNotFound(KapowarrException):
    "File with given filepath or ID not found"

    def __init__(self, id_or_path: Union[int, str]) -> None:
        self.file_id = None
        self.filepath = None
        if isinstance(id_or_path, int):
            self.file_id = id_or_path
            LOGGER.warning(
                f"File with given ID not found: {id_or_path}"
            )
        else:
            self.filepath = id_or_path
            LOGGER.warning(
                f"File with given path not found: {id_or_path}"
            )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 404,
            "error": self.__class__.__name__,
            "result": {
                "file_id": self.file_id,
                "filepath": self.filepath
            }
        }


# region Rootfolders
class RootFolderNotFound(KapowarrException):
    "Rootfolder with given ID not found"

    def __init__(self, root_folder_id: int) -> None:
        self.root_folder_id = root_folder_id
        LOGGER.warning(
            f"Rootfolder with given ID not found: {root_folder_id}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 404,
            "error": self.__class__.__name__,
            "result": {
                "root_folder_id": self.root_folder_id
            }
        }


class RootFolderInUse(KapowarrException):
    """
    A root folder with the given ID is requested to be deleted
    but is used by a volume
    """

    def __init__(self, root_folder_id: int) -> None:
        self.root_folder_id = root_folder_id
        LOGGER.warning(
            "Rootfolder with the given ID is requested to be deleted "
            f"but is used by a volume: {root_folder_id}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 400,
            "error": self.__class__.__name__,
            "result": {
                "root_folder_id": self.root_folder_id
            }
        }


class RootFolderInvalid(KapowarrException):
    """
    The root folder is a parent or child of an existing root folder,
    which is not allowed
    """

    def __init__(self, folder: str) -> None:
        self.folder = folder
        LOGGER.warning(
            "The root folder is a parent or child of an existing root folder, "
            f"which is not allowed: {folder}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 400,
            "error": self.__class__.__name__,
            "result": {
                "folder": self.folder
            }
        }


# region Remote Mapping
class RemoteMappingNotFound(KapowarrException):
    "Remote mapping with given ID not found"

    def __init__(self, mapping_id: int) -> None:
        self.mapping_id = mapping_id
        LOGGER.warning(
            f"Remote mapping with given ID not found: {mapping_id}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 404,
            "error": self.__class__.__name__,
            "result": {
                "mapping_id": self.mapping_id
            }
        }


class RemoteMappingInvalid(KapowarrException):
    """
    A folder is a parent or child of an existing mapping folder,
    which is not allowed
    """

    def __init__(self, folder: str) -> None:
        self.folder = folder
        LOGGER.warning(
            "The mapped folder is a parent or child of an existing mapped folder, "
            f"which is not allowed: {folder}")
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 400,
            "error": self.__class__.__name__,
            "result": {
                "folder": self.folder
            }
        }


# region Volumes
class VolumeNotFound(KapowarrException):
    "The volume with the given (comicvine) key was not found"

    def __init__(self, volume_id: int) -> None:
        self.volume_id = volume_id
        LOGGER.warning(
            f"The volume with the given (comicvine) key was not found: {volume_id}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 404,
            "error": self.__class__.__name__,
            "result": {
                "volume_id": self.volume_id
            }
        }


class VolumeNotMatched(KapowarrException):
    "Volume not matched with ComicVine database"

    def __init__(self) -> None:
        LOGGER.warning(
            "Volume not matched with ComicVine database"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 400,
            "error": self.__class__.__name__,
            "result": {}
        }


class VolumeAlreadyAdded(KapowarrException):
    "The volume that is desired to be added is already added"

    def __init__(self, comicvine_id: int) -> None:
        self.comicvine_id = comicvine_id
        LOGGER.warning(
            "The volume that is desired to be added is already added: "
            f"CV {comicvine_id}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 400,
            "error": self.__class__.__name__,
            "result": {
                "comicvine_id": self.comicvine_id
            }
        }


class VolumeDownloadedFor(KapowarrException):
    "The volume is desired to be deleted but there is a download for it going"

    def __init__(self, volume_id: int) -> None:
        self.volume_id = volume_id
        LOGGER.warning(
            "The volume is desired to be deleted but "
            f"there is a download for it going: {volume_id}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 400,
            "error": self.__class__.__name__,
            "result": {
                "volume_id": self.volume_id
            }
        }


class TaskForVolumeRunning(KapowarrException):
    "The volume is desired to be deleted but there is a task running for it"

    def __init__(self, volume_id: int) -> None:
        self.volume_id = volume_id
        LOGGER.warning(
            "The volume is desired to be deleted but "
            f"there is a task running for it: {volume_id}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 400,
            "error": self.__class__.__name__,
            "result": {
                "volume_id": self.volume_id
            }
        }


class IssueNotFound(KapowarrException):
    "The issue with the given (comicvine) key was not found"

    def __init__(self, issue_id: int) -> None:
        self.issue_id = issue_id
        LOGGER.warning(
            f"The issue with the given (comicvine) key was not found: {issue_id}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 404,
            "error": self.__class__.__name__,
            "result": {
                "issue_id": self.issue_id
            }
        }


# region Tasks
class TaskNotFound(KapowarrException):
    "Task with given ID or name not found"

    def __init__(self, id_or_name: Union[int, str]) -> None:
        self.task_id = None
        self.task_name = None
        if isinstance(id_or_name, int):
            self.task_id = id_or_name
            LOGGER.warning(
                f"Task with given ID not found: {id_or_name}"
            )
        else:
            self.task_name = id_or_name
            LOGGER.warning(
                f"Task with given name not found: {id_or_name}"
            )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 404,
            "error": self.__class__.__name__,
            "result": {
                "task_id": self.task_id,
                "task_name": self.task_name
            }
        }


class TaskNotDeletable(KapowarrException):
    "The task could not be deleted because it's at the front of the queue"

    def __init__(self, task_id: int) -> None:
        self.task_id = task_id
        LOGGER.warning(
            "The task could not be deleted because "
            f"it's at the front of the queue: {task_id}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 400,
            "error": self.__class__.__name__,
            "result": {
                "task_id": self.task_id
            }
        }


# region Downloads
class DownloadNotFound(KapowarrException):
    "Download with given ID not found"

    def __init__(self, download_id: int) -> None:
        self.download_id = download_id
        LOGGER.warning(
            f"Download with given ID not found: {download_id}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 404,
            "error": self.__class__.__name__,
            "result": {
                "download_id": self.download_id
            }
        }


class LinkBroken(KapowarrException):
    "The link is broken"

    def __init__(self, link: str) -> None:
        self.link = link
        LOGGER.warning(
            f"Link is broken: {self.link}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 400,
            "error": self.__class__.__name__,
            "result": {
                "link": self.link
            }
        }


class EnqueuingDownloadFailure(KapowarrException):
    "Failed to enqueue download"

    def __init__(self, reason: EnqueuingDownloadFailureReason) -> None:
        self.reason = reason
        self.reason_text = reason.value
        LOGGER.warning(
            f"Failed to enqueue download: {self.reason_text}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 400,
            "error": self.__class__.__name__,
            "result": {
                "reason_text": self.reason.value
            }
        }


class DownloadLimitReached(KapowarrException):
    "The download limit of the source is reached"

    def __init__(self, source: DownloadSource) -> None:
        self.source = source
        self.source_text = source.value
        LOGGER.warning(
            f"Download source {self.source_text} has reached its download limit"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 509,
            "error": self.__class__.__name__,
            "result": {
                "source": self.source.value
            }
        }


class DownloadUnmovable(KapowarrException):
    "The position of the download in the queue can not be changed"

    def __init__(self, download_id: int) -> None:
        self.download_id = download_id
        LOGGER.warning(
            f"The position of the download in the queue can not be changed: {download_id}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 400,
            "error": self.__class__.__name__,
            "result": {
                "download_id": self.download_id
            }
        }


# region Credentials
class CredentialNotFound(KapowarrException):
    "Credential with given ID not found"

    def __init__(self, credential_id: int) -> None:
        self.credential_id = credential_id
        LOGGER.warning(
            f"Credential with given ID not found: {credential_id}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 404,
            "error": self.__class__.__name__,
            "result": {
                "credential_id": self.credential_id
            }
        }


class CredentialInvalid(KapowarrException):
    "Failed to login with the given credentials"

    def __init__(self) -> None:
        LOGGER.warning("Failed to login with the given credentials")
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 400,
            "error": self.__class__.__name__,
            "result": {}
        }


# region Download Clients
class ClientNotWorking(KapowarrException):
    "The download client is not working"

    def __init__(self, reason: BrokenClientReason) -> None:
        self.reason = reason
        self.reason_text = reason.value
        LOGGER.warning(
            f"The download client isn't working: {self.reason_text}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 400,
            "error": self.__class__.__name__,
            "result": {
                "reason_text": self.reason_text
            }
        }


class ExternalClientNotFound(KapowarrException):
    "External client with given ID not found"

    def __init__(self, external_client_id: int) -> None:
        self.external_client_id = external_client_id
        LOGGER.warning(
            f"External client with given ID not found: {external_client_id}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 404,
            "error": self.__class__.__name__,
            "result": {
                "external_client_id": self.external_client_id
            }
        }


class ExternalClientDownloading(KapowarrException):
    "External client is desired to be deleted but there is a download using it"

    def __init__(self, external_client_id: int) -> None:
        self.external_client_id = external_client_id
        LOGGER.warning(
            "The external client is desired to be deleted but "
            f"there is a download using it: {external_client_id}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 400,
            "error": self.__class__.__name__,
            "result": {
                "external_client_id": self.external_client_id
            }
        }


# region ComicVine
class CVRateLimitReached(KapowarrException):
    "ComicVine API rate limit reached"

    def __init__(self) -> None:
        LOGGER.warning(
            "Reached the rate limit of ComicVine"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 509,
            "error": self.__class__.__name__,
            "result": {}
        }


class InvalidComicVineApiKey(KapowarrException):
    "No Comic Vine API key is set or it's invalid"

    def __init__(self) -> None:
        LOGGER.warning(
            "No Comic Vine API key is set or it's invalid"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 400,
            "error": self.__class__.__name__,
            "result": {}
        }


# region Indexers
class IndexerRateLimitReached(KapowarrException):
    "Indexer rate limit has been reached"

    def __init__(self, indexer_name: str) -> None:
        self.indexer_name = indexer_name
        LOGGER.warning(
            f"Reached the rate limit of indexer: {indexer_name}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 509,
            "error": self.__class__.__name__,
            "result": {
                "indexer_name": self.indexer_name
            }
        }


class IndexerTemporarilyBlocked(KapowarrException):
    "Indexer is temporarily blocked due to repeated failures"

    def __init__(self, indexer_name: str, retry_time: int) -> None:
        self.indexer_name = indexer_name
        self.retry_time = retry_time
        LOGGER.info(
            f"Indexer {indexer_name} is temporarily blocked until {retry_time}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 503,
            "error": self.__class__.__name__,
            "result": {
                "indexer_name": self.indexer_name,
                "retry_time": self.retry_time
            }
        }


# region Blocklist
class BlocklistEntryNotFound(KapowarrException):
    "Blocklist entry with given ID not found"

    def __init__(self, blocklist_entry_id: int) -> None:
        self.blocklist_entry_id = blocklist_entry_id
        LOGGER.warning(
            f"Blocklist entry with given ID not found: {blocklist_entry_id}"
        )
        return

    @property
    def api_response(self) -> ApiResponse:
        return {
            "code": 404,
            "error": self.__class__.__name__,
            "result": {
                "blocklist_entry_id": self.blocklist_entry_id
            }
        }
