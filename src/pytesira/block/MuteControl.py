#!/usr/bin/env python3
from threading import Event
from pytesira.block.block import Block
from queue import Queue
from pytesira.util.channel import Channel
from pytesira.util.ttp_response import TTPResponse, TTPResponseType
import logging

class MuteControl(Block):

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

        # Block ID
        self.__block_id = block_id

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

        # Setup subscriptions
        self.register_subscriptions()

        # Initialization helper (this will be used by export_init_helper() in the superclass
        # to save initialization maps)
        self._init_helper = {
            "ganged" : self.ganged,
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
            cmd_res = self._sync_command(f'"{self.__block_id}" set mute {channel_index} {str(new_value).lower()}')
            if cmd_res.type != TTPResponseType.CMD_OK:
                raise ValueError(cmd_res.value)
            return cmd_res

        else:
            # Not supported (yet?)
            self._logger.warning(f"unhandled attribute change: {data_type}")

    # =================================================================================================================

    def __load_init_helper(self, init_helper : dict) -> None:
        """
        Use initialization helper to set up attributes instead of querying
        """
        self.ganged = init_helper["ganged"]
        self.channels = {}
        for i, d in init_helper["channels"].items():
            self.channels[int(i)] = Channel(self.__block_id, int(i), self._channel_change_callback, d)

    # =================================================================================================================

    def register_subscriptions(self) -> None:
        """
        (re)register subscriptions for this module. This should be called by each
        module on init, and may be called again by the main thread if an interruption
        in connectivity is detected (e.g., SSH disconnect-then-reconnect)
        """
        self._register_subscription(subscribe_type = "mutes", channel = None)

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

        # Huh, this isn't handled?
        else:
            self._logger.debug(f"unhandled subscription callback: {response}")

        # Call superclass handler to deal with callbacks
        super().subscription_callback(response)

    # =================================================================================================================

    def __query_attributes(self) -> None:

        # Ganged setup?
        self.ganged = bool(self._sync_command(f"{self.__block_id} get ganged").value)

        # How many channels?
        num_channels = int(self._sync_command(f"{self.__block_id} get numChannels").value)
        self.channels = {}

        # For each channel, what's the index and labels?
        # NOTE: Tesira indices starts at 1, in some cases 0 is a special ID meaning all channels
        for i in range(1, num_channels + 1):
            self.channels[int(i)] = Channel(self.__block_id, int(i), self._channel_change_callback, {
                "label" : self._sync_command(f"{self.__block_id} get label {i}").value
            })