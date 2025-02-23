#!/usr/bin/env python3
from threading import Event
from queue import Queue
from pytesira.block.base_level_mute_no_subscription import BaseLevelMuteNoSubscription
from pytesira.util.types import NoiseGeneratorType, TTPResponseType
import logging


class NoiseGenerator(BaseLevelMuteNoSubscription):
    """
    Noise generator block
    """

    # Define version of this block's code here. A mismatch between this
    # and the value saved in the cached attribute-list value file will
    # trigger a re-discovery of attributes, to handle any changes
    VERSION = "0.1.1"

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

        # Block ID
        self._block_id = block_id

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

        # Query status attributes
        self._query_status_attributes()

    # =================================================================================================================

    def _query_status_attributes(self):
        """
        Query status attributes that doesn't support subscriptions
        """
        super()._query_status_attributes
        self.__noise_type = NoiseGeneratorType(
            str(self._sync_command(f"{self._block_id} get type").value).upper().strip()
        )
        self.channels[0]._muted(self._sync_command(f"{self._block_id} get mute").value)

    # =================================================================================================================

    @property
    def noise_type(self) -> bool:
        if self.__noise_type is None:
            raise AttributeError("unsupported attribute noise_type")
        return self.__noise_type

    @noise_type.setter
    def noise_type(self, value: NoiseGeneratorType) -> None:
        assert type(value) is NoiseGeneratorType
        rtn_val, cmd_res = self._set_and_update_val("type", value=str(value.value))
        self.__noise_type = NoiseGeneratorType(str(rtn_val).upper().strip())

        if cmd_res.type != TTPResponseType.CMD_OK:
            raise ValueError(cmd_res.value)
        return cmd_res
