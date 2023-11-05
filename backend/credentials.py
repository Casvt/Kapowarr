#-*- coding: utf-8 -*-

import logging
from sqlite3 import IntegrityError
from typing import List

from backend.custom_exceptions import (CredentialAlreadyAdded,
                                       CredentialInvalid, CredentialNotFound,
                                       CredentialSourceNotFound)
from backend.db import get_db
from backend.lib.mega import Mega, RequestError


class Credentials:
	"""For interracting with the service credentials
	"""
	cache = {}
	__load_first = True
	
	def __init__(self, sids: dict) -> None:
		"""Set up the credential class

		Args:
			sids (dict): The sids variable at backend.lib.mega.sids
		"""
		self.sids = sids
		return
	
	def get_all(self, use_cache: bool=True) -> List[dict]:
		"""Get all credentials

		Args:
			use_cache (bool, optional): Wether or not to pull data from cache
			instead of going to the database.
				Defaults to True.

		Returns:
			List[dict]: The list of credentials
		"""		
		if not use_cache or not self.cache or self.__load_first:
			cred = dict(
				(c['id'], dict(c))
				for c in get_db('dict').execute("""
					SELECT
						c.id, cs.source,
						c.email, c.password
					FROM credentials c
					INNER JOIN credentials_sources cs
					ON c.source = cs.id;
					"""
				)
			)
			self.cache = cred
			self.__load_first = False

		return list(self.cache.values())
	
	def get_one(self, id: int, use_cache: bool=True) -> dict:
		"""Get a credential based on it's id.

		Args:
			id (int): The id of the credential to get.

			use_cache (bool, optional): Wether or not to pull data from cache
			instead of going to the database.
				Defaults to True.

		Raises:
			CredentialNotFound: The id doesn't map to any credential.
				Could also be because of cache being behind database.

		Returns:
			dict: The credential info
		"""		
		if not use_cache or self.__load_first:
			self.get_all(use_cache=False)
		cred = self.cache.get(id)
		if not cred:
			raise CredentialNotFound
		return cred

	def get_one_from_source(self, source: str, use_cache: bool=True) -> dict:
		"""Get a credential based on it's source string.

		Args:
			source (str): The source of which to get the credential.

			use_cache (bool, optional): Wether or not to pull data from cache
			instead of going to the database.
				Defaults to True.

		Returns:
			dict: The credential info or a 'ghost' version of the response
		"""
		if not use_cache or self.__load_first:
			self.get_all(use_cache=False)
		for cred in self.cache.values():
			if cred['source'] == source:
				return cred
			
		# If no cred is set for the source,
		# return a 'ghost' cred because other code can then
		# simply grab value of 'email' and 'password' and it'll be None
		return {
			'id': -1,
			'source': source,
			'email': None, 
			'password': None
		}

	def add(self, source: str, email: str, password: str) -> dict:
		"""Add a credential

		Args:
			source (str): The service for which the credential is.
				Must be a value of `settings.credential_sources`.

			email (str): The email of the credential.

			password (str): The password of the credential

		Raises:
			CredentialSourceNotFound: The source string doesn't map to any service.
			CredentialAlreadyAdded: The service already has a credential for it.

		Returns:
			dict: The credential info
		"""
		cursor = get_db()
		source_id = cursor.execute(
			"SELECT id FROM credentials_sources WHERE source = ? LIMIT 1;",
			(source,)
		).fetchone()
		if not source_id:
			raise CredentialSourceNotFound(source)

		logging.info(f'Adding credential for {source}')
		try:
			if source == 'mega':
				Mega('', email, password, only_check_login=True)
			
			id = get_db().execute("""
				INSERT INTO credentials(source, email, password)
				VALUES (?,?,?);
				""",
				(source_id[0], email, password)
			).lastrowid

		except RequestError:
			raise CredentialInvalid

		except IntegrityError:
			raise CredentialAlreadyAdded
		
		return self.get_one(id, use_cache=False)
	
	def delete(self, cred_id: int) -> None:
		"""Delete a credential

		Args:
			cred_id (int): The id of the credential to delete

		Raises:
			CredentialNotFound: The id doesn't map to any credential
		"""
		logging.info(f'Deleting credential: {cred_id}')
		
		if not get_db().execute(
			"DELETE FROM credentials WHERE id = ?", (cred_id,)
		).rowcount:
			raise CredentialNotFound

		self.get_all(use_cache=False)
		self.sids.clear()
		return

	def get_open(self) -> List[str]:
		"""Get a list of all services that
		don't have a credential registered for it

		Returns:
			List[str]: The list of service strings
		"""
		result = [
			s[0]
			for s in get_db().execute("""
				SELECT cs.source
				FROM credentials_sources cs
				LEFT JOIN credentials c
				ON cs.id = c.source
				WHERE c.id IS NULL;
			""")
		]

		return result
