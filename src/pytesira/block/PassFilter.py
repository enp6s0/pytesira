#!/usr/bin/env python3
from threading import Event
from pytesira.block.block import Block
from queue import Queue
from pytesira.util.ttp_response import TTPResponse, TTPResponseType
import time
import logging

class PassFilter(Block):
    """
    Pass filter DSP block
    """

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
            self.__query_base_attributes()

        # Query status on start, too
        self.__query_status_attributes()

        # Initialization helper base
        self._init_helper = {
            "max_slope" : self.max_slope,
            "filter_type" : self.filter_type,
            "slope" : self.slope
        }

    # =================================================================================================================

    def __load_init_helper(self, init_helper : dict) -> None:
        """
        Use initialization helper to set up attributes instead of querying
        """
        self.max_slope = init_helper["max_slope"]
        self.filter_type = init_helper["filter_type"]
        self.slope = init_helper["slope"]

    # =================================================================================================================

    def __query_base_attributes(self) -> None:
        """
        Query base attributes - that is, things we don't expect to be changed
        and should save into the initialization helper to make next time loading
        at least a bit faster
        """
        # Max slope
        self.max_slope = self._sync_command(f"{self._block_id} get maxSlope").value

        # Filter type and slope can be queried in one
        fts = self._sync_command(f"{self._block_id} get filterTypeSlope").value
        self.filter_type = fts["type"]
        self.slope = fts["slope"]

    def __query_status_attributes(self) -> None:
        """
        Query status attributes - e.g., those that we expect to be changed (or tweaked) at runtime
        """
        self.__bypass = self._sync_command(f"{self._block_id} get bypass").value
        self.__cutoff_frequency = self._sync_command(f"{self._block_id} get frequency").value

    # =================================================================================================================

    def refresh_status(self) -> None:
        """
        Manually refresh/poll block status again

        For now, the compromise for these blocks is we accept the possibility that their attributes
        may be out of date, and let the end-user manually call a refresh when needed

        TODO: might want to give them an option to set a refresh timer for these blocks?
        """
        self.__query_status_attributes()

    # =================================================================================================================

    @property
    def bypass(self) -> bool:
        return self.__bypass
    @bypass.setter
    def bypass(self, value : bool) -> None:
        self.__bypass, _ = self._set_and_update_val("bypass", value = value)

    @property
    def cutoff_frequency(self) -> float:
        return self.__cutoff_frequency
    @cutoff_frequency.setter
    def cutoff_frequency(self, value : float) -> None:
        self.__cutoff_frequency, _ = self._set_and_update_val("frequency", value = value)
