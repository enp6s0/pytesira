#!/usr/bin/env python3
from threading import Event
from pytesira.block.block import Block
from queue import Queue
from pytesira.util.ttp_response import TTPResponse, TTPResponseType
import time
import logging

class SourceSelector(Block):

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
            self._logger.warning(f"cannot use initialization helper: {e}")
            self.__query_attributes()

        # Setup subscriptions
        self.register_subscriptions()
        
    # =================================================================================================================

    def register_subscriptions(self) -> None:
        """
        (re)register subscriptions for this module. This should be called by each
        module on init, and may be called again by the main thread if an interruption
        in connectivity is detected (e.g., SSH disconnect-then-reconnect)
        """
        self._register_subscription(subscribe_type = "outputMute", channel = None)
        self._register_subscription(subscribe_type = "outputLevel", channel = None)
        self._register_subscription(subscribe_type = "sourceSelection", channel = None)

        # Subscribe to source levels too
        for index in self.sources.keys():
            self._register_subscription(subscribe_type = "sourceLevel", channel = index)

    # =================================================================================================================

    def __load_init_helper(self, init_helper : dict) -> None:
        """
        Use initialization helper to set up attributes instead of querying
        """
        self.stereo = bool(init_helper["stereo"])
        self.num_input = int(init_helper["num_input"])
        self.num_output = int(init_helper["num_output"])
        self.muted = False          # updated by subscription, not in helper
        self.selected_source = 0    # updated by subscription, not in helper
        self.sources = init_helper["sources"]
        self.output_level = init_helper["output_level"]

    def export_init_helper(self) -> dict:
        """
        Export initialization helper dict (to make setup faster in the future)
        """
        helper = super().export_init_helper()
        helper["helper"] = {
            "stereo" : self.stereo,
            "num_input" : self.num_input,
            "num_output" : self.num_output,
            "sources" : self.sources,
            "output_level" : self.output_level,
        }

        return helper

    # =================================================================================================================

    def __query_attributes(self) -> None:

        # Stereo mode?
        self.stereo = bool(self._sync_command(f"{self._block_id} get stereoEnable").value)

        # Number of inputs and outputs
        self.num_input = int(self._sync_command(f"{self._block_id} get numInputs").value)
        self.num_output = int(self._sync_command(f"{self._block_id} get numOutputs").value)

        # Output muted?
        self.muted = bool(self._sync_command(f"{self._block_id} get outputMute").value)

        # How many actual input channels (sources) and outputs?
        if self.stereo:
            self.num_input = int(self.num_input // 2)
            self.num_output = int(self.num_output // 2)

        # Which channel is selected? (0 = nothing)
        self.selected_source = 0

        # For each source, they have index, label, and level attributes assigned
        # as well as a "selected" helper attribute to verify which source is currently selected
        # NOTE: Tesira indices starts at 1
        self.sources = {}
        for i in range(1, self.num_input + 1):
            self.sources[str(i)] = {
                "index" : i,
                "label" : self._sync_command(f"{self._block_id} get label {i}").value,
                "level" : {
                    "min" : self._sync_command(f"{self._block_id} get sourceMinLevel {i}").value,
                    "max" : self._sync_command(f"{self._block_id} get sourceMaxLevel {i}").value,
                },
                "selected" : False
            }

        # We also allow control of output levels
        self.output_level = {
            "min" : self._sync_command(f"{self._block_id} get outputMinLevel").value,
            "max" : self._sync_command(f"{self._block_id} get outputMaxLevel").value
        }

    # =================================================================================================================

    def subscription_callback(self, response : TTPResponse) -> None:
        """
        Handle incoming subscription callbacks
        """

        """
        # Subscribe to source levels too
        for index in self.sources.keys():
            self._register_subscription(subscribe_type = "sourceLevel", channel = index)
        """

        # Output mute?
        if response.subscription_type == "outputMute":
            self.muted = bool(response.value)
            self._logger.debug(f"mute state = {response.value}")

        # Output level?
        elif response.subscription_type == "outputLevel":
            self.output_level["current"] = float(response.value)
            self._logger.debug(f"output level = {response.value}")

        # Source selection?
        elif response.subscription_type == "sourceSelection":
            self.selected_source = int(response.value)

            # Update each sources too for easy reference
            for i in self.sources.keys():
                self.sources[i]["selected"] = bool(str(i) == str(self.selected_source))

            self._logger.debug(f"source selection = {response.value}")

        # Source levels?
        elif response.subscription_type == "sourceLevel":
            if str(response.subscription_channel_id) in self.sources.keys():
                self.sources[str(response.subscription_channel_id)]["level"]["current"] = float(response.value)
                self._logger.debug(f"source level update on {response.subscription_channel_id} = {response.value}")
            else:
                self._logger.error(f"source level invalid index: {idx}")

        # Huh, this isn't handled?
        else:
            self._logger.debug(f"unhandled subscription callback: {response}")

        # Call superclass handler to deal with callbacks
        super().subscription_callback(response)

    # =================================================================================================================

    def set_mute(self, value : bool, channel : int = 0) -> TTPResponse:
        """
        Stub for set mute, for blocks that supports it

        Note that we keep the channel parameter to preserve compatibility with
        other set_mute's, but it's not used nor required in this case
        """
        assert type(value) == bool, "invalid value type for set_mute"
        return self._sync_command(f'"{self._block_id}" set outputMute {str(value).lower()}')

    # =================================================================================================================

    def select_source(self, source : int = 0) -> TTPResponse:
        """
        Select a specific source (or specify source = 0 to not select anything)
        """
        assert type(source) == int, "invalid value type for source"
        assert 0 <= source, "invalid value for source"
        return self._sync_command(f'"{self._block_id}" set sourceSelection {source}')

    # =================================================================================================================

    def set_source_level(self, source : int, value : float) -> TTPResponse:
        """
        Set level for a specific source
        """
        assert type(source) == int, "invalid value type for source"
        assert 1 <= source, "invalid value for source"
        assert type(value) == float, "invalid value type for level"
        return self._sync_command(f'"{self._block_id}" set sourceLevel {source} {value}')

    # =================================================================================================================

    def set_level(self, value : float, channel : int = 0) -> TTPResponse:
        """
        Set output level. Note that we keep the calling signature of set_level,
        but ignore channels here
        """
        assert type(value) == float, "invalid type for value"
        return self._sync_command(f'"{self._block_id}" set outputLevel {value}')