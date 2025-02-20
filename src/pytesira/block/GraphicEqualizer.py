#!/usr/bin/env python3
from threading import Event
from pytesira.block.block import Block
from queue import Queue
from pytesira.util.ttp_response import TTPResponse, TTPResponseType
from pytesira.util.band import Band
import time
import logging

class GraphicEqualizer(Block):
    """
    Graphic equalizer DSP block
    """

    # Define version of this block's code here. A mismatch between this
    # and the value saved in the cached attribute-list value file will
    # trigger a re-discovery of attributes, to handle any changes
    VERSION = "0.3.0"

    # =================================================================================================================

    def __init__(self,
        block_id: str,                  # block ID on Tesira
        exit_flag: Event,               # exit flag to stop the block's threads (sync'd with everything else)                    
        connected_flag: Event,          # connected flag (module can refuse to allow access if this is not set)
        command_queue: Queue,           # command queue (to run synchronous commands and get results)
        subscriptions: dict,            # subscription container on main thread
        init_helper: str|None = None,   # initialization helper (if not specified, query everything from scratch)
    ) -> None:

        # Block ID for later use
        self._block_id = block_id

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

        # Initialization helper
        self._init_helper = {
            "bands" : {}
        }
        for idx, b in self.bands.items():
            self._init_helper["bands"][int(idx)] = b.schema

    # =================================================================================================================

    def __load_init_helper(self, init_helper : dict) -> None:
        """
        Use initialization helper to set up attributes instead of querying
        """
        self.bands = {}
        for i, d in init_helper["bands"].items():
            self.bands[int(i)] = Band(self._block_id, int(i), self.__attribute_change_callback, d)

    # =================================================================================================================

    def __query_base_attributes(self) -> None:
        """
        Query base attributes - that is, things we don't expect to be changed
        and should save into the initialization helper to make next time loading
        at least a bit faster
        """

        # How many bands?
        num_bands = int(self._sync_command(f"{self._block_id} get numBands").value)
        self.bands = {}

        # Create a "blank slate" band for each EQ band
        for i in range(1, num_bands + 1):
            self.bands[int(i)] = Band(self._block_id, int(i), self.__attribute_change_callback, {})

    def __query_status_attributes(self) -> None:
        """
        Query status attributes - e.g., current bypass status or current band gain setting.
        We hope to not have to do this too often, as it takes A LOT of time with full 31-band EQs
        but may have to, in case the values are changed by external control...
        """

        # Get attributes for each band
        for i in self.bands.keys():
            self.bands[int(i)]._level(self._sync_command(f"{self._block_id} get gain {i}").value)
            self.bands[int(i)]._min_level(self._sync_command(f"{self._block_id} get minGain {i}").value)
            self.bands[int(i)]._max_level(self._sync_command(f"{self._block_id} get maxGain {i}").value)
            self.bands[int(i)]._bypass(self._sync_command(f"{self._block_id} get bypass {i}").value)

        # Bypass-all status
        self.__bypass = self._sync_command(f"{self._block_id} get bypassAll").value

    # =================================================================================================================

    def __attribute_change_callback(self, data_type : str, source_index : int, new_value : bool|str|float|int) -> TTPResponse:
        """
        Send out commands when we get an attribute change on one of our sources
        """

        # Gain changes
        if data_type in ["level", "min_level", "max_level"]:

            # Translation on what to set
            _tdict = {
                "level" : "gain",
                "min_level" : "minGain",
                "max_level" : "maxGain"
            }
            to_set = _tdict[str(data_type).lower().strip()]

            # Update value and local cache of the same value (using the "magic" updater method)
            new_val, cmd_res = self._set_and_update_val(to_set, new_value, source_index)
            getattr(self.bands[int(source_index)], f"_{data_type}")(new_val)

            if cmd_res.type != TTPResponseType.CMD_OK:
                raise ValueError(cmd_res.value)
            return cmd_res
            
        # Bypass change
        elif data_type == "bypass":

            new_val, cmd_res = self._set_and_update_val("bypass", str(new_value).lower(), source_index)
            self.bands[int(source_index)]._bypass(new_val)

            if cmd_res.type != TTPResponseType.CMD_OK:
                raise ValueError(cmd_res.value)
            return cmd_res

        else:
            # Not supported (yet?)
            self._logger.warning(f"unhandled attribute change: {data_type}")

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
    def bypass(self, value : bool) -> None:
        """
        Set 'bypass all channels' value
        """
        assert type(value) == bool, "invalid value type for bypass"

        # To update the block status, we don't have a subscription, so we do a query (just to confirm)
        self.__bypass, cmd_result = self._set_and_update_val("bypassAll", str(value).lower())
        
        # Raise an error if the original command didn't return OK for whatever reason
        if cmd_result.type != TTPResponseType.CMD_OK:
            raise ValueError(cmd_result.value)