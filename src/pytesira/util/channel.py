#!/usr/bin/env python3
from collections.abc import Callable

class Channel:
    """
    Channel object for a block ID
    """

    def __init__(self, block_id : str, index : int, callback : Callable, schema : dict = {}) -> None:
        """
        Initialize a channel object
        """

        # Which block do we belong to, and what index?
        self.__block_id = str(block_id)
        self.__index = int(index)
        assert 1 <= self.__index, "invalid block index"

        # Callback for when a value is updated, such that the parent block can actually
        # handle updating this
        self.__callback = callback
        assert callable(callback), "callback for level not callable"

        # Callbacks should accept the parameters: type, channel index, new value
        # which will be called if the value is updated programatically

        # Based on the schema dict provided, we can initialize our attributes
        self.__label = str(schema["label"]).strip() if "label" in schema else None
        self.__muted = bool(schema["muted"]) if "muted" in schema else None
        self.__inverted = bool(schema["inverted"]) if "inverted" in schema else None
        self.__fault_on_inactive = bool(schema["fault_on_inactive"]) if "fault_on_inactive" in schema else None

        # Current, maximum, and minimum levels
        # (these are modifiable and we handle custom setters accordingly)
        self.__level = float(schema["level"]) if "level" in schema else None
        self.__min_level = float(schema["min_level"]) if "min_level" in schema else None
        self.__max_level = float(schema["max_level"]) if "max_level" in schema else None

    # =================================================================================================================

    def __repr__(self) -> str:
        return f"Channel: {self.schema}"

    @property
    def schema(self) -> dict:
        """
        Export schema to dict (allows re-initialization of object if needed)
        """
        return {
            "index" : self.__index,
            "label" : self.__label,
            "muted" : self.__muted,
            "level" : self.__level,
            "inverted" : self.__inverted,
            "fault_on_inactive" : self.__fault_on_inactive,
            "min_level" : self.__min_level,
            "max_level" : self.__max_level,
        }

    # =================================================================================================================
    # Simple protected property getter, not intended for update by the API consumer
    # =================================================================================================================

    @property
    def index(self) -> int:
        return self.__index
    def _index(self, value : int) -> None:
        self.__index = int(value)

    @property
    def label(self) -> str:
        return self.__label
    def _label(self, value : str) -> None:
        self.__label = str(value)

    # =================================================================================================================
    # Values that are INTENDED to be changed by API consumers
    # =================================================================================================================

    @property
    def muted(self) -> bool:
        return self.__muted

    @muted.setter
    def muted(self, value : bool) -> None:
        assert type(value) == bool, "invalid muted type"
        assert self.__muted is not None, "unsupported attribute muted"
        self.__callback("muted", self.__index, value)

    def _muted(self, value : bool) -> None:
        """
        Hidden updater so that the parent class can update our value
        without triggering circular callbacks
        """
        self.__muted = bool(value)

    # =================================================================================================================

    @property
    def inverted(self) -> bool:
        return self.__inverted

    @inverted.setter
    def inverted(self, value : bool) -> None:
        assert type(value) == bool, "invalid inverted type"
        assert self.__inverted is not None, "unsupported attribute inverted"
        self.__callback("inverted", self.__index, value)

    def _inverted(self, value : bool) -> None:
        """
        Hidden updater so that the parent class can update our value
        without triggering circular callbacks
        """
        self.__inverted = bool(value)

    # =================================================================================================================

    @property
    def fault_on_inactive(self) -> bool:
        return self.__fault_on_inactive

    @fault_on_inactive.setter
    def fault_on_inactive(self, value : bool) -> None:
        assert type(value) == bool, "invalid fault_on_inactive type"
        assert self.__fault_on_inactive is not None, "unsupported attribute fault_on_inactive"
        self.__callback("fault_on_inactive", self.__index, value)

    def _fault_on_inactive(self, value : bool) -> None:
        """
        Hidden updater so that the parent class can update our value
        without triggering circular callbacks
        """
        self.__fault_on_inactive = bool(value)

    # =================================================================================================================

    @property
    def level(self) -> float:
        return self.__level

    @level.setter
    def level(self, value : float) -> None:
        assert type(value) == float, "invalid level type"
        assert self.__level is not None, "unsupported attribute level"
        self.__callback("level", self.__index, value)

    def _level(self, value : float) -> None:
        """
        Hidden updater so that the parent class can update our value
        without triggering circular callbacks
        """
        self.__level = value

    # =================================================================================================================

    @property
    def min_level(self) -> float:
        return self.__min_level

    @min_level.setter
    def min_level(self, value : float) -> None:
        assert type(value) == float, "invalid min_level type"
        assert self.__level is not None, "unsupported attribute min_level"
        self.__callback("min_level", self.__index, value)

    def _min_level(self, value : float) -> None:
        """
        Hidden updater so that the parent class can update our value
        without triggering circular callbacks
        """
        self.__min_level = value

    # =================================================================================================================

    @property
    def max_level(self) -> float:
        return self.__max_level

    @max_level.setter
    def max_level(self, value : float) -> None:
        assert type(value) == float, "invalid level type"
        assert self.__level is not None, "unsupported attribute max_level"
        self.__callback("max_level", self.__index, value)

    def _max_level(self, value : float) -> None:
        """
        Hidden updater so that the parent class can update our value
        without triggering circular callbacks
        """
        self.__max_level = value