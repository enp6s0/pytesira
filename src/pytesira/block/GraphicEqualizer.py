#!/usr/bin/env python3
from threading import Event
from pytesira.block.block import Block
from queue import Queue
from pytesira.util.ttp_response import TTPResponse, TTPResponseType
import time
import logging

class GraphicEqualizer(Block):
    """
    Graphic equalizer DSP block
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
        self._init_helper = {
            "bands" : self.bands
        }

    # =================================================================================================================

    def __load_init_helper(self, init_helper : dict) -> None:
        """
        Use initialization helper to set up attributes instead of querying
        """
        self.bands = init_helper["bands"]
        
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

        # For each band, what's the minimum and maximum ranges?
        for i in range(1, num_bands + 1):

            self.bands[str(i)] = {
                "index" : i,
                "gain" : {
                    "min" : self._sync_command(f"{self._block_id} get minGain {i}").value,
                    "max" : self._sync_command(f"{self._block_id} get maxGain {i}").value,
                },
            }

    def __query_status_attributes(self) -> None:
        """
        Query status attributes - e.g., current bypass status or current band gain setting.
        We hope to not have to do this too often, as it takes A LOT of time with full 31-band EQs
        but may have to, in case the values are changed by external control...
        """

        for i in self.bands.keys():
            self.bands[str(i)]["gain"]["current"] = self._sync_command(f"{self._block_id} get gain {i}").value
            self.bands[str(i)]["bypass"] = self._sync_command(f"{self._block_id} get bypass {i}").value

        # Bypass-all status
        self.bypass = self._sync_command(f"{self._block_id} get bypassAll").value

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

    def set_bypass_all(self, value : bool) -> TTPResponse:
        """
        Set 'bypass all channels' value
        """
        assert type(value) == bool, "invalid value type for set_bypass_all"

        # To update the block status, we don't have a subscription, so we do a query (just to confirm)
        cmd_result = self._sync_command(f'"{self._block_id}" set bypassAll {str(value).lower()}')
        self.bypass = self._sync_command(f"{self._block_id} get bypassAll").value

        return cmd_result

    def set_bypass(self, value : bool, band : int = 0) -> TTPResponse:
        """
        Set per-channel bypass
        """
        assert type(value) == bool, "invalid value type for set_bypass"
        assert type(band) == int, "invalid band type for set_bypass"

        # Same as above, send command and query
        cmd_result = self._sync_command(f'"{self._block_id}" set bypass {band} {str(value).lower()}')
        self.bands[str(band)]["bypass"] = self._sync_command(f"{self._block_id} get bypass {band}").value

        return cmd_result

    def set_band_gain(self, value : float, band : int = 0) -> TTPResponse:
        """
        Set gain on a band
        """
        assert type(value) == float, "invalid value type for set_band_gain"
        assert type(band) == int, "invalid band type for set_band_gain"

        # Same as above again, send command and query
        cmd_result = self._sync_command(f'"{self._block_id}" set gain {band} {value}')
        self.bands[str(band)]["gain"]["current"] = self._sync_command(f"{self._block_id} get gain {band}").value

        return cmd_result

    # =================================================================================================================