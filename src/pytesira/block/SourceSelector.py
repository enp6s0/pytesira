#!/usr/bin/env python3
from threading import Event
from pytesira.block.block import Block
from queue import Queue
from pytesira.util.ttp_response import TTPResponse, TTPResponseType
from pytesira.util.source import Source
import logging


class SourceSelector(Block):

    # Define version of this block's code here. A mismatch between this
    # and the value saved in the cached attribute-list value file will
    # trigger a re-discovery of attributes, to handle any changes
    VERSION = "0.3.0"

    # =================================================================================================================

    def __init__(
        self,
        block_id: str,  # block ID on Tesira
        exit_flag: Event,  # exit flag to stop the block's threads (sync'd with everything else)
        connected_flag: Event,  # connected flag (module can refuse to allow access if this is not set)
        command_queue: Queue,  # command queue (to run synchronous commands and get results)
        subscriptions: dict,  # subscription container on main thread
        init_helper: (
            str | None
        ) = None,  # initialization helper (if not specified, query everything from scratch)
    ) -> None:

        # Save block ID for callbacks and later changes
        self.__block_id = block_id

        # Setup logger
        self._logger = logging.getLogger(f"{__name__}.{block_id}")

        # Initialize base class
        super().__init__(
            block_id,
            exit_flag,
            connected_flag,
            command_queue,
            subscriptions,
            init_helper,
        )

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
            "stereo": self.stereo,
            "num_input": self.num_input,
            "num_output": self.num_output,
            "sources": {},
            "min_output_level": self.min_output_level,
            "max_output_level": self.max_output_level,
            "output_level": self.__output_level,
        }
        for idx, s in self.sources.items():
            self._init_helper["sources"][int(idx)] = s.schema

    # =================================================================================================================

    def register_subscriptions(self) -> None:
        """
        (re)register subscriptions for this module. This should be called by each
        module on init, and may be called again by the main thread if an interruption
        in connectivity is detected (e.g., SSH disconnect-then-reconnect)
        """
        self._register_subscription(subscribe_type="outputMute", channel=None)
        self._register_subscription(subscribe_type="outputLevel", channel=None)
        self._register_subscription(subscribe_type="sourceSelection", channel=None)

        # Subscribe to source levels too
        for index in self.sources.keys():
            self._register_subscription(subscribe_type="sourceLevel", channel=index)

    # =================================================================================================================

    def __load_init_helper(self, init_helper: dict) -> None:
        """
        Use initialization helper to set up attributes instead of querying
        """
        self.stereo = bool(init_helper["stereo"])
        self.num_input = int(init_helper["num_input"])
        self.num_output = int(init_helper["num_output"])
        self.__muted = False  # updated by subscription, not in helper
        self.__selected_source = 0  # updated by subscription, not in helper
        self.__output_level = init_helper["output_level"]
        self.min_output_level = init_helper["min_output_level"]
        self.max_output_level = init_helper["max_output_level"]

        self.sources = {}
        for i, d in init_helper["sources"].items():
            self.sources[int(i)] = Source(
                self.__block_id, int(i), self._source_attribute_change_callback, d
            )

    # =================================================================================================================

    def __query_attributes(self) -> None:

        # Stereo mode?
        self.stereo = bool(
            self._sync_command(f"{self._block_id} get stereoEnable").value
        )

        # Number of inputs and outputs
        self.num_input = int(
            self._sync_command(f"{self._block_id} get numInputs").value
        )
        self.num_output = int(
            self._sync_command(f"{self._block_id} get numOutputs").value
        )

        # Output muted?
        self.__muted = bool(
            self._sync_command(f"{self._block_id} get outputMute").value
        )

        # How many actual input channels (sources) and outputs?
        if self.stereo:
            self.num_input = int(self.num_input // 2)
            self.num_output = int(self.num_output // 2)

        # Which channel is selected? (0 = nothing)
        self.__selected_source = 0

        # For each source, they have index, label, and level attributes assigned
        # as well as a "selected" helper attribute to verify which source is currently selected
        # NOTE: Tesira indices starts at 1
        self.sources = {}
        for i in range(1, self.num_input + 1):
            self.sources[int(i)] = Source(
                self.__block_id,
                int(i),
                self._source_attribute_change_callback,
                {
                    "label": self._sync_command(
                        f"{self._block_id} get label {i}"
                    ).value,
                    "min_level": self._sync_command(
                        f"{self._block_id} get sourceMinLevel {i}"
                    ).value,
                    "max_level": self._sync_command(
                        f"{self._block_id} get sourceMaxLevel {i}"
                    ).value,
                },
            )

        # We also allow control of output levels
        self.min_output_level = self._sync_command(
            f"{self._block_id} get outputMinLevel"
        ).value
        self.max_output_level = self._sync_command(
            f"{self._block_id} get outputMaxLevel"
        ).value

    # =================================================================================================================

    def _source_attribute_change_callback(
        self, data_type: str, source_index: int, new_value: bool | str | float | int
    ) -> TTPResponse:
        """
        Send out commands when we get an attribute change on one of our sources
        """
        if data_type == "level":
            cmd_res = self._sync_command(
                f'"{self._block_id}" set sourceLevel {source_index} {new_value}'
            )
            if cmd_res.type != TTPResponseType.CMD_OK:
                raise ValueError(cmd_res.value)
            return cmd_res

        else:
            # Not supported (yet?)
            self._logger.warning(f"unhandled attribute change: {data_type}")

    # =================================================================================================================

    def subscription_callback(self, response: TTPResponse) -> None:
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
            self.__muted = bool(response.value)
            self._logger.debug(f"mute state = {response.value}")

        # Output level?
        elif response.subscription_type == "outputLevel":
            self.__output_level = float(response.value)
            self._logger.debug(f"output level = {response.value}")

        # Source selection?
        elif response.subscription_type == "sourceSelection":
            self.__selected_source = int(response.value)
            self._logger.debug(f"source selection = {response.value}")

        # Source levels?
        elif response.subscription_type == "sourceLevel":
            if int(response.subscription_channel_id) in self.sources.keys():
                self.sources[int(response.subscription_channel_id)]._level(
                    float(response.value)
                )
                self._logger.debug(
                    f"source level update on {response.subscription_channel_id} = {response.value}"
                )
            else:
                self._logger.error(
                    f"source level invalid index: {response.subscription_channel_id}"
                )

        # Huh, this isn't handled?
        else:
            self._logger.debug(f"unhandled subscription callback: {response}")

        # Call superclass handler to deal with callbacks
        super().subscription_callback(response)

    # =================================================================================================================

    @property
    def muted(self) -> bool:
        return self.__muted

    @muted.setter
    def muted(self, value: bool) -> None:
        assert type(value) == bool, "invalid type for muted"
        cmd_res = self._sync_command(
            f'"{self._block_id}" set outputMute {str(value).lower()}'
        )
        if cmd_res.type != TTPResponseType.CMD_OK:
            raise ValueError(cmd_res.value)

    # =================================================================================================================

    @property
    def selected_source(self) -> int:
        return self.__selected_source

    @selected_source.setter
    def selected_source(self, value: int) -> None:
        """
        Select a specific source (or specify source = 0 to not select anything)
        """
        assert type(value) == int, "invalid type for selected_source"
        assert 0 <= value, "invalid value for selected_source"
        cmd_res = self._sync_command(f'"{self._block_id}" set sourceSelection {value}')
        if cmd_res.type != TTPResponseType.CMD_OK:
            raise ValueError(cmd_res.value)

    # =================================================================================================================

    @property
    def output_level(self) -> float:
        return self.__output_level

    @output_level.setter
    def output_level(self, value: float) -> None:
        assert type(value) == float, "invalid type for value"
        cmd_res = self._sync_command(f'"{self._block_id}" set outputLevel {value}')
        if cmd_res.type != TTPResponseType.CMD_OK:
            raise ValueError(cmd_res.value)
