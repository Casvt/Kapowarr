# -*- coding: utf-8 -*-

from typing import Any, Callable, Dict, List, Tuple

from backend.base.custom_exceptions import CredentialNotFound
from backend.base.definitions import CredentialData, CredentialSource
from backend.base.logging import LOGGER
from backend.internals.db import get_db


class Credentials:
    auth_tokens: Dict[CredentialSource, Dict[str, Tuple[Any, int]]] = {}
    """
    Store auth tokens as to avoid logging in while already having a cleared
    token. Maps from credential source to user identifier (something like user
    ID, email or username) to a tuple of the token and its expiration time.
    """

    validators: Dict[
        CredentialSource,
        Callable[[CredentialData], CredentialData]
    ] = {}
    "The validators may raise ClientNotWorking or CredentialInvalid"

    @classmethod
    def register_validator(cls, source: CredentialSource):
        """Register a validator of credentials for a certain source.

        Args:
            source (CredentialSource): The credential source.

        Raises:
            RuntimeError: A credential validator with the given source is
                already registered.
        """
        def wrapper(
            validator: Callable[[CredentialData], CredentialData]
        ) -> Callable[[CredentialData], CredentialData]:
            if source in cls.validators:
                raise RuntimeError(
                    f"Credential validator with source {source.value} "
                    "registered multiple times"
                )
            cls.validators[source] = validator
            return validator
        return wrapper

    @classmethod
    def get_all(cls) -> List[CredentialData]:
        """Get all credentials.

        Returns:
            List[CredentialData]: The list of credentials.
        """
        return [
            CredentialData(**{
                **cred,
                'source': CredentialSource[cred["source"].upper()]
            })
            for cred in get_db().execute("""
                SELECT
                    id, source,
                    username, email,
                    password, api_key
                FROM credentials;
            """).fetchalldict()
        ]

    @classmethod
    def get_one(cls, credential_id: int) -> CredentialData:
        """Get a credential based on its ID.

        Args:
            id (int): The ID of the credential to get.

        Raises:
            CredentialNotFound: The ID doesn't map to any credential.

        Returns:
            CredentialData: The credential info.
        """
        result = get_db().execute("""
            SELECT
                id, source,
                username, email,
                password, api_key
            FROM credentials
            WHERE id = ?
            LIMIT 1;
            """,
            (credential_id,)
        ).fetchonedict()

        if result is None:
            raise CredentialNotFound(credential_id)

        return CredentialData(**{
            **result,
            'source': CredentialSource(result["source"])
        })

    @classmethod
    def get_from_source(cls, source: CredentialSource) -> List[CredentialData]:
        """Get credentials for the given source.

        Args:
            source (CredentialSource): The source of the credentials.

        Returns:
            List[CredentialData]: The credentials for the given source.
        """
        return [
            c
            for c in cls.get_all()
            if c.source == source
        ]

    @classmethod
    def add(cls, credential_data: CredentialData) -> CredentialData:
        """Add a credential.

        Args:
            credential_data (CredentialData): The data of the credential to
                store.

        Raises:
            ClientNotWorking: Can't connect to service.
            CredentialInvalid: The credential data is invalid.

        Returns:
            CredentialData: The credential info.
        """
        LOGGER.info(f'Adding credential for {credential_data.source.value}')

        source = credential_data.source
        credential_data = cls.validators[source](credential_data)

        credential_id = get_db().execute("""
            INSERT INTO credentials(source, username, email, password, api_key)
            VALUES (:source, :username, :email, :password, :api_key);
            """,
            credential_data.todict()
        ).lastrowid

        return cls.get_one(credential_id)

    @classmethod
    def delete(cls, cred_id: int) -> None:
        """Delete a credential.

        Args:
            cred_id (int): The ID of the credential to delete.

        Raises:
            CredentialNotFound: The ID doesn't map to any credential.
        """
        LOGGER.info(f'Deleting credential: {cred_id}')

        source = cls.get_one(cred_id).source

        get_db().execute(
            "DELETE FROM credentials WHERE id = ?", (cred_id,)
        )

        if source in cls.auth_tokens:
            del cls.auth_tokens[source]

        return
