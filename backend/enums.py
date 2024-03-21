#-*- coding: utf-8 -*-

from enum import Enum


class BaseEnum(Enum):
	def __eq__(self, other: object) -> bool:
		return self.value == other

class SeedingHandling(BaseEnum):
	COMPLETE = 'complete'
	"Let torrent complete (finish seeding) and then move all files"

	COPY = 'copy'
	"Copy the files while the torrent is seeding, then delete original files"

class BlocklistReasonID(BaseEnum):
	LINK_BROKEN = 1
	SOURCE_NOT_SUPPORTED = 2
	NO_WORKING_LINKS = 3
	ADDED_BY_USER = 4

class BlocklistReason(BaseEnum):
	LINK_BROKEN = 'Link broken'

	SOURCE_NOT_SUPPORTED = 'Source not supported'

	NO_WORKING_LINKS = 'No supported or working links'

	ADDED_BY_USER = 'Added by user'

class SpecialVersion(BaseEnum):
	TPB = 'tpb'

	ONE_SHOT = 'one-shot'

	HARD_COVER = 'hard-cover'

	VOLUME_AS_ISSUE = 'volume-as-issue'
	"Volume where each issue is named `Volume N`"

	NORMAL = None
	"Normal volume, so not a special version"

class DownloadState(BaseEnum):
	QUEUED_STATE = 'queued'
	DOWNLOADING_STATE = 'downloading'
	SEEDING_STATE = 'seeding'
	IMPORTING_STATE = 'importing'

	FAILED_STATE = 'failed'
	"Download was unsuccessful"
	CANCELED_STATE = 'canceled'
	"Download was removed from queue"
	SHUTDOWN_STATE = 'shutting down'
	"Download was stopped because Kapowarr is shutting down"

class SocketEvent(BaseEnum):
	DISCONNECT = 'request_disconnect'

	TASK_ADDED = 'task_added'
	TASK_STATUS = 'task_status'
	TASK_ENDED = 'task_ended'

	QUEUE_ADDED = 'queue_added'
	QUEUE_STATUS = 'queue_status'
	QUEUE_ENDED = 'queue_ended'
