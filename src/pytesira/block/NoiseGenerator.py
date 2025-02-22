#!/usr/bin/env python3
from threading import Event
from queue import Queue
from pytesira.block.base_level_mute_no_subscription import BaseLevelMuteNoSubscription
import logging


class NoiseGenerator(BaseLevelMuteNoSubscription):
    """
    Noise generator block
    """

    # Define version of this block's code here. A mismatch between this
    # and the value saved in the cached attribute-list value file will
    # trigger a re-discovery of attributes, to handle any changes
    VERSION = "0.1.0"

    def __init__(
        self,
        block_id: str,  # block ID on Tesira
        exit_flag: Event,  # exit flag to stop the block's threads (sync'd with everything else)
        connected_flag: Event,  # connected flag (module can refuse to allow access if this is not set)
        command_queue: Queue,  # command queue (to run synchronous commands and get results)
        subscriptions: dict,  # subscription container on main thread
        init_helper: (
            str | None
        ) = None,  # initialization helper (if not specified, query everything from scratch)
    ) -> None:

        # Block ID
        self._block_id = block_id

        # Setup logger
        self._logger = logging.getLogger(f"{__name__}.{block_id}")

        # No channel label key, use autogeneration
        self._chan_label_key = "@"

        # Initialize base class
        super().__init__(
            block_id,
            exit_flag,
            connected_flag,
            command_queue,
            subscriptions,
            init_helper,
        )

        # Query status attributes
        self._query_status_attributes()
