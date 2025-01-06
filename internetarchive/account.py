import json
from typing import ClassVar, Dict, List, Optional

import requests

from internetarchive import get_session
from internetarchive.exceptions import AccountAPIError


class Account:
    API_BASE_URL: str = '/services/xauthn/'
    API_INFO_PARAMS: ClassVar[Dict[str, str]] = {'op': 'info'}
    API_LOCK_UNLOCK_PARAMS: ClassVar[Dict[str, str]] = {'op': 'lock_unlock'}

    def __init__(
        self,
        locked: bool,
        verified: bool,
        email: str,
        canonical_email: str,
        itemname: str,
        screenname: str,
        notifications: List[str],
        has_disability_access: bool,
        session: Optional[requests.Session] = None
    ):
        self.locked = locked
        self.verified = verified
        self.email = email
        self.canonical_email = canonical_email
        self.itemname = itemname
        self.screenname = screenname
        self.notifications = notifications
        self.has_disability_access = has_disability_access
        self.session = session or get_session()

    def _get_api_base_url(self) -> str:
        """Dynamically construct the API base URL using the session's host."""
        return f'https://{self.session.host}{self.API_BASE_URL}'  # type: ignore[attr-defined]

    def _make_api_request(
        self,
        endpoint: str,
        params: Dict[str, str],
        data: Dict[str, str],
        session: Optional[requests.Session] = None
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
    def from_email(cls,
                   email: str,
                   session: Optional[requests.Session] = None) -> "Account":
        """Factory method to initialize an Account using an email."""
        json_data = cls._fetch_account_data_from_api('email', email, session)
        return cls.from_json(json_data, session)

    @classmethod
    def from_screenname(cls,
                        screenname: str,
                        session: Optional[requests.Session] = None) -> "Account":
        """Factory method to initialize an Account using a screenname."""
        json_data = cls._fetch_account_data_from_api('screenname', screenname, session)
        return cls.from_json(json_data, session)

    @classmethod
    def from_itemname(cls,
                      itemname: str,
                      session: Optional[requests.Session] = None) -> "Account":
        """Factory method to initialize an Account using an itemname."""
        json_data = cls._fetch_account_data_from_api('itemname', itemname, session)
        return cls.from_json(json_data, session)

    @classmethod
    def _fetch_account_data_from_api(
        cls,
        identifier_type: str,
        identifier: str,
        session: Optional[requests.Session] = None
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
            raise ValueError(f"Failed to fetch account data: {e}")

    @classmethod
    def from_json(
        cls,
        json_data: Dict,
        session: Optional[requests.Session] = None
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
            "verified"
        ]
        for field in required_fields:
            if field not in json_data:
                raise ValueError(f"Missing required field in JSON data: {field}")

        return cls(
            locked=json_data["locked"],
            verified=json_data["verified"],
            email=json_data["email"],
            canonical_email=json_data["canonical_email"],
            itemname=json_data["itemname"],
            screenname=json_data["screenname"],
            notifications=json_data["notifications"],
            has_disability_access=json_data["has_disability_access"],
            session=session
        )

    def lock(self,
             comment: Optional[str] = None,
             session: Optional[requests.Session] = None) -> requests.Response:
        """
        Lock the account.

        Args:
            comment: An optional comment for the lock operation.
            session: Optional session to use for the request.

        Returns:
            The response from the API.
        """
        data = {'itemname': self.itemname, 'is_lock': "1"}
        if comment:
            data['comments'] = comment
        return self._make_api_request(
            self.API_BASE_URL,
            params=self.API_LOCK_UNLOCK_PARAMS,
            data=data,
            session=session
        )

    def unlock(self,
               comment: Optional[str] = None,
               session: Optional[requests.Session] = None) -> requests.Response:
        """
        Unlock the account.

        Args:
            comment: An optional comment for the unlock operation.
            session: Optional session to use for the request.

        Returns:
            The response from the API.
        """
        data = {'itemname': self.itemname, 'is_lock': "0"}
        if comment:
            data['comments'] = comment
        return self._make_api_request(
            self.API_BASE_URL,
            params=self.API_LOCK_UNLOCK_PARAMS,
            data=data,
            session=session
        )

    def __iter__(self):
        """
        Allows the Account instance to be converted to a dictionary using dict(Account).

        Returns:
            A dictionary representation of the Account instance.
        """
        return iter({
            "locked": self.locked,
            "verified": self.verified,
            "email": self.email,
            "canonical_email": self.canonical_email,
            "itemname": self.itemname,
            "screenname": self.screenname,
            "notifications": self.notifications,
            "has_disability_access": self.has_disability_access,
        }.items())

    def __repr__(self) -> str:
        return (
            f"Account(locked={self.locked}, verified={self.verified}, "
            f"email={self.email}, canonical_email={self.canonical_email}, "
            f"itemname={self.itemname}, screenname={self.screenname}, "
            f"notifications={self.notifications}, "
            f"has_disability_access={self.has_disability_access})"
        )
