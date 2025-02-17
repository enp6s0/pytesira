#!/usr/bin/env python3
from threading import Event
from pytesira.block.block import Block
from queue import Queue
from pytesira.util.ttp_response import TTPResponse, TTPResponseType
from pytesira.util.channel import Channel
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

        # We don't query status attributes here and let subclasses decide whether
        # to just use ours, extend ours, or bypass ours...

        # Initialization helper base
        # (this will be used by export_init_helper() in the superclass to save initialization maps)
        # (additional attributes may then be set by the subclass extending BaseLevelMute)
        self._init_helper = {
            "channels" : {}
        }
        for idx, c in self.channels.items():
            self._init_helper["channels"][int(idx)] = c.schema
        
    # =================================================================================================================

    def _channel_change_callback(self, data_type : str, channel_index : int, new_value : bool|str|float|int) -> None:
        """
        Send out commands when we get a change on one of our channels
        """

        if data_type == "muted":
            new_val, cmd_res = self._set_and_update_val("mute", value = new_value, channel = channel_index)
            self.channels[channel_index]._muted(new_val)
            return cmd_res

        elif data_type == "level":
            new_val, cmd_res = self._set_and_update_val("level", value = new_value, channel = channel_index)
            self.channels[channel_index]._level(new_val)
            return cmd_res

        else:
            # Not supported (yet?)
            self._logger.warning(f"unhandled attribute change: {data_type}")

    # =================================================================================================================

    def __load_init_helper(self, init_helper : dict) -> None:
        """
        Use initialization helper to set up attributes instead of querying
        """
        self.channels = {}
        for i, d in init_helper["channels"].items():
            self.channels[int(i)] = Channel(self._block_id, int(i), self._channel_change_callback, d)

    # =================================================================================================================

    def _query_status_attributes(self) -> None:
        """
        Query status attributes - e.g., those that we expect to be changed (or tweaked) at runtime
        """
        for i in self.channels.keys():
            self.channels[i]._muted(self._sync_command(f"{self._block_id} get mute {i}").value)
            self.channels[i]._level(self._sync_command(f"{self._block_id} get level {i}").value)

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
            self.channels[int(i)] = Channel(self._block_id, int(i), self._channel_change_callback, {
                "label" : channel_label,
                "min_level" : self._sync_command(f"{self._block_id} get minLevel {i}").value,
                "max_level" : self._sync_command(f"{self._block_id} get maxLevel {i}").value
            })
