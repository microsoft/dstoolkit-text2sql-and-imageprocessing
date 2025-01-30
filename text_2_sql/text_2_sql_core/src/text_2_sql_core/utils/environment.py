# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import os
from enum import Enum


class IdentityType(Enum):
    """The type of the indexer"""

    USER_ASSIGNED = "user_assigned"
    SYSTEM_ASSIGNED = "system_assigned"
    KEY = "key"


def get_identity_type() -> IdentityType:
    """This function returns the identity type.

    Returns:
        IdentityType: The identity type
    """
    identity = os.environ["IdentityType"]

    if identity == "user_assigned":
        return IdentityType.USER_ASSIGNED
    elif identity == "system_assigned":
        return IdentityType.SYSTEM_ASSIGNED
    elif identity == "key":
        return IdentityType.KEY
    else:
        raise ValueError("Invalid identity type")
