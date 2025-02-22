#!/usr/bin/env python3
from threading import Event
from pytesira.block.block import Block
from queue import Queue
from pytesira.util.types import TTPResponseType
import logging


class Ducker(Block):
    """
    Ducker DSP block
    """

    # Define version of this block's code here. A mismatch between this
    # and the value saved in the cached attribute-list value file will
    # trigger a re-discovery of attributes, to handle any changes
    VERSION = "0.1.0"

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
            self.__query_base_attributes()

        # Query status on start, too
        self.__query_status_attributes()

        # Initialization helper base
        self._init_helper = {}

    # =================================================================================================================

    def __load_init_helper(self, init_helper: dict) -> None:
        """
        Use initialization helper to set up attributes instead of querying
        """
        # Nothing to see here, move along...
        pass

    # =================================================================================================================

    def __query_base_attributes(self) -> None:
        """
        Query base attributes - that is, things we don't expect to be changed
        and should save into the initialization helper to make next time loading
        at least a bit faster
        """
        # Also nothing to see here...
        pass

    def __query_status_attributes(self) -> None:
        """
        Query status attributes - e.g., those that we expect to be changed (or tweaked) at runtime
        For duckers, it's practically everything we support...
        """

        # Mix sense (do we want to add sense audio to the mix?)
        self.__mix_sense = self._sync_command(f"{self._block_id} get mixSense").value

        # Sense configuration
        self.__sense_level = self._sync_command(
            f"{self._block_id} get senseLevel"
        ).value
        self.__sense_mute = self._sync_command(f"{self._block_id} get senseMute").value

        # Threshold and ducking level
        self.__threshold = self._sync_command(f"{self._block_id} get threshold").value
        self.__ducking_level = self._sync_command(
            f"{self._block_id} get duckingLevel"
        ).value

        # Attack and release times
        self.__attack_time = self._sync_command(
            f"{self._block_id} get attackTime"
        ).value
        self.__release_time = self._sync_command(
            f"{self._block_id} get releaseTime"
        ).value

        # Input stuff
        self.__input_mute = self._sync_command(f"{self._block_id} get inputMute").value
        self.__input_level = self._sync_command(
            f"{self._block_id} get inputLevel"
        ).value
        self.__min_input_level = self._sync_command(
            f"{self._block_id} get minInputLevel"
        ).value
        self.__max_input_level = self._sync_command(
            f"{self._block_id} get maxInputLevel"
        ).value

        # Bypass status
        self.__bypass = self._sync_command(f"{self._block_id} get bypass").value

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
    def bypass(self, value: bool) -> None:
        self.__bypass, cmd_res = self._set_and_update_val("bypass", value=value)
        if cmd_res.type != TTPResponseType.CMD_OK:
            raise ValueError(cmd_res.value)
        return cmd_res

    # =================================================================================================================

    @property
    def mix_sense(self) -> bool:
        return self.__mix_sense

    @mix_sense.setter
    def mix_sense(self, value: bool) -> None:
        self.__mix_sense, cmd_res = self._set_and_update_val("mixSense", value=value)
        if cmd_res.type != TTPResponseType.CMD_OK:
            raise ValueError(cmd_res.value)
        return cmd_res

    # =================================================================================================================

    @property
    def sense_level(self) -> bool:
        return self.__sense_level

    @sense_level.setter
    def sense_level(self, value: float) -> None:
        self.__sense_level, cmd_res = self._set_and_update_val(
            "senseLevel", value=value
        )
        if cmd_res.type != TTPResponseType.CMD_OK:
            raise ValueError(cmd_res.value)
        return cmd_res

    # =================================================================================================================

    @property
    def sense_mute(self) -> bool:
        return self.__sense_mute

    @sense_mute.setter
    def sense_mute(self, value: bool) -> None:
        self.__sense_mute, cmd_res = self._set_and_update_val("senseMute", value=value)
        if cmd_res.type != TTPResponseType.CMD_OK:
            raise ValueError(cmd_res.value)
        return cmd_res

    # =================================================================================================================

    @property
    def threshold(self) -> bool:
        return self.__threshold

    @threshold.setter
    def threshold(self, value: float) -> None:
        self.__threshold, cmd_res = self._set_and_update_val("threshold", value=value)
        if cmd_res.type != TTPResponseType.CMD_OK:
            raise ValueError(cmd_res.value)
        return cmd_res

    # =================================================================================================================

    @property
    def ducking_level(self) -> bool:
        return self.__ducking_level

    @ducking_level.setter
    def ducking_level(self, value: float) -> None:
        self.__ducking_level, cmd_res = self._set_and_update_val(
            "duckingLevel", value=value
        )
        if cmd_res.type != TTPResponseType.CMD_OK:
            raise ValueError(cmd_res.value)
        return cmd_res

    # =================================================================================================================

    @property
    def attack_time(self) -> bool:
        return self.__attack_time

    @attack_time.setter
    def attack_time(self, value: float) -> None:
        self.__attack_time, cmd_res = self._set_and_update_val(
            "attackTime", value=value
        )
        if cmd_res.type != TTPResponseType.CMD_OK:
            raise ValueError(cmd_res.value)
        return cmd_res

    # =================================================================================================================

    @property
    def release_time(self) -> bool:
        return self.__release_time

    @release_time.setter
    def release_time(self, value: float) -> None:
        self.__release_time, cmd_res = self._set_and_update_val(
            "releaseTime", value=value
        )
        if cmd_res.type != TTPResponseType.CMD_OK:
            raise ValueError(cmd_res.value)
        return cmd_res

    # =================================================================================================================

    @property
    def input_mute(self) -> bool:
        return self.__input_mute

    @input_mute.setter
    def input_mute(self, value: bool) -> None:
        self.__input_mute, cmd_res = self._set_and_update_val("inputMute", value=value)
        if cmd_res.type != TTPResponseType.CMD_OK:
            raise ValueError(cmd_res.value)
        return cmd_res

    # =================================================================================================================

    @property
    def input_level(self) -> bool:
        return self.__input_level

    @input_level.setter
    def input_level(self, value: float) -> None:
        self.__input_level, cmd_res = self._set_and_update_val(
            "inputLevel", value=value
        )
        if cmd_res.type != TTPResponseType.CMD_OK:
            raise ValueError(cmd_res.value)
        return cmd_res

    # =================================================================================================================

    @property
    def min_input_level(self) -> bool:
        return self.__min_input_level

    @min_input_level.setter
    def min_input_level(self, value: float) -> None:
        self.__min_input_level, cmd_res = self._set_and_update_val(
            "minInputLevel", value=value
        )
        if cmd_res.type != TTPResponseType.CMD_OK:
            raise ValueError(cmd_res.value)
        return cmd_res

    # =================================================================================================================

    @property
    def max_input_level(self) -> bool:
        return self.__max_input_level

    @max_input_level.setter
    def max_input_level(self, value: float) -> None:
        self.__max_input_level, cmd_res = self._set_and_update_val(
            "maxInputLevel", value=value
        )
        if cmd_res.type != TTPResponseType.CMD_OK:
            raise ValueError(cmd_res.value)
        return cmd_res

    # =================================================================================================================
