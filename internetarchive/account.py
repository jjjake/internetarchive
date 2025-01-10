import json
from dataclasses import dataclass, field
from typing import ClassVar, Dict, List, Optional

import requests

from internetarchive import get_session
from internetarchive.exceptions import AccountAPIError
from internetarchive.session import ArchiveSession

"""
internetarchive.account
~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (C) 2012-2025 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.

This module provides the `Account` class for interacting with user accounts on the
Internet Archive. It requires administrative privileges.
"""


@dataclass
class Account:
    """
    A class for interacting with user accounts on the Internet Archive.

    Note:
        This class requires administrative privileges.

    This class provides methods to:
    - Fetch account details using various identifiers (e.g., email, screenname, itemname).
    - Lock and unlock accounts.
    - Convert account data to a dictionary for serialization.

    Example Usage:
        >>> from internetarchive.account import Account
        >>> account = Account.from_account_lookup('email', 'foo@example.com')
        >>> account.lock(comment="Locked spam account")
        >>> print(account.to_dict())
    """
    locked: bool
    verified: bool
    email: str
    canonical_email: str
    itemname: str
    screenname: str
    notifications: List[str]
    has_disability_access: bool
    lastlogin: str
    createdate: str
    session: ArchiveSession = field(default_factory=get_session)

    API_BASE_URL: str = '/services/xauthn/'
    API_INFO_PARAMS: ClassVar[Dict[str, str]] = {'op': 'info'}
    API_LOCK_UNLOCK_PARAMS: ClassVar[Dict[str, str]] = {'op': 'lock_unlock'}

    def _get_api_base_url(self) -> str:
        """Dynamically construct the API base URL using the session's host."""
        return f'https://{self.session.host}{self.API_BASE_URL}'  # type: ignore[attr-defined]

    def _post_api_request(
        self,
        endpoint: str,
        params: Dict[str, str],
        data: Dict[str, str],
        session: Optional[ArchiveSession] = None
    ) -> requests.Response:
        """
        Helper method to make API requests.

        Args:
            endpoint: The API endpoint to call.
            params: Query parameters for the request.
            data: Data to send in the request body.
            session: Optional session to use for the request. Defaults to self.session.

        Returns:
            The response from the API.

        Raises:
            requests.exceptions.RequestException: If the API request fails.
        """
        session = session or self.session
        url = f'https://{session.host}{endpoint}'  # type: ignore[attr-defined]
        response = session.post(url, params=params, data=data)
        response.raise_for_status()
        return response

    @classmethod
    def from_account_lookup(
        cls,
        identifier_type: str,
        identifier: str,
        session: Optional[ArchiveSession] = None
    ) -> "Account":
        """
        Factory method to initialize an Account using an identifier type and value.

        Args:
            identifier_type: The type of identifier (e.g., 'email', 'screenname').
            identifier: The value of the identifier (e.g., 'foo@example.com').
            session: Optional session to use for the request.

        Returns:
            An instance of Account.
        """
        json_data = cls._fetch_account_data_from_api(identifier_type, identifier, session)
        return cls.from_json(json_data, session)

    @classmethod
    def _fetch_account_data_from_api(
        cls,
        identifier_type: str,
        identifier: str,
        session: Optional[ArchiveSession] = None
    ) -> Dict:
        """
        Fetches account data from the API using an identifier type and value.

        Args:
            identifier_type: The type of identifier (e.g., 'email', 'screenname').
            identifier: The value of the identifier (e.g., 'foo@example.com').
            session: Optional session to use for the request.

        Returns:
            A dictionary containing the account data.

        Raises:
            requests.exceptions.RequestException: If the API request fails.
            ValueError: If the API response is invalid or missing required data.
        """
        data = {identifier_type: identifier}
        session = session or get_session()
        try:
            response = session.post(
                f'https://{session.host}{cls.API_BASE_URL}',  # type: ignore[attr-defined]
                params=cls.API_INFO_PARAMS,
                data=json.dumps(data)
            )
            response.raise_for_status()
            j = response.json()
            if j.get("error") or not j.get("values"):
                raise AccountAPIError(j.get("error", "Unknown error"), error_data=j)
            return j["values"]
        except requests.exceptions.RequestException as e:
            raise AccountAPIError(f"Failed to fetch account data: {e}")


    @classmethod
    def from_json(
        cls,
        json_data: Dict,
        session: Optional[ArchiveSession] = None
    ) -> "Account":
        """
        Factory method to initialize an Account using JSON data.

        Args:
            json_data: A dictionary containing account data.
            session: Optional session to use for the request.

        Returns:
            An instance of Account.

        Raises:
            ValueError: If required fields are missing in the JSON data.
        """
        required_fields = [
            "canonical_email",
            "email",
            "has_disability_access",
            "itemname",
            "locked",
            "notifications",
            "screenname",
            "verified",
            "lastlogin",
            "createdate",
        ]
        for requried_field in required_fields:
            if requried_field not in json_data:
                raise ValueError(f"Missing required requried_field in JSON data: {requried_field}")

        # Ensure session is of type ArchiveSession
        if session is None:
            session = get_session()  # Default to ArchiveSession
        elif not isinstance(session, ArchiveSession):
            raise TypeError(f"Expected session to be of type ArchiveSession, got {type(session)}")

        return cls(
            locked=json_data["locked"],
            verified=json_data["verified"],
            email=json_data["email"],
            canonical_email=json_data["canonical_email"],
            itemname=json_data["itemname"],
            screenname=json_data["screenname"],
            notifications=json_data["notifications"],
            has_disability_access=json_data["has_disability_access"],
            lastlogin=json_data["lastlogin"],
            createdate=json_data["createdate"],
            session=session
        )

    def lock(self,
             comment: Optional[str] = None,
             session: Optional[ArchiveSession] = None) -> requests.Response:
        """
        Lock the account.

        Args:
            comment: An optional comment for the lock operation.
            session: Optional session to use for the request.

        Returns:
            The response from the API.
        """
        data = {'itemname': self.itemname, 'is_lock': '1'}
        if comment:
            data['comments'] = comment
        return self._post_api_request(
            self.API_BASE_URL,
            params=self.API_LOCK_UNLOCK_PARAMS,
            data=data,
            session=session
        )

    def unlock(self,
               comment: Optional[str] = None,
               session: Optional[ArchiveSession] = None) -> requests.Response:
        """
        Unlock the account.

        Args:
            comment: An optional comment for the unlock operation.
            session: Optional session to use for the request.

        Returns:
            The response from the API.
        """
        data = {'itemname': self.itemname, 'is_lock': '0'}
        if comment:
            data['comments'] = comment
        return self._post_api_request(
            self.API_BASE_URL,
            params=self.API_LOCK_UNLOCK_PARAMS,
            data=data,
            session=session
        )

    def to_dict(self) -> Dict:
        """
        Converts the Account instance to a dictionary.

        Returns:
            A dictionary representation of the Account instance.
        """
        return {
            "locked": self.locked,
            "verified": self.verified,
            "email": self.email,
            "canonical_email": self.canonical_email,
            "itemname": self.itemname,
            "screenname": self.screenname,
            "notifications": self.notifications,
            "has_disability_access": self.has_disability_access,
            "lastlogin": self.lastlogin,
            "createdate": self.createdate,
        }
