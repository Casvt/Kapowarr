#-*- coding: utf-8 -*-

import logging
from sqlite3 import IntegrityError
from time import time
from typing import Any, Dict, List

from backend.custom_exceptions import BlocklistEntryNotFound
from backend.db import get_db
from backend.enums import BlocklistReason, BlocklistReasonID


def get_blocklist(offset: int=0) -> List[Dict[str, Any]]:
	"""Get the blocklist entries in blocks of 50

	Args:
		offset (int, optional): The offset of the list.
			The higher the number, the deeper into the list you go.

			Defaults to 0.

	Returns:
		List[Dict[str, Any]]: A list of dicts where each dict is a blocklist entry
	"""
	logging.debug(f'Fetching blocklist with offset {offset}')
	entries = list(map(
		dict,
		get_db(dict).execute("""
			SELECT
				id,
				link,
				reason,
				added_at
			FROM blocklist
			ORDER BY id DESC
			LIMIT 50
			OFFSET ?;
		""", (offset * 50,))
	))
	for entry in entries:
		entry.update({
			'reason': BlocklistReason[
				BlocklistReasonID(entry['reason']).name
			].value
		})

	return entries

def delete_blocklist() -> None:
	"""Delete all blocklist entries
	"""
	logging.info('Deleting blocklist')
	get_db().execute(
		"DELETE FROM blocklist;"
	)
	return

def get_blocklist_entry(id: int) -> Dict[str, Any]:
	"""Get info about a blocklist entry

	Args:
		id (int): The id of the blocklist entry

	Raises:
		BlocklistEntryNotFound: The id doesn't map to any blocklist entry

	Returns:
		Dict[str, Any]: The info about the blocklist entry, similar to the dicts
		in the output of `blocklist.get_blocklist()`
	"""
	logging.debug(f'Fetching blocklist entry {id}')
	entry = get_db(dict).execute("""
		SELECT
			id,
			link,
			reason,
			added_at
		FROM blocklist
		WHERE id = ?
		LIMIT 1;
		""",
		(id,)
	).fetchone()

	if not entry:
		raise BlocklistEntryNotFound

	result = dict(entry)
	result['reason'] = BlocklistReason[
		BlocklistReasonID(result['reason']).name
	].value
	return result

def delete_blocklist_entry(id: int) -> None:
	"""Delete a blocklist entry

	Args:
		id (int): The id of the blocklist entry

	Raises:
		BlocklistEntryNotFound: The id doesn't map to any blocklist entry
	"""
	logging.debug(f'Deleting blocklist entry {id}')
	entry_found = get_db().execute(
		"DELETE FROM blocklist WHERE id = ?",
		(id,)
	).rowcount

	if entry_found:
		return
	raise BlocklistEntryNotFound

def blocklist_contains(link: str) -> bool:
	"""Check if a link is in the blocklist

	Args:
		link (str): The link to check for

	Returns:
		bool: `True` if the link is in the blocklist, otherwise `False`.
	"""
	result = (1,) in get_db().execute(
		"SELECT 1 FROM blocklist WHERE link = ? LIMIT 1",
		(link,)
	)
	return result

def add_to_blocklist(link: str, reason: BlocklistReason) -> Dict[str, Any]:
	"""Add a link to the blocklist

	Args:
		link (str): The link to block
		reason (BlocklistReasons): The reason why the link is blocklisted.
			See `backend.enums.BlocklistReason`.

	Returns:
		Dict[str, Any]: Info about the blocklist entry.
	"""
	logging.info(f'Adding {link} to blocklist with reason "{reason.value}"')
	cursor = get_db()
	reason_id = BlocklistReasonID[reason.name].value

	# Try to add link to blocklist
	try:
		id = cursor.execute(
			"INSERT INTO blocklist(link, reason, added_at) VALUES (?, ?, ?);",
			(link, reason_id, round(time()))
		).lastrowid
	except IntegrityError:
		# Check if link isn't already in blocklist
		id = cursor.execute(
			"SELECT id FROM blocklist WHERE link = ? LIMIT 1",
			(link,)
		).fetchone()
		if id:
			return get_blocklist_entry(id[0])
		raise NotImplementedError

	return get_blocklist_entry(id)
