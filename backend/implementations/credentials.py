# -*- coding: utf-8 -*-

from typing import Any, Dict, List, Tuple

from typing_extensions import assert_never

from backend.base.custom_exceptions import (ClientNotWorking,
                                            CredentialInvalid,
                                            CredentialNotFound)
from backend.base.definitions import CredentialData, CredentialSource
from backend.base.logging import LOGGER
from backend.internals.db import get_db


class Credentials:
    auth_tokens: Dict[CredentialSource, Dict[str, Tuple[Any, int]]] = {}
    """
    Store auth tokens as to avoid logging in while already having a cleared
    token. Maps from credential source to user identifier (something like user
    ID, email or username) to a tuple of the token and it's expiration time.
    """

    def get_all(self) -> List[CredentialData]:
        """Get all credentials.

        Returns:
            List[CredentialData]: The list of credentials.
        """
        return [
            CredentialData(**{
                **dict(c),
                'source': CredentialSource[c["source"].upper()]
            })
            for c in get_db().execute("""
                SELECT
                    id, source,
                    username, email,
                    password, api_key
                FROM credentials;
            """).fetchall()
        ]

    def get_one(self, id: int) -> CredentialData:
        """Get a credential based on it's id.

        Args:
            id (int): The ID of the credential to get.

        Raises:
            CredentialNotFound: The ID doesn't map to any credential.

        Returns:
            CredentialData: The credential info
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
            (id,)
        ).fetchone()

        if result is None:
            raise CredentialNotFound

        return CredentialData(**{
            **dict(result),
            'source': CredentialSource(result["source"])
        })

    def get_from_source(
        self,
        source: CredentialSource
    ) -> List[CredentialData]:
        """Get credentials for the given source.

        Args:
            source (CredentialSource): The source of the credentials.

        Returns:
            List[CredentialData]: The credentials for the given source.
        """
        return [
            c
            for c in self.get_all()
            if c.source == source
        ]

    def add(self, credential_data: CredentialData) -> CredentialData:
        """Add a credential.

        Args:
            credential_data (CredentialData): The data of the credential to
            store.

        Returns:
            dict: The credential info
        """
        LOGGER.info(f'Adding credential for {credential_data.source.value}')

        # Check if it works
        if credential_data.source == CredentialSource.MEGA:
            from backend.implementations.direct_clients.mega import (
                MegaAccount, MegaAPIClient)

            try:
                MegaAccount(
                    MegaAPIClient(),
                    credential_data.email or '',
                    credential_data.password or ''
                )

            except ClientNotWorking as e:
                raise CredentialInvalid(e.desc)

            credential_data.api_key = None
            credential_data.username = None

        elif credential_data.source == CredentialSource.PIXELDRAIN:
            from backend.implementations.download_clients import \
                PixelDrainDownload

            try:
                result = PixelDrainDownload.login(
                    credential_data.api_key or ''
                )
                if result == -1:
                    raise ClientNotWorking("Failed to login into Pixeldrain")

            except ClientNotWorking as e:
                raise CredentialInvalid(e.desc)

            credential_data.email = None
            credential_data.username = None
            credential_data.password = None

        else:
            assert_never(credential_data.source)

        id = get_db().execute("""
            INSERT INTO credentials(source, username, email, password, api_key)
            VALUES (:source, :username, :email, :password, :api_key);
            """,
            credential_data.as_dict()
        ).lastrowid

        return self.get_one(id)

    def delete(self, cred_id: int) -> None:
        """Delete a credential.

        Args:
            cred_id (int): The ID of the credential to delete.

        Raises:
            CredentialNotFound: The ID doesn't map to any credential.
        """
        LOGGER.info(f'Deleting credential: {cred_id}')

        source = self.get_one(cred_id).source

        get_db().execute(
            "DELETE FROM credentials WHERE id = ?", (cred_id,)
        )

        if source in self.auth_tokens:
            del self.auth_tokens[source]

        return
