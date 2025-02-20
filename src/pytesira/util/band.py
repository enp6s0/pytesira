#!/usr/bin/env python3
from collections.abc import Callable
from pytesira.util.indexed_object_with_level import IndexedObjectWithLevel

class Band(IndexedObjectWithLevel):
    """
    Band object for EQs

    Note that to keep the code simple, level = gain (so we can directly
    extend IndexedObjectWithLevel and not have to maintain repetitive code here)
    """

    def __init__(self, block_id : str, index : int, callback : Callable, schema : dict = {}) -> None:
        # Call superclass init. This also handles setting up self._callback for us,
        # which we can directly call from here if needed.
        #
        # Callbacks should accept the parameters: type, channel index, new value
        # which will be called if the value is updated programatically
        super().__init__(block_id, index, callback, schema)

        # Based on the schema dict provided, we can initialize our extra attributes
        self.__bypass = bool(schema["bypass"]) if "bypass" in schema else None

    # =================================================================================================================

    def __repr__(self) -> str:
        return f"Band: {self.schema}"

    @property
    def schema(self) -> dict:
        """
        Export schema to dict (allows re-initialization of object if needed)
        """
        # Get base schema
        schema = super().schema

        # Then we extend the schema to include our values
        schema["bypass"] = self.__bypass

        # Clean out anything that's a None, as that means we don't have
        # that attribute (or don't support it)
        schema = {k: v for k, v in schema.items() if v is not None}

        return schema

    # =================================================================================================================
    # Values that are INTENDED to be changed by API consumers
    # =================================================================================================================

    @property
    def bypass(self) -> bool:
        if self.__bypass is None:
            raise AttributeError
        return self.__bypass

    @bypass.setter
    def bypass(self, value : bool) -> None:
        assert type(value) == bool, "invalid bypass type"
        assert self.__bypass is not None, "unsupported attribute bypass"
        self._callback("bypass", self.index, value)

    def _bypass(self, value : bool) -> None:
        """
        Hidden updater so that the parent class can update our value
        without triggering circular callbacks
        """
        self.__bypass = bool(value)

    # =================================================================================================================
