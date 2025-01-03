from typing import ClassVar, Dict, List, Optional

import requests

from internetarchive import get_session
from internetarchive.exceptions import AccountAPIError


class Account:
    # Class-level constants for API configuration
    API_URL = 'https://archive.org/services/xauthn/'
    API_PARAMS: ClassVar[dict] = {'op': 'info'}

    def __init__(
        self,
        locked: bool,
        verified: bool,
        email: str,
        canonical_email: str,
        itemname: str,
        screenname: str,
        notifications: List[str],
        has_disability_access: bool
    ):
        self.locked = locked
        self.verified = verified
        self.email = email
        self.canonical_email = canonical_email
        self.itemname = itemname
        self.screenname = screenname
        self.notifications = notifications
        self.has_disability_access = has_disability_access

    @classmethod
    def from_email(cls, email: str) -> "Account":
        """Factory method to initialize an Account using an email."""
        json_data = cls._fetch_account_data_from_api('email', email)
        return cls.from_json(json_data)

    @classmethod
    def from_screenname(cls, screenname: str) -> "Account":
        """Factory method to initialize an Account using a screenname."""
        json_data = cls._fetch_account_data_from_api('screenname', screenname)
        return cls.from_json(json_data)

    @classmethod
    def from_itemname(cls, itemname: str) -> "Account":
        """Factory method to initialize an Account using an itemname."""
        json_data = cls._fetch_account_data_from_api('itemname', itemname)
        return cls.from_json(json_data)

    @staticmethod
    def _fetch_account_data_from_api(identifier_type: str, identifier: str) -> Dict:
        """
        Fetches account data from the API using an identifier type and value.

        Args:
            identifier_type: The type of identifier (e.g., 'email', 'screenname').
            identifier: The value of the identifier (e.g., 'foo@example.com').

        Returns:
            A dictionary containing the account data.

        Raises:
            requests.exceptions.RequestException: If the API request fails.
            ValueError: If the API response is invalid or missing required data.
        """
        data = {identifier_type: identifier}
        session = get_session()
        try:
            response = session.post(Account.API_URL, params=Account.API_PARAMS, data=data)
            response.raise_for_status()
            j = response.json()
            if j.get("error") or not j.get("values"):
                raise AccountAPIError(j.get("error", "Unknown error"),
                                      error_data=j)
            return response.json()["values"]
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Failed to fetch account data: {e}")

    @classmethod
    def from_json(cls, json_data: Dict) -> "Account":
        """
        Factory method to initialize an Account using JSON data.

        Args:
            json_data: A dictionary containing account data.

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
        )

    def __iter__(self):
        """
        Allows the Account instance to be converted to a dictionary using dict(Account).

        Returns:
            A dictionary representation of the Account instance.
        """
        # Return a dictionary of all attributes, including the stored JSON data
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
