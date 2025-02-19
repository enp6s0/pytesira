#!/usr/bin/env python3
from collections.abc import Callable
from pytesira.util.indexed_object_with_level import IndexedObjectWithLevel

class Source(IndexedObjectWithLevel):
    """
    Channel object for source selector sources. This is basically IndexedObject with level,
    and nothing else, really...
    """

    def __repr__(self) -> str:
        return f"Source: {self.schema}"
