#!/usr/bin/env python3
from collections.abc import Callable


class IndexedObject:
    """
    Indexed object (belonging to a DSP block)
    Base class for things like channels, sources, etc.

    Only carries block ID, index,, change callback, and optional label on its own. Everything else
    is to be provided by classes that implements this
    """

    def __init__(
        self, block_id: str, index: int, callback: Callable, schema: dict = {}
    ) -> None:
        """
        Initialize the object
        """

        # Which block do we belong to, and what index?
        self.__block_id = str(block_id)
        self.__index = int(index)
        assert 1 <= self.__index, "invalid block index"

        # Callback for when a value is updated, such that the parent block can actually
        # handle updating this
        self._callback = callback
        assert callable(callback), "callback for level not callable"

        # Callbacks should accept the parameters: type, channel index, new value
        # which will be called if the value is updated programatically

        # Based on the schema dict provided, we can initialize our attributes
        # (only label is handled at this level though)
        self.__label = str(schema["label"]).strip() if "label" in schema else None

    # =================================================================================================================

    def __repr__(self) -> str:
        return f"IndexedObject: {self.schema}"

    @property
    def schema(self) -> dict:
        """
        Export schema to dict (allows re-initialization of object if needed)
        """
        schema = {
            "index": self.__index,
            "label": self.__label,
            "parent": self.__block_id,
        }

        # Clean out anything that's a None, as that means we don't have
        # that attribute (or don't support it)
        schema = {k: v for k, v in schema.items() if v is not None}

        return schema

    # =================================================================================================================
    # Simple protected property getter, not intended for update by the API consumer
    # =================================================================================================================

    @property
    def index(self) -> int:
        """
        Index, pretty much a read-only
        """
        if self.__index is None:
            raise AttributeError
        return self.__index

    @index.setter
    def index(self, value) -> None:
        raise AttributeError("index cannot be edited")

    @property
    def label(self) -> str:
        """
        Label, intended to be read-only, but can be changed
        if really needed
        """
        if self.__label is None:
            raise AttributeError
        return self.__label

    @label.setter
    def label(self, value) -> None:
        raise AttributeError("label cannot be edited")

    def _label(self, value: str) -> None:
        """
        We, however, provide this updater for the framework itself
        to update the value without triggering circular updates
        """
        self.__label = str(value)
