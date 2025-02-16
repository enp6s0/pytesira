#!/usr/bin/env python3
from threading import Event
from pytesira.block.block import Block
from queue import Queue
from pytesira.util.ttp_response import TTPResponse, TTPResponseType
import time
import logging

class BaseLevelMuteNoSubscription(Block):

    """
    Base class for blocks supporting per-channel level and mute settings
    that DOES NOT support subscriptions (e.g., AudioOutput)

    Not instantiated directly by the main code
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

        # Note: logger should be set up first by any block that is built on top of this
        # otherwise, we raise an exception
        assert hasattr(self, "_logger"), "logger should be set up first!"

        # How do we query channel names (might be different - this can be set by subclasses
        # but if not, we use default)
        if not hasattr(self, "_chan_label_key"):
            self._chan_label_key = "label"

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

        # Query status attributes as well
        self._query_status_attributes()

        # Initialization helper base
        # (this will be used by export_init_helper() in the superclass to save initialization maps)
        # (additional attributes may then be set by the subclass extending BaseLevelMute)
        self._init_helper = {
            "channels" : self.channels
        }
        
    # =================================================================================================================

    def __load_init_helper(self, init_helper : dict) -> None:
        """
        Use initialization helper to set up attributes instead of querying
        """
        self.channels = {}
        for i, d in init_helper["channels"].items():
            self.channels[str(i)] = d

    # =================================================================================================================

    def _query_status_attributes(self) -> None:
        """
        Query status attributes - e.g., those that we expect to be changed (or tweaked) at runtime
        """
        for i in self.channels.keys():
            self.channels[str(i)]["muted"] = self._sync_command(f"{self._block_id} get mute {i}").value
            self.channels[str(i)]["level"]["current"] = self._sync_command(f"{self._block_id} get level {i}").value

    def refresh_status(self) -> None:
        """
        Manually refresh/poll block status again

        For now, the compromise for these blocks is we accept the possibility that their attributes
        may be out of date, and let the end-user manually call a refresh when needed

        TODO: might want to give them an option to set a refresh timer for these blocks?
        """
        self._query_status_attributes()

    # =================================================================================================================

    def __query_base_attributes(self) -> None:
        """
        Query base attributes - e.g., those that aren't expected to change at runtime
        """

        # How many channels?
        num_channels = int(self._sync_command(f"{self._block_id} get numChannels").value)
        self.channels = {}

        # For each channel, what's the index and labels?
        # NOTE: Tesira indices starts at 1, in some cases 0 is a special ID meaning all channels
        for i in range(1, num_channels + 1):

            # Query label
            if self._chan_label_key == "@":
                # Special value, this means we don't query but create one
                # (since blocks such as AudioOutput doesn't have label support)
                channel_label = f"{self._block_id}_{i}"
            else:
                label_query = self._sync_command(f"{self._block_id} get {self._chan_label_key} {i}")
                if label_query.type == TTPResponseType.CMD_ERROR:
                    channel_label = ""
                else:
                    channel_label = str(label_query.value).strip()

            # TODO: min/max levels can be changed (not supported yet but it could be), need to figure 
            # out how to make it play nice with block map caching. Potentially will need a callback 
            # so main thread can update block maps again with the new helper if we notice something
            # has changed, hmm...
            self.channels[str(i)] = {
                "index" : i,
                "label" : channel_label,
                "level" : {
                    "min" : self._sync_command(f"{self._block_id} get minLevel {i}").value,
                    "max" : self._sync_command(f"{self._block_id} get maxLevel {i}").value,
                },
            }

    # =================================================================================================================

    def set_mute(self, value : bool, channel : int = 0) -> TTPResponse:
        """
        Set mute status (and update local)
        """
        self.channels[str(channel)]["muted"], cmd_res = self._set_and_update_val("mute", value = value, channel = channel)
        return cmd_res

    def set_level(self, value : float, channel : int = 0) -> TTPResponse:
        """
        Set current level for a channel
        """
        self.channels[str(channel)]["level"]["current"], cmd_res = self._set_and_update_val("level", value = value, channel = channel)
        return cmd_res

    # =================================================================================================================