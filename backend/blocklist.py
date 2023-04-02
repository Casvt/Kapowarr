#-*- coding: utf-8 -*-

"""This file contains all functions to interract with the blocklist
"""

from sqlite3 import IntegrityError
from time import time
from typing import List

from backend.custom_exceptions import BlocklistEntryNotFound, InvalidKeyValue
from backend.db import get_db

def get_blocklist() -> List[dict]:
	entries = get_db('dict').execute("""
		SELECT
			bl.id,
			bl.link,
			blr.reason,
			bl.added_at
		FROM
			blocklist AS bl,
			blocklist_reasons AS blr
		WHERE
			bl.reason = blr.id
		ORDER BY bl.id DESC;
	""").fetchall()
	entries = list(map(dict, entries))
	
	return entries

def delete_blocklist() -> None:
	get_db().execute(
		"DELETE FROM blocklist"
	)
	return

def get_blocklist_entry(id: int) -> dict:
	entry = get_db('dict').execute("""
		SELECT
			bl.id,
			bl.link,
			blr.reason,
			bl.added_at
		FROM
			blocklist AS bl,
			blocklist_reasons AS blr
		WHERE
			bl.reason = blr.id
			AND bl.id = ?
		LIMIT 1;
	""", (id,)).fetchone()
	if entry:
		return dict(entry)
	raise BlocklistEntryNotFound

def delete_blocklist_entry(id: int) -> None:
	entry_found = get_db().execute(
		"DELETE FROM blocklist WHERE id = ?",
		(id,)
	).rowcount
	
	if entry_found:
		return
	raise BlocklistEntryNotFound

def blocklist_contains(link: str) -> bool:
	result = get_db().execute(
		"SELECT 1 FROM blocklist WHERE link = ? LIMIT 1",
		(link,)
	).fetchone()
	return result is not None

def add_to_blocklist(link: str, reason_id: int) -> dict:
	cursor = get_db()
	
	# Check if link isn't already in blocklist
	id = cursor.execute("SELECT id FROM blocklist WHERE link = ? LIMIT 1", (link,)).fetchone()
	if id:
		return get_blocklist_entry(id[0])

	# Add link to blocklist
	try:
		id = cursor.execute(
			"INSERT INTO blocklist(link, reason, added_at) VALUES (?, ?, ?);",
			(link, reason_id, round(time()))
		).lastrowid
	except IntegrityError:
		raise InvalidKeyValue('reason', reason_id)

	return get_blocklist_entry(id)
