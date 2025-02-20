#!/usr/bin/env python3
from threading import Event
from queue import Queue
from pytesira.util.ttp_response import TTPResponse
from pytesira.block.base_level_mute import BaseLevelMute
import logging

class LevelControl(BaseLevelMute):

    # Define version of this block's code here. A mismatch between this
    # and the value saved in the cached attribute-list value file will
    # trigger a re-discovery of attributes, to handle any changes
    VERSION = "0.1.0"

    # =================================================================================================================

    def __init__(self,
        block_id: str,                  # block ID on Tesira
        exit_flag: Event,               # exit flag to stop the block's threads (sync'd with everything else)                    
        connected_flag: Event,          # connected flag (module can refuse to allow access if this is not set)
        command_queue: Queue,           # command queue (to run synchronous commands and get results)
        subscriptions: dict,            # subscription container on main thread
        init_helper: str|None = None,   # initialization helper (if not specified, query everything from scratch)
    ) -> None:

        # Setup logger
        self._logger = logging.getLogger(f"{__name__}.{block_id}")

        # Initialize base class
        super().__init__(block_id, exit_flag, connected_flag, command_queue, subscriptions, init_helper)

        # If init helper isn't set, this is the time to query
        try:
            assert init_helper is not None, "no helper present"
            self.__load_init_helper(init_helper)
        except Exception as e:
            # There's a problem, throw warning and then simply query
            self._logger.debug(f"cannot use initialization helper: {e}")
            self.__query_attributes()

        # Base subscriptions are already handled by the BaseLevelMute class
        # but if we have anything extra, they can be initialized here

        # Extend initialization helper to include block-specific
        # attributes we want to also save
        self._init_helper["ganged"] = self.ganged

    # =================================================================================================================

    def __load_init_helper(self, init_helper : dict) -> None:
        """
        Use initialization helper to set up attributes instead of querying
        """
        self.ganged = init_helper["ganged"]

    # =================================================================================================================

    def subscription_callback(self, response : TTPResponse) -> None:
        """
        Handle incoming subscription callbacks
        """

        # Add any specific subscription callbacks here
        # in this case, there's none

        # Process base subscription callbacks too!
        super().subscription_callback(response)

    # =================================================================================================================

    def __query_attributes(self) -> None:

        # Ganged setup?
        self.ganged = bool(self._sync_command(f"{self._block_id} get ganged").value)