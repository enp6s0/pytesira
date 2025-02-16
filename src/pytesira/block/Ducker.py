#!/usr/bin/env python3
from threading import Event
from pytesira.block.block import Block
from queue import Queue
from pytesira.util.ttp_response import TTPResponse, TTPResponseType
import time
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
            self._logger.debug(f"cannot use initialization helper: {e}")
            self.__query_base_attributes()

        # Query status on start, too
        self.__query_status_attributes()

        # Initialization helper base
        self._init_helper = {}

    # =================================================================================================================

    def __load_init_helper(self, init_helper : dict) -> None:
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
        self.mix_sense = self._sync_command(f"{self._block_id} get mixSense").value

        # Sense configuration
        self.sense_level = self._sync_command(f"{self._block_id} get senseLevel").value
        self.sense_mute = self._sync_command(f"{self._block_id} get senseMute").value

        # Threshold and ducking level
        self.threshold = self._sync_command(f"{self._block_id} get threshold").value
        self.ducking_level = self._sync_command(f"{self._block_id} get duckingLevel").value

        # Attack and release times
        self.attack_time = self._sync_command(f"{self._block_id} get attackTime").value
        self.release_time = self._sync_command(f"{self._block_id} get releaseTime").value

        # Input stuff
        self.input_mute = self._sync_command(f"{self._block_id} get inputMute").value
        self.input_level = self._sync_command(f"{self._block_id} get inputLevel").value
        self.min_input_level = self._sync_command(f"{self._block_id} get minInputLevel").value
        self.max_input_level = self._sync_command(f"{self._block_id} get maxInputLevel").value

        # Bypass status
        self.bypass = self._sync_command(f"{self._block_id} get bypass").value

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

    # Setter methods for flags and variables

    def set_bypass(self, value : bool) -> TTPResponse:
        self.bypass, cmd_res = self._set_and_update_val("bypass", value = value)
        return cmd_res

    def set_mix_sense(self, value : bool) -> TTPResponse:
        self.mix_sense, cmd_res = self._set_and_update_val("mixSense", value = value)
        return cmd_res

    def set_sense_level(self, value : float) -> TTPResponse:
        self.sense_level, cmd_res = self._set_and_update_val("senseLevel", value = value)
        return cmd_res

    def set_sense_mute(self, value : bool) -> TTPResponse:
        self.sense_mute, cmd_res = self._set_and_update_val("senseMute", value = value)
        return cmd_res

    def set_threshold(self, value : float) -> TTPResponse:
        self.threshold, cmd_res = self._set_and_update_val("threshold", value = value)
        return cmd_res

    def set_ducking_level(self, value : float) -> TTPResponse:
        self.ducking_level, cmd_res = self._set_and_update_val("duckingLevel", value = value)
        return cmd_res

    def set_attack_time(self, value : float) -> TTPResponse:
        self.atack_time, cmd_res = self._set_and_update_val("attackTime", value = value)
        return cmd_res

    def set_release_time(self, value : float) -> TTPResponse:
        self.release_time, cmd_res = self._set_and_update_val("releaseTime", value = value)
        return cmd_res

    def set_input_mute(self, value : bool) -> TTPResponse:
        self.release_time, cmd_res = self._set_and_update_val("inputMute", value = value)
        return cmd_res

    def set_input_level(self, value : float) -> TTPResponse:
        self.release_time, cmd_res = self._set_and_update_val("inputLevel", value = value)
        return cmd_res

    def set_min_input_level(self, value : float) -> TTPResponse:
        self.release_time, cmd_res = self._set_and_update_val("minInputLevel", value = value)
        return cmd_res

    def set_max_input_level(self, value : float) -> TTPResponse:
        self.release_time, cmd_res = self._set_and_update_val("maxInputLevel", value = value)
        return cmd_res   

    # =================================================================================================================