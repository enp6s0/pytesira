#!/usr/bin/env python3
from threading import Event
from queue import Queue
from pytesira.util.ttp_response import TTPResponse, TTPResponseType
from collections.abc import Callable
import time

class Block:

    # Define version of this block's code here. A mismatch between this
    # and the value saved in the cached attribute-list value file will
    # trigger a re-discovery of attributes, to handle any changes
    VERSION = "base-0.1.0"

    def __init__(self,
        block_id: str,                  # block ID on Tesira
        exit_flag: Event,               # exit flag to stop the block's threads (sync'd with everything else)                    
        connected_flag: Event,          # connected flag (module can refuse to allow access if this is not set)
        command_queue: Queue,           # command queue (to run synchronous commands and get results)
        subscriptions: dict,            # subscription container on main thread
        init_helper: str|None = None,   # initialization helper (if not specified, query everything from scratch)
    ) -> None:

        # Logger should be set up first by subclass, but if not
        # we can also set it up again here
        if not self._logger:
            self._logger = logging.getLogger(f"{__name__}.{block_id}")
        
        # Load setup variables
        self._block_id = str(block_id)
        self._exit = exit_flag
        self._connected = connected_flag
        self._command_queue = command_queue
        self._init_helper = init_helper
        self._subscriptions = subscriptions

        # Synchronous command mailbox
        self._sync_cmd_mailbox = None

        # Callbacks
        self._callbacks = {}

    def register_subscriptions(self) -> None:
        """
        (re)register subscriptions for this module. This should be called by each
        module on init, and may be called again by the main thread if an interruption
        in connectivity is detected (e.g., SSH disconnect-then-reconnect)
        """
        return

    def subscription_callback(self, response : TTPResponse) -> None:
        """
        Subscription results matching this block ID will be returned here so that
        they can be processed
        """

        # Call handler that should call OUR callbacks as well
        self._on_subscription_callback()

        return

    def subscribe(self) -> None:
        """
        Set up required subscriptions. Can be omitted (base class stub used)
        if the block type does not require any subscriptions
        """
        return

    def export_init_helper(self) -> dict:
        """
        Export initialization helper/map. This will be called by the main thread
        after the attribute query process, which allows for the block map
        to be updated
        """
        return {
            "version" : self.VERSION,
            "helper" : self._init_helper
        }

    def set_mute(self, value : bool, channel : int = 0) -> TTPResponse:
        """
        Stub for set mute, for blocks that supports it
        """
        raise NotImplementedError

    def set_level(self, value : float, channel : int = 0) -> TTPResponse:
        """
        Stub for set audio level, for blocks that supports it
        """
        raise NotImplementedError

    # =================================================================================================================
    # Generally, there's no need to change or override methods below here, they apply to every block in the same way
    # =================================================================================================================

    def register_callback(self, callback : Callable, key : str|None = None) -> None:
        """
        Register a callback, optionally specifying a callback key so it can be 
        easily unregistered if so needed
        """
        self._callbacks[key if key else callback] = callback
        self._logger.debug(f"callback registered ({len(self._callbacks)} active callbacks)")

    def unregister_callback(self, key : str) -> None:
        """
        Unregister callback based on key specified earlier on callback creation
        """
        try:
            del self._callbacks[key]
            self._logger.debug(f"callback removed ({len(self._callbacks)} active callbacks)")
        except Exception as e:
            self._logger.warning(f"cannot remove callback {key}: {e}")

    # =================================================================================================================
    # More internal functions which should only be called by this class and its subclasses
    # again, they should apply to every block in the same way, so no need to edit or override them
    # =================================================================================================================

    def _on_subscription_callback(self):
        """
        Handler for "on subscription callback": checks all locally registered callbacks
        and call them if possible (with current block as the object variable)
        """
        for key, callback in self._callbacks.items():
            if callable(callback):
                callback(self)
                self._logger.debug(f"callback invoked: {callback}")
            else:
                self._logger.debug(f"uncallable callback: {callback} ({type(callback)})")

    def _register_subscription(self, subscribe_type : str, channel : int|None = None) -> None:
        """
        Register subscription with the DSP. This function generates the subscription command
        with the correct prefix IDs and metadata, such that responses will be directed back here

        DO NOT CHANGE this without also double checking what's done in the main thread
        AS WELL AS TTPResponse, otherwise subscribed data might end up in the wrong place!
        """

        # Subscriptions can be done on a per channel basis too, so we need to handle that
        sub_channel = "" if channel is None else f" {channel}"
        channel_id = "ALL" if sub_channel == "" else str(sub_channel).strip()

        # Create subscription name
        sub_name = f"S_{subscribe_type}_{channel_id}_{self._block_id}"

        # Create subscription string
        sub_string = f'"{self._block_id}" subscribe {subscribe_type}{sub_channel} "{sub_name}"'

        # Add that subscription to the main subscription list
        subscription_meta = (self, self._block_id, sub_name, sub_string)
        self._subscriptions[sub_name] = subscription_meta

        # Send command to device to actually start subscription
        self._sync_command(sub_string)
        self._logger.debug(f"subscription setup: {self._block_id} {subscribe_type} (total {len(self._subscriptions)} subscriptions active)")

    def _sync_command_callback(self, data : TTPResponse) -> None:
        """
        Should we queue a synchronous command and that gets executed by the main thread,
        this method gets called for a response to that command
        """
        self._sync_cmd_mailbox = data
        return

    def _sync_command(self, command : str, timeout : float = 3.0) -> TTPResponse:
        """
        Execute synchronous command (technically this abstracts it behind a queue,
        but we don't have to see that elsewhere in the block module code, which makes it nicer!)
        """
        # Reset mailbox, just in case
        self._sync_cmd_mailbox = None

        # Queue command
        self._command_queue.put((self, command))
        cmd_queued = time.perf_counter()

        # Now we wait until we either get data or timeout occurs, whichever comes first
        while time.perf_counter() - cmd_queued < timeout:

            # Let other tasks run
            time.sleep(0.01)

            # Did we get something?
            if self._sync_cmd_mailbox:
                cmd_response = self._sync_cmd_mailbox
                self._sync_cmd_mailbox = None
                return cmd_response

        # If we're here, we got... nothing
        self._sync_cmd_mailbox = None
        raise Exception(f"Command timeout: {command}")