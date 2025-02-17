#!/usr/bin/env python3
from threading import Event
from pytesira.block.block import Block
from queue import Queue
from pytesira.util.ttp_response import TTPResponse, TTPResponseType
from pytesira.block.base_level_mute_no_subscription import BaseLevelMuteNoSubscription
import time
import logging

class BaseUSB(BaseLevelMuteNoSubscription):
    """
    Base block for USB I/O blocks

    (USB blocks are weird, they don't support subscription to levels, but DO support
    subscriptions for things like connection status and a bunch of host-related statuses)
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

        # Block ID
        self._block_id = block_id

        # Setup logger
        self._logger = logging.getLogger(f"{__name__}.{block_id}")

        # No channel label key, use autogeneration
        self._chan_label_key = "@"

        # Initialize base class
        super().__init__(block_id, exit_flag, connected_flag, command_queue, subscriptions, init_helper)

        # Query status attributes
        # (override base_level_mute_no_subscription)
        self._query_status_attributes()

        # Register base subscriptions
        self.__register_base_subscriptions()

    # =================================================================================================================

    def __register_base_subscriptions(self) -> None:
        """
        (re)register subscriptions for this module. This should be called by each
        module on init, and may be called again by the main thread if an interruption
        in connectivity is detected (e.g., SSH disconnect-then-reconnect)
        """
        self._register_subscription(subscribe_type = "hostMasterMute", channel = None)
        self._register_subscription(subscribe_type = "hostMasterVol", channel = None)
        for i in self.channels.keys():
            self._register_subscription(subscribe_type = "hostMute", channel = int(i))
            self._register_subscription(subscribe_type = "hostVol", channel = int(i))

            # TODO: we need to handle peak-occuring as callback triggering only
            # but no internal state updates, WHILE letting called functions know
            # exactly which channel is peaking
            # self._register_subscription(subscribe_type = "peak", channel = int(i))

        self._register_subscription(subscribe_type = "connected", channel = None)
        self._register_subscription(subscribe_type = "streaming", channel = None)

    def _query_status_attributes(self) -> None:
        """
        Query status attributes - e.g., those that we expect to be changed (or tweaked) at runtime
        """
        for i in self.channels.keys():
            self.channels[i]._muted(self._sync_command(f"{self._block_id} get mute {i}").value)
            self.channels[i]._level(self._sync_command(f"{self._block_id} get level {i}").value)

    # =================================================================================================================

    def subscription_callback(self, response : TTPResponse) -> None:
        """
        Handle incoming subscription callbacks
        """
        # Master mute, volume (level)?
        if response.subscription_type == "hostMasterMute":
            self.host_muted = response.value
        elif response.subscription_type == "hostMasterVol":
            self.host_level = response.value
        
        # Connected or streaming states?
        elif response.subscription_type == "connected":
            self.connected = response.value
        elif response.subscription_type == "streaming":
            self.streaming = response.value

        # Per channel status?
        # TODO: migrate to new channel object
        #elif response.subscription_type == "hostMute":
        #    if int(response.subscription_channel_id) in self.channels.keys():
        #        self.channels[int(response.subscription_channel_id)]["host_muted"] = response.value
        #elif response.subscription_type == "hostVol":
        #    if int(response.subscription_channel_id) in self.channels.keys():
        #        self.channels[int(response.subscription_channel_id)]["level"]["host"] = response.value

        # Call superclass handler to deal with the callbacks we may have to make
        super().subscription_callback(response)

    # =================================================================================================================

    def set_mute(self, value : bool, channel : int = 0) -> TTPResponse:
        """
        set_mute is overridden for USB, since we apparently have two mute states - self-mute
        (which is polling only) and host mute (which is subscription)
        """
        self.channels[int(channel)]["dsp_muted"], cmd_res = self._set_and_update_val("mute", value = value, channel = channel)
        return cmd_res