#!/usr/bin/env python3
from collections.abc import Callable
from pytesira.util.indexed_object_with_level import IndexedObjectWithLevel


class Channel(IndexedObjectWithLevel):
    """
    Channel object for a block ID
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

        # Based on the schema dict provided, we can initialize our extra attributes
        self.__muted = bool(schema["muted"]) if "muted" in schema else None
        self.__inverted = bool(schema["inverted"]) if "inverted" in schema else None
        self.__fault_on_inactive = (
            bool(schema["fault_on_inactive"]) if "fault_on_inactive" in schema else None
        )

    # =================================================================================================================

    def __repr__(self) -> str:
        return f"Channel: {self.schema}"

    @property
    def schema(self) -> dict:
        """
        Export schema to dict (allows re-initialization of object if needed)
        """
        # Get base schema
        schema = super().schema

        # Then we extend the schema to include our values
        schema["muted"] = self.__muted
        schema["inverted"] = self.__inverted
        schema["fault_on_inactive"] = self.__fault_on_inactive

        # Clean out anything that's a None, as that means we don't have
        # that attribute (or don't support it)
        schema = {k: v for k, v in schema.items() if v is not None}

        return schema

    # =================================================================================================================
    # Values that are INTENDED to be changed by API consumers
    # =================================================================================================================

    @property
    def muted(self) -> bool:
        if self.__muted is None:
            raise AttributeError
        return self.__muted

    @muted.setter
    def muted(self, value: bool) -> None:
        assert type(value) is bool, "invalid muted type"
        assert self.__muted is not None, "unsupported attribute muted"
        self._callback("muted", self.index, value)

    def _muted(self, value: bool) -> None:
        """
        Hidden updater so that the parent class can update our value
        without triggering circular callbacks
        """
        self.__muted = bool(value)

    # =================================================================================================================

    @property
    def inverted(self) -> bool:
        if self.__inverted is None:
            raise AttributeError
        return self.__inverted

    @inverted.setter
    def inverted(self, value: bool) -> None:
        assert type(value) is bool, "invalid inverted type"
        assert self.__inverted is not None, "unsupported attribute inverted"
        self._callback("inverted", self.index, value)

    def _inverted(self, value: bool) -> None:
        """
        Hidden updater so that the parent class can update our value
        without triggering circular callbacks
        """
        self.__inverted = bool(value)

    # =================================================================================================================

    @property
    def fault_on_inactive(self) -> bool:
        if self.__fault_on_inactive is None:
            raise AttributeError
        return self.__fault_on_inactive

    @fault_on_inactive.setter
    def fault_on_inactive(self, value: bool) -> None:
        assert type(value) is bool, "invalid fault_on_inactive type"
        assert (
            self.__fault_on_inactive is not None
        ), "unsupported attribute fault_on_inactive"
        self._callback("fault_on_inactive", self.index, value)

    def _fault_on_inactive(self, value: bool) -> None:
        """
        Hidden updater so that the parent class can update our value
        without triggering circular callbacks
        """
        self.__fault_on_inactive = bool(value)
