#-*- coding: utf-8 -*-

"""This file is for getting and setting up database connections
"""

import logging
from os import makedirs
from os.path import dirname
from sqlite3 import Connection, ProgrammingError, Row
from threading import current_thread
from time import time
from typing import List

from flask import g
from waitress.task import ThreadedTaskDispatcher as OldThreadedTaskDispatcher

from backend.logging import set_log_level

__DATABASE_FILEPATH__ = 'db', 'Kapowarr.db'
__DATABASE_VERSION__ = 14

class Singleton(type):
	_instances = {}
	def __call__(cls, *args, **kwargs):
		i = f'{cls}{current_thread()}'
		if (i not in cls._instances
		or cls._instances[i].closed):
			cls._instances[i] = super(Singleton, cls).__call__(*args, **kwargs)

		return cls._instances[i]

class ThreadedTaskDispatcher(OldThreadedTaskDispatcher):
	def handler_thread(self, thread_no: int) -> None:
		super().handler_thread(thread_no)
		i = f'{DBConnection}{current_thread()}'
		if i in Singleton._instances and not Singleton._instances[i].closed:
			Singleton._instances[i].close()

	def shutdown(self, cancel_pending: bool = True, timeout: int = 5) -> bool:
		logging.info('Shutting down Kapowarr...')
		super().shutdown(cancel_pending, timeout)
		DBConnection(20.0).close()

class DBConnection(Connection, metaclass=Singleton):
	"For creating a connection with a database"	
	file = ''
	
	def __init__(self, timeout: float) -> None:
		"""Create a connection with a database

		Args:
			timeout (float): How long to wait before giving up on a command
		"""
		logging.debug(f'Creating connection {self}')
		super().__init__(self.file, timeout=timeout)
		super().cursor().execute("PRAGMA foreign_keys = ON;")
		self.closed = False
		return
	
	def close(self) -> None:
		logging.debug(f'Closing connection {self}')
		self.closed = True
		super().close()
		return

	def __repr__(self) -> str:
		return f'<{self.__class__.__name__}; {current_thread().name}; {id(self)}>'

class TempDBConnection(Connection):
	"""For creating a temporary connection with a database.
	The user needs to manually commit and close.
	"""
	file = ''
	
	def __init__(self, timeout: float) -> None:
		"""Create a temporary connection with a database

		Args:
			timeout (float): How long to wait before giving up on a command
		"""
		logging.debug(f'Creating temporary connection {self}')
		super().__init__(self.file, timeout=timeout)
		super().cursor().execute("PRAGMA foreign_keys = ON;")
		self.closed = False
		return
	
	def close(self) -> None:
		logging.debug(f'Closing temporary connection {self}')
		self.closed = True
		super().close()
		return

	def __repr__(self) -> str:
		return f'<{self.__class__.__name__}; {current_thread().name}; {id(self)}>'

def set_db_location(db_file_location: str) -> None:
	"""Setup database location. Create folder for database
	and set location for db.DBConnection

	Args:
		db_file_location (str): The absolute path to the database file
	"""
	logging.debug(f'Setting database location: {db_file_location}')

	# Create folder where file will be put in if it doesn't exist yet
	makedirs(dirname(db_file_location), exist_ok=True)

	DBConnection.file = db_file_location
	TempDBConnection.file = db_file_location

	return

def get_db(output_type='tuple', temp: bool=False):
	"""Get a database cursor instance or create a new one if needed

	Args:
		output_type ('tuple'|'dict', optional): The type of output of the cursor.
			Defaults to 'tuple'.

		temp (bool, optional): Decides if a new manually handled cursor is returned
		instead of the cached one.
			Defaults to False.

	Returns:
		Cursor: Database cursor instance with desired output type set
	"""
	if temp:
		cursor = TempDBConnection(timeout=20.0).cursor()
	else:
		try:
			cursor = g.cursor
		except AttributeError:
			db = DBConnection(timeout=20.0)
			cursor = g.cursor = db.cursor()
		
	if output_type == 'dict':
		cursor.row_factory = Row
	else:
		cursor.row_factory = None

	return cursor

def close_db(e: str=None):
	"""Close database cursor, commit database and close database.

	Args:
		e (str, optional): Error. Defaults to None.
	"""
	try:
		cursor = g.cursor
		db: DBConnection = cursor.connection
		cursor.close()
		delattr(g, 'cursor')
		db.commit()
		if not current_thread().name.startswith('waitress-'):
			db.close()
	except (AttributeError, ProgrammingError):
		pass

	return

def update_db_version(desired_db_version: int) -> None:
	"""Set the database version to the value of the parameter.

	Args:
		desired_db_version (int): The version that the database should be set to.
	"""
	cursor = get_db()
	cursor.execute(
		"UPDATE config SET value = ? WHERE key = 'database_version';",
		(desired_db_version,)
	)
	cursor.connection.commit()
	return

def migrate_db(current_db_version: int) -> None:
	"""
	Migrate a Kapowarr database from it's current version
	to the newest version supported by the Kapowarr version installed.
	"""
	logging.info('Migrating database to newer version...')
	cursor = get_db()
	if current_db_version == 1:
		# V1 -> V2
		cursor.executescript("DELETE FROM download_queue;")
		
		current_db_version = 2
		update_db_version(current_db_version)

	if current_db_version == 2:
		# V2 -> V3
		cursor.executescript("""
			BEGIN TRANSACTION;
			PRAGMA defer_foreign_keys = ON;
			
			-- Issues
			CREATE TEMPORARY TABLE temp_issues AS
				SELECT * FROM issues;
			DROP TABLE issues;

			CREATE TABLE issues(
				id INTEGER PRIMARY KEY,
				volume_id INTEGER NOT NULL,
				comicvine_id INTEGER NOT NULL,
				issue_number VARCHAR(20) NOT NULL,
				calculated_issue_number FLOAT(20) NOT NULL,
				title VARCHAR(255),
				date VARCHAR(10),
				description TEXT,
				monitored BOOL NOT NULL DEFAULT 1,

				FOREIGN KEY (volume_id) REFERENCES volumes(id)
					ON DELETE CASCADE
			);
			INSERT INTO issues
				SELECT * FROM temp_issues;

			-- Issues files				
			CREATE TEMPORARY TABLE temp_issues_files AS
				SELECT * FROM issues_files;
			DROP TABLE issues_files;
			
			CREATE TABLE issues_files(
				file_id INTEGER NOT NULL,
				issue_id INTEGER NOT NULL,

				FOREIGN KEY (file_id) REFERENCES files(id)
					ON DELETE CASCADE,
				FOREIGN KEY (issue_id) REFERENCES issues(id),
				CONSTRAINT PK_issues_files PRIMARY KEY (
					file_id,
					issue_id
				)
			);
			INSERT INTO issues_files
				SELECT * FROM temp_issues_files;

			COMMIT;
		""")
		
		current_db_version = 3
		update_db_version(current_db_version)
	
	if current_db_version == 3:
		# V3 -> V4
		
		cursor.execute("""
			DELETE FROM files
			WHERE rowid IN (
				SELECT f.rowid
				FROM files f
				LEFT JOIN issues_files if
				ON f.id = if.file_id
				WHERE if.file_id IS NULL
			);
		""")

		current_db_version = 4
		update_db_version(current_db_version)
	
	if current_db_version == 4:
		# V4 -> V5
		from backend.files import process_issue_number

		cursor2 = get_db(temp=True)
		for result in cursor2.execute("SELECT id, issue_number FROM issues;"):
			calc_issue_number = process_issue_number(result[1])
			cursor.execute(
				"UPDATE issues SET calculated_issue_number = ? WHERE id = ?;",
				(calc_issue_number, result[0])
			)
		cursor2.connection.close()

		current_db_version = 5
		update_db_version(current_db_version)
	
	if current_db_version == 5:
		# V5 -> V6
		from backend.comicvine import ComicVine
		
		cursor.executescript("""
			BEGIN TRANSACTION;
			PRAGMA defer_foreign_keys = ON;

			-- Issues
			CREATE TEMPORARY TABLE temp_issues AS
				SELECT * FROM issues;
			DROP TABLE issues;

			CREATE TABLE IF NOT EXISTS issues(
				id INTEGER PRIMARY KEY,
				volume_id INTEGER NOT NULL,
				comicvine_id INTEGER UNIQUE NOT NULL,
				issue_number VARCHAR(20) NOT NULL,
				calculated_issue_number FLOAT(20) NOT NULL,
				title VARCHAR(255),
				date VARCHAR(10),
				description TEXT,
				monitored BOOL NOT NULL DEFAULT 1,

				FOREIGN KEY (volume_id) REFERENCES volumes(id)
					ON DELETE CASCADE
			);
			INSERT INTO issues
				SELECT * FROM temp_issues;
				
			-- Volumes
			ALTER TABLE volumes
				ADD last_cv_update VARCHAR(255);
			ALTER TABLE volumes
				ADD last_cv_fetch INTEGER(8) DEFAULT 0;
				
			COMMIT;
		""")

		volume_ids = [
			str(v[0])
			for v in cursor.execute("SELECT comicvine_id FROM volumes;")
		]
		updates = (
			(r['date_last_updated'], r['comicvine_id'])
			for r in ComicVine().fetch_volumes(volume_ids)
		)
		cursor.executemany(
			"UPDATE volumes SET last_cv_update = ? WHERE comicvine_id = ?;",
			updates
		)

		current_db_version = 6
		update_db_version(current_db_version)
		
	if current_db_version == 6:
		# V6 -> V7
		cursor.execute("""
			ALTER TABLE volumes
				ADD custom_folder BOOL NOT NULL DEFAULT 0;
		""")
		
		current_db_version = 7
		update_db_version(current_db_version)

	if current_db_version == 7:
		# V7 -> V8
		from backend.volumes import determine_special_version
		
		cursor.execute("""
			ALTER TABLE volumes
				ADD special_version VARCHAR(255);
		""")
		
		volumes = cursor.execute("""
			SELECT
				v.id,
				v.title,
				v.description,
				COUNT(*) AS issue_count,
				i.title AS first_issue_title
			FROM volumes v
			INNER JOIN issues i
			ON v.id = i.volume_id
			GROUP BY v.id;
		""").fetchall()

		updates = (
			(determine_special_version(v[1], v[2], v[3], v[4]) ,v[0])
			for v in volumes
		)

		cursor.executemany(
			"UPDATE volumes SET special_version = ? WHERE id = ?;",
			updates
		)
		
		current_db_version = 8
		update_db_version(current_db_version)

	if current_db_version == 8:
		# V8 -> V9
		cursor.executescript("""
			PRAGMA foreign_keys = OFF;

			CREATE TABLE new_volumes(
				id INTEGER PRIMARY KEY,
				comicvine_id INTEGER NOT NULL,
				title VARCHAR(255) NOT NULL,
				year INTEGER(5),
				publisher VARCHAR(255),
				volume_number INTEGER(8) DEFAULT 1,
				description TEXT,
				cover BLOB,
				monitored BOOL NOT NULL DEFAULT 0,
				root_folder INTEGER NOT NULL,
				folder TEXT,
				custom_folder BOOL NOT NULL DEFAULT 0,
				last_cv_fetch INTEGER(8) DEFAULT 0,
				special_version VARCHAR(255),
				
				FOREIGN KEY (root_folder) REFERENCES root_folders(id)
			);

			INSERT INTO new_volumes
				SELECT
					id, comicvine_id, title, year, publisher,
					volume_number, description, cover, monitored,
					root_folder, folder, custom_folder,
					0 AS last_cv_fetch, special_version
				FROM volumes;
		
			DROP TABLE volumes;

			ALTER TABLE new_volumes RENAME TO volumes;

			PRAGMA foreign_keys = ON;
		""")

		current_db_version = 9
		update_db_version(current_db_version)

	if current_db_version == 9:
		# V9 -> V10
		
		# Nothing is changed in the database
		# It's just that this code needs to run once
		# and the DB migration system does exactly that:
		# run pieces of code once.
		from backend.settings import update_manifest

		url_base: str = cursor.execute(
			"SELECT value FROM config WHERE key = 'url_base' LIMIT 1;"
		).fetchone()[0]
		update_manifest(url_base)
		
		current_db_version = 10
		update_db_version(current_db_version)

	if current_db_version == 10:
		# V10 -> V11
		from backend.volumes import determine_special_version

		volumes = cursor.execute("""
			SELECT
				id, title,
				description
			FROM volumes;
			"""
		).fetchall()

		updates = []
		for volume in volumes:
			issue_titles = [
				i[0] for i in cursor.execute(
					"SELECT title FROM issues WHERE volume_id = ?;",
					(volume[0],)
				)
			]
			updates.append(
				(determine_special_version(volume[1], volume[2], issue_titles),
	 			volume[0])
			)

		cursor.executemany(
			"UPDATE volumes SET special_version = ? WHERE id = ?;",
			updates
		)

		current_db_version = 11
		update_db_version(current_db_version)

	if current_db_version == 11:
		# V11 -> V12
		cursor.executescript("""
			DROP TABLE download_queue;

			CREATE TABLE download_queue(
				id INTEGER PRIMARY KEY,
				client_type VARCHAR(255) NOT NULL,
				torrent_client_id INTEGER,

				link TEXT NOT NULL,
				filename_body TEXT NOT NULL,
				source VARCHAR(25) NOT NULL,

				volume_id INTEGER NOT NULL,
				issue_id INTEGER,
				page_link TEXT,

				FOREIGN KEY (torrent_client_id) REFERENCES torrent_clients(id),
				FOREIGN KEY (volume_id) REFERENCES volumes(id),
				FOREIGN KEY (issue_id) REFERENCES issues(id)
			);
		""")

	if current_db_version == 12:
		# V12 -> V13
		unzip = cursor.execute(
			"SELECT value FROM config WHERE key = 'unzip' LIMIT 1;"
		).fetchone()[0]

		cursor.execute(
			"DELETE FROM config WHERE key = 'unzip';"
		)

		if unzip:
			cursor.executescript("""
				UPDATE config
				SET value = 'folder'
				WHERE key = 'format_preference';
				
				UPDATE config
				SET value = 1
				WHERE key = 'convert';
				"""
			)

	if current_db_version == 13:
		# V13 -> V14
		format_preference: List[str] = cursor.execute("""
			SELECT value
			FROM config
			WHERE key = 'format_preference'
			LIMIT 1;
		""").fetchone()[0].split(',')
		
		if 'folder' in format_preference:
			cursor.execute("""
				UPDATE config
				SET value = 1
				WHERE key = 'extract_issue_ranges';
				"""
			)
			format_preference.remove('folder')
			cursor.execute("""
				UPDATE config
				SET value = ?
				WHERE key = 'format_preference';
				""",
				(",".join(format_preference),)
			)

	return

def setup_db() -> None:
	"""Setup the database tables and default config when they aren't setup yet
	"""
	from backend.settings import (Settings, blocklist_reasons, credential_sources,
	                              default_settings, supported_source_strings,
	                              task_intervals)

	cursor = get_db()
	cursor.execute("PRAGMA journal_mode = wal;")

	setup_commands = """
		CREATE TABLE IF NOT EXISTS config(
			key VARCHAR(100) PRIMARY KEY,
			value BLOB
		);
		CREATE TABLE IF NOT EXISTS root_folders(
			id INTEGER PRIMARY KEY,
			folder VARCHAR(254) UNIQUE NOT NULL
		);
		CREATE TABLE IF NOT EXISTS volumes(
			id INTEGER PRIMARY KEY,
			comicvine_id INTEGER NOT NULL,
			title VARCHAR(255) NOT NULL,
			year INTEGER(5),
			publisher VARCHAR(255),
			volume_number INTEGER(8) DEFAULT 1,
			description TEXT,
			cover BLOB,
			monitored BOOL NOT NULL DEFAULT 0,
			root_folder INTEGER NOT NULL,
			folder TEXT,
			custom_folder BOOL NOT NULL DEFAULT 0,
			last_cv_fetch INTEGER(8) DEFAULT 0,
			special_version VARCHAR(255),
			
			FOREIGN KEY (root_folder) REFERENCES root_folders(id)
		);
		CREATE TABLE IF NOT EXISTS issues(
			id INTEGER PRIMARY KEY,
			volume_id INTEGER NOT NULL,
			comicvine_id INTEGER NOT NULL UNIQUE,
			issue_number VARCHAR(20) NOT NULL,
			calculated_issue_number FLOAT(20) NOT NULL,
			title VARCHAR(255),
			date VARCHAR(10),
			description TEXT,
			monitored BOOL NOT NULL DEFAULT 1,

			FOREIGN KEY (volume_id) REFERENCES volumes(id)
				ON DELETE CASCADE
		);
		CREATE INDEX IF NOT EXISTS issues_volume_number_index
			ON issues(volume_id, calculated_issue_number);
		CREATE TABLE IF NOT EXISTS files(
			id INTEGER PRIMARY KEY,
			filepath TEXT UNIQUE NOT NULL,
			size INTEGER
		);
		CREATE TABLE IF NOT EXISTS issues_files(
			file_id INTEGER NOT NULL,
			issue_id INTEGER NOT NULL,

			FOREIGN KEY (file_id) REFERENCES files(id)
				ON DELETE CASCADE,
			FOREIGN KEY (issue_id) REFERENCES issues(id),
			CONSTRAINT PK_issues_files PRIMARY KEY (
				file_id,
				issue_id
			)
		);
		CREATE TABLE IF NOT EXISTS torrent_clients(
			id INTEGER PRIMARY KEY,
			type VARCHAR(255) NOT NULL,
			title VARCHAR(255) NOT NULL,
			base_url TEXT NOT NULL,
			username VARCHAR(255),
			password VARCHAR(255),
			api_token VARCHAR(255)
		);
		CREATE TABLE IF NOT EXISTS download_queue(
			id INTEGER PRIMARY KEY,
			client_type VARCHAR(255) NOT NULL,
			torrent_client_id INTEGER,

			link TEXT NOT NULL,
			filename_body TEXT NOT NULL,
			source VARCHAR(25) NOT NULL,

			volume_id INTEGER NOT NULL,
			issue_id INTEGER,
			page_link TEXT,

			FOREIGN KEY (torrent_client_id) REFERENCES torrent_clients(id),
			FOREIGN KEY (volume_id) REFERENCES volumes(id),
			FOREIGN KEY (issue_id) REFERENCES issues(id)
		);
		CREATE TABLE IF NOT EXISTS download_history(
			original_link TEXT NOT NULL,
			title TEXT NOT NULL,
			downloaded_at INTEGER NOT NULL
		);
		CREATE TABLE IF NOT EXISTS task_history(
			task_name NOT NULL,
			display_title NOT NULL,
			run_at INTEGER NOT NULL
		);
		CREATE TABLE IF NOT EXISTS task_intervals(
			task_name PRIMARY KEY,
			interval INTEGER NOT NULL,
			next_run INTEGER NOT NULL
		);
		CREATE TABLE IF NOT EXISTS blocklist_reasons(
			id INTEGER PRIMARY KEY,
			reason TEXT NOT NULL UNIQUE
		);
		CREATE TABLE IF NOT EXISTS blocklist(
			id INTEGER PRIMARY KEY,
			link TEXT NOT NULL UNIQUE,
			reason INTEGER NOT NULL,
			added_at INTEGER NOT NULL,

			FOREIGN KEY (reason) REFERENCES blocklist_reasons(id)
		);
		CREATE TABLE IF NOT EXISTS credentials_sources(
			id INTEGER PRIMARY KEY,
			source VARCHAR(30) NOT NULL UNIQUE
		);
		CREATE TABLE IF NOT EXISTS credentials(
			id INTEGER PRIMARY KEY,
			source INTEGER NOT NULL UNIQUE,
			email VARCHAR(255) NOT NULL,
			password VARCHAR(255) NOT NULL,
			
			FOREIGN KEY (source) REFERENCES credentials_sources(id)
				ON DELETE CASCADE
		);
		CREATE TABLE IF NOT EXISTS service_preference(
			source VARCHAR(30) UNIQUE NOT NULL,
			pref INTEGER UNIQUE CHECK (pref >= 1)
		);
	"""
	cursor.executescript(setup_commands)

	# Insert default setting values for keys that
	# don't have a value yet or have newly been added
	cursor.executemany(
		"""
		INSERT OR IGNORE INTO config
		VALUES (?,?);
		""",
		default_settings.items()
	)
	
	set_log_level(cursor.execute(
		"SELECT value FROM config WHERE key = 'log_level' LIMIT 1;"
	).fetchone()[0])

	# Migrate database if needed
	current_db_version = int(cursor.execute(
		"SELECT value FROM config WHERE key = 'database_version' LIMIT 1;"
	).fetchone()[0])

	if current_db_version < __DATABASE_VERSION__:
		logging.debug(
			f'Database migration: {current_db_version} -> {__DATABASE_VERSION__}'
		)
		migrate_db(current_db_version)
		# Redundant but just to be sure, in case
		# the version isn't updated in the last migration of the function
		update_db_version(__DATABASE_VERSION__)

	# Generate api key
	api_key_exists = (None,) not in cursor.execute(
		"SELECT value FROM config WHERE key = 'api_key' LIMIT 1;"
	)
	if not api_key_exists:
		Settings().generate_api_key()

	# Add task intervals
	logging.debug(f'Inserting task intervals: {task_intervals}')
	current_time = round(time())
	cursor.executemany(
		"""
		INSERT INTO task_intervals
		VALUES (?, ?, ?)
		ON CONFLICT(task_name) DO
		UPDATE
		SET
			interval = ?;
		""",
		((k, v, current_time, v) for k, v in task_intervals.items())
	)
	
	# Add blocklist reasons
	logging.debug(f'Inserting blocklist reasons: {blocklist_reasons}')
	cursor.executemany(
		"""
		INSERT OR IGNORE INTO blocklist_reasons(id, reason)
		VALUES (?,?);
		""",
		blocklist_reasons.items()
	)
	
	# Add credentials sources
	logging.debug(f'Inserting credentials sources: {credential_sources}')
	cursor.executemany(
		"""
		INSERT OR IGNORE INTO credentials_sources(source)
		VALUES (?);
		""",
		[(s,) for s in credential_sources]
	)

	# Add service preferences
	order = [
		(names[0], place + 1)
		for place, names in enumerate(supported_source_strings)
	]
	logging.debug(f'Inserting service preferences: {order}')
	cursor.executemany(
		"""
		INSERT OR IGNORE INTO service_preference(source, pref)
		VALUES (?,?);
		""",
		order
	)

	return
