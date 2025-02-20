#!/usr/bin/env python3
from threading import Event
from pytesira.block.block import Block
from queue import Queue
from pytesira.util.ttp_response import TTPResponse, TTPResponseType
from pytesira.util.channel import Channel

class BaseLevelMute(Block):

    """
    Base class for blocks supporting per-channel level and mute settings
    (e.g., LevelControl, DanteInput, DanteOutput)

    Not instantiated directly by the main code
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

        # My block ID
        self.__block_id = block_id

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

        # Setup subscriptions
        self._register_base_subscriptions()

        # Initialization helper base
        # (this will be used by export_init_helper() in the superclass to save initialization maps)
        # (additional attributes may then be set by the subclass extending BaseLevelMute)
        self._init_helper = {
            "channels" : {}
        }
        for idx, c in self.channels.items():
            self._init_helper["channels"][int(idx)] = c.schema

    # =================================================================================================================

    def _channel_change_callback(self, data_type : str, channel_index : int, new_value : bool|str|float|int) -> TTPResponse:
        """
        Send out commands when we get a change on one of our channels
        """

        if data_type == "muted":
            cmd_res = self._sync_command(f'"{self._block_id}" set mute {channel_index} {str(new_value).lower()}')
            if cmd_res.type != TTPResponseType.CMD_OK:
                raise ValueError(cmd_res.value)
            return cmd_res

        elif data_type == "level":
            cmd_res = self._sync_command(f'"{self._block_id}" set level {channel_index} {new_value}')
            if cmd_res.type != TTPResponseType.CMD_OK:
                raise ValueError(cmd_res.value)
            return cmd_res

        else:
            # Not supported (yet?)
            self._logger.warning(f"unhandled attribute change: {data_type}")

    # =================================================================================================================

    def _register_base_subscriptions(self) -> None:
        """
        (re)register subscriptions for this module. This should be called by each
        module on init, and may be called again by the main thread if an interruption
        in connectivity is detected (e.g., SSH disconnect-then-reconnect)
        """
        self._register_subscription(subscribe_type = "mutes", channel = None)
        self._register_subscription(subscribe_type = "levels", channel = None)

    # =================================================================================================================

    def __load_init_helper(self, init_helper : dict) -> None:
        """
        Use initialization helper to set up attributes instead of querying
        """
        self.channels = {}
        for i, d in init_helper["channels"].items():
            self.channels[int(i)] = Channel(self.__block_id, int(i), self._channel_change_callback, d)

    # =================================================================================================================

    def subscription_callback(self, response : TTPResponse) -> None:
        """
        Handle incoming subscription callbacks
        """
        # Mutes?
        if response.subscription_type == "mutes":
            for i, mute in enumerate(response.value):
                idx = i + 1
                if int(idx) in self.channels.keys():
                    self.channels[int(idx)]._muted(mute)
                else:
                    self._logger.error(f"mute response invalid index: {idx}")
            self._logger.debug(f"mute state changed: {response.value}")

        # Levels?
        elif response.subscription_type == "levels":
            for i, level in enumerate(response.value):
                idx = i + 1
                if int(idx) in self.channels.keys():
                    self.channels[int(idx)]._level(level)
                else:
                    self._logger.error(f"level response invalid index: {idx}")
            self._logger.debug(f"levels changed: {response.value}")

        # Call superclass handler to deal with the callbacks we may have to make
        super().subscription_callback(response)

    # =================================================================================================================

    def __query_base_attributes(self) -> None:

        # How many channels?
        num_channels = int(self._sync_command(f"{self._block_id} get numChannels").value)
        self.channels = {}

        # For each channel, what's the index and labels?
        # NOTE: Tesira indices starts at 1, in some cases 0 is a special ID meaning all channels
        for i in range(1, num_channels + 1):

            # Query label
            label_query = self._sync_command(f"{self._block_id} get {self._chan_label_key} {i}")
            if label_query.type == TTPResponseType.CMD_ERROR:
                channel_label = ""
            else:
                channel_label = str(label_query.value).strip()

            self.channels[int(i)] = Channel(self.__block_id, int(i), self._channel_change_callback, {
                "label" : channel_label,
                "min_level" : self._sync_command(f"{self._block_id} get minLevel {i}").value,
                "max_level" : self._sync_command(f"{self._block_id} get maxLevel {i}").value
            })