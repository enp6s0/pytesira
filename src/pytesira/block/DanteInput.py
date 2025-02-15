#!/usr/bin/env python3
from threading import Event
from queue import Queue
from pytesira.util.ttp_response import TTPResponse, TTPResponseType
from pytesira.block.base_level_mute import BaseLevelMute
import time
import logging

class DanteInput(BaseLevelMute):
    """
    Dante input DSP block
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

        # In Dante blocks, there's no label for each channel, but there's channelName instead
        self._chan_label_key = "channelName"

        # Initialize base class
        super().__init__(block_id, exit_flag, connected_flag, command_queue, subscriptions, init_helper)

        # If init helper isn't set, this is the time to query
        try:
            assert init_helper is not None, "no helper present"
            self.__load_init_helper(init_helper)
        except Exception as e:
            # There's a problem, throw warning and then simply query
            self._logger.warning(f"cannot use initialization helper: {e}")
            self.__query_attributes()

        # Base subscriptions are already handled by the BaseLevelMute class
        # so here we only initialize faultOnInactive subscribers
        for index in self.channels.keys():
            self._register_subscription(subscribe_type = "faultOnInactive", channel = index)

    # =================================================================================================================

    def __load_init_helper(self, init_helper : dict) -> None:
        """
        Use initialization helper to set up attributes instead of querying

        Note: we don't have to call super() here, since super().__init__ has already taken care of doing so for us
        """
        pass

    # =================================================================================================================

    def subscription_callback(self, response : TTPResponse) -> None:
        """
        Handle incoming subscription callbacks
        """

        # Fault-on-inactive status update callback
        if response.subscription_type == "faultOnInactive":
            if str(response.subscription_channel_id) in self.channels.keys():
                self.channels[str(response.subscription_channel_id)]["fault_on_inactive"] = bool(response.value)

        # Process base subscription callbacks too!
        super().subscription_callback(response)

    # =================================================================================================================

    def __query_attributes(self) -> None:
        """
        Query block-specific attributes that we're going to keep around
        """
        pass

    # =================================================================================================================

    def set_invert(self, value : bool, channel : int = 0) -> TTPResponse:
        """
        Set invert on a channel
        """
        assert type(value) == bool, "invalid value type for set_invert"
        return self._sync_command(f'"{self._block_id}" set invert {channel} {str(value).lower()}')

    def set_fault_on_inactive(self, value : bool, channel : int = 0) -> TTPResponse:
        """
        Set fault-on-inactive property of a channel
        """
        assert type(value) == bool, "invalid value type for set_fault_on_inactive"
        return self._sync_command(f'"{self._block_id}" set faultOnInactive {channel} {str(value).lower()}')

    # =================================================================================================================
