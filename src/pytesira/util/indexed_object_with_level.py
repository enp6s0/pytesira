#!/usr/bin/env python3
from collections.abc import Callable
from pytesira.util.indexed_object import IndexedObject


class IndexedObjectWithLevel(IndexedObject):
    """
    Indexed object, with current, minimum, and maximum level extensions
    """

    def __init__(
        self, block_id: str, index: int, callback: Callable, schema: dict = {}
    ) -> None:
        """
        Initialize a channel object
        """

        # Call superclass init. This also handles setting up self._callback for us,
        # which we can directly call from here if needed.
        #
        # Callbacks should accept the parameters: type, channel index, new value
        # which will be called if the value is updated programatically
        super().__init__(block_id, index, callback, schema)

        # Current, maximum, and minimum levels
        # (these are modifiable and we handle custom setters accordingly)
        self.__level = float(schema["level"]) if "level" in schema else None
        self.__min_level = float(schema["min_level"]) if "min_level" in schema else None
        self.__max_level = float(schema["max_level"]) if "max_level" in schema else None

    # =================================================================================================================

    def __repr__(self) -> str:
        return f"IndexedObjectWithLevel: {self.schema}"

    @property
    def schema(self) -> dict:
        """
        Export schema to dict (allows re-initialization of object if needed)
        """
        # Get base schema
        schema = super().schema

        # Then we extend the schema to include our values
        schema["level"] = self.__level
        schema["min_level"] = self.__min_level
        schema["max_level"] = self.__max_level

        # Clean out anything that's a None, as that means we don't have
        # that attribute (or don't support it)
        schema = {k: v for k, v in schema.items() if v is not None}

        return schema

    # =================================================================================================================
    # Values that are INTENDED to be changed by API consumers
    # =================================================================================================================

    @property
    def level(self) -> float:
        if self.__level is None:
            raise AttributeError
        return self.__level

    @level.setter
    def level(self, value: float) -> None:
        assert type(value) == float, "invalid level type"
        assert self.__level is not None, "unsupported attribute level"
        self._callback("level", self.index, value)

    def _level(self, value: float) -> None:
        """
        Hidden updater so that the parent class can update our value
        without triggering circular callbacks
        """
        self.__level = value

    # =================================================================================================================

    @property
    def min_level(self) -> float:
        if self.__min_level is None:
            raise AttributeError
        return self.__min_level

    @min_level.setter
    def min_level(self, value: float) -> None:
        assert type(value) == float, "invalid min_level type"
        assert self.__level is not None, "unsupported attribute min_level"
        self._callback("min_level", self.index, value)

    def _min_level(self, value: float) -> None:
        """
        Hidden updater so that the parent class can update our value
        without triggering circular callbacks
        """
        self.__min_level = value

    # =================================================================================================================

    @property
    def max_level(self) -> float:
        if self.__max_level is None:
            raise AttributeError
        return self.__max_level

    @max_level.setter
    def max_level(self, value: float) -> None:
        assert type(value) == float, "invalid level type"
        assert self.__level is not None, "unsupported attribute max_level"
        self._callback("max_level", self.index, value)

    def _max_level(self, value: float) -> None:
        """
        Hidden updater so that the parent class can update our value
        without triggering circular callbacks
        """
        self.__max_level = value
