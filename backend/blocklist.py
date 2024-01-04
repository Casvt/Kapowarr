#-*- coding: utf-8 -*-

import logging
from sqlite3 import IntegrityError
from time import time
from typing import List

from backend.custom_exceptions import BlocklistEntryNotFound, InvalidKeyValue
from backend.db import get_db
from backend.settings import blocklist_reasons


def get_blocklist(offset: int=0) -> List[dict]:
	"""Get the blocklist entries in blocks of 50

	Args:
		offset (int, optional): The offset of the list.
			The higher the number, the deeper into the list you go.
			
			Defaults to 0.

	Returns:
		List[dict]: A list of dicts where each dict is a blocklist entry
	"""	
	logging.debug(f'Fetching blocklist with offset {offset}')
	entries = list(map(
		dict,
		get_db(dict).execute("""
			SELECT
				bl.id,
				bl.link,
				blr.reason,
				bl.added_at
			FROM blocklist bl
			INNER JOIN blocklist_reasons blr
			ON bl.reason = blr.id
			ORDER BY bl.id DESC
			LIMIT 50
			OFFSET ?;
		""", (offset * 50,))
	))
	
	return entries

def delete_blocklist() -> None:
	"""Delete all blocklist entries
	"""	
	logging.info('Deleting blocklist')
	get_db().execute(
		"DELETE FROM blocklist;"
	)
	return

def get_blocklist_entry(id: int) -> dict:
	"""Get info about a blocklist entry

	Args:
		id (int): The id of the blocklist entry

	Raises:
		BlocklistEntryNotFound: The id doesn't map to any blocklist entry

	Returns:
		dict: The info about the blocklist entry, similar to the dicts in
		the output of `blocklist.get_blocklist()`
	"""	
	logging.debug(f'Fetching blocklist entry {id}')
	entry = get_db(dict).execute("""
		SELECT
			bl.id,
			bl.link,
			blr.reason,
			bl.added_at
		FROM blocklist bl
		INNER JOIN blocklist_reasons blr
		ON bl.reason = blr.id
		WHERE bl.id = ?
		LIMIT 1;
	""", (id,)).fetchone()
	if entry:
		return dict(entry)
	raise BlocklistEntryNotFound

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

def add_to_blocklist(link: str, reason_id: int) -> dict:
	"""Add a link to the blocklist

	Args:
		link (str): The link to block
		reason_id (int): The id of the reason why the link is blocklisted.
			See `settings.blocklist_reasons`

	Raises:
		InvalidKeyValue: The reason id doesn't map to any reason

	Returns:
		dict: Info about the blocklist entry.
	"""	
	logging.info(f'Adding {link} to blocklist with reason "{blocklist_reasons[reason_id]}"')
	cursor = get_db()

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

		raise InvalidKeyValue('reason', reason_id)

	return get_blocklist_entry(id)
