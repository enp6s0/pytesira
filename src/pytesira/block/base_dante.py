#!/usr/bin/env python3
from threading import Event
from queue import Queue
from pytesira.util.ttp_response import TTPResponse, TTPResponseType
from pytesira.block.base_level_mute import BaseLevelMute
import time
import logging

class BaseDante(BaseLevelMute):
    """
    Dante I/O dsp block
    """

    # Define version of this block's code here. A mismatch between this
    # and the value saved in the cached attribute-list value file will
    # trigger a re-discovery of attributes, to handle any changes
    VERSION = "0.2.0"

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

        # States that needs to be queried
        self._query_status_attributes()

        # Base subscriptions are already handled by the BaseLevelMute class
        # so here we only initialize faultOnInactive subscribers
        for index in self.channels.keys():
            self._register_subscription(subscribe_type = "faultOnInactive", channel = index)

    # =================================================================================================================

    def _channel_change_callback(self, data_type : str, channel_index : int, new_value : bool|str|float|int) -> TTPResponse:
        """
        Send out commands when we get a change on one of our channels
        """

        if data_type == "inverted":
            new_val, cmd_res = self._set_and_update_val("invert", value = new_value, channel = channel_index)
            if cmd_res.type != TTPResponseType.CMD_OK:
                raise ValueError(cmd_res.value)
            self.channels[channel_index]._inverted(new_val)
            return cmd_res

        elif data_type == "fault_on_inactive":
            new_val, cmd_res = self._set_and_update_val("faultOnInactive", value = str(new_value).lower(), channel = channel_index)
            if cmd_res.type != TTPResponseType.CMD_OK:
                raise ValueError(cmd_res.value)
            self.channels[channel_index]._fault_on_inactive(new_val)
            return cmd_res

        else:
            # We don't deal with this, so let our superclass handler handle it instead
            super()._channel_change_callback(data_type, channel_index, new_value)

    # =================================================================================================================

    def _query_status_attributes(self) -> None:
        """
        Query status attributes - e.g., those that we expect to be changed (or tweaked) at runtime
        """

        # Invert status
        # (this in effect "extends" the channel object to support the inverted attribute,
        #  if it's not already there)
        for i in self.channels.keys():
            self.channels[i]._inverted(self._sync_command(f"{self._block_id} get invert {i}").value)

    def refresh_status(self) -> None:
        """
        Manually refresh/poll block status again

        For now, the compromise for these blocks is we accept the possibility that their attributes
        may be out of date, and let the end-user manually call a refresh when needed

        TODO: might want to give them an option to set a refresh timer for these blocks?
        """
        self._query_status_attributes()

    # =================================================================================================================

    def subscription_callback(self, response : TTPResponse) -> None:
        """
        Handle incoming subscription callbacks
        """

        # Fault-on-inactive status update callback
        if response.subscription_type == "faultOnInactive":
            if int(response.subscription_channel_id) in self.channels.keys():
                self.channels[int(response.subscription_channel_id)]._fault_on_inactive(response.value)

        # Process base subscription callbacks too!
        super().subscription_callback(response)

    # =================================================================================================================