#!/usr/bin/env python3
# Consolidated import for PyTesira enum types
from enum import Enum


class TTPResponseType(Enum):
    """
    TTP response types
    """

    UNKNOWN = 0  # Unknown / default, should never really occur
    CMD_OK = 1  # OK response with no value (e.g., command acknowledgements)
    CMD_OK_VALUE = 2  # OK response with attached value
    CMD_ERROR = 3  # Error response
    SUBSCRIPTION = 5  # Subscription response
