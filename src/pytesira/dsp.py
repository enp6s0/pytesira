#!/usr/bin/env python3
#
# PyTesira DSP class (the one thing that people will import)
#

# Base transport and block classes
from pytesira.transport.transport import Transport
from pytesira.block.block import Block
from pytesira.util.ttp_response import TTPResponse, TTPResponseType

# Others
import os
import time
import json
import queue
import logging
import importlib
import importlib.metadata
from datetime import datetime
from threading import Thread, Event


class DSP:
    """
    PyTesira DSP class - the main thing!

    TODO:
        * Graceful handling of SSH connection restarts - should also trigger re-subscription on blocks
    """

    def __init__(self,
        block_map : str | None = None,          # Block map (attributes cache) file location. This allows PyTesira to bypass block query
                                                # on startup, resulting in much faster initialization, but will result in incorrect attributes
                                                # if the system is reprogrammed through the Tesira software. If left blank, or there are
                                                # detectable differences (e.g., different number of DSP blocks), PyTesira will automatically
                                                # query the DSP for attribute updates, which may take some time (especially on complex setups)
        device_refresh_interval : int = 5,      # Device data refresh interval - how often should we poll for things like active alarms?
    ) -> None:

        # PyTesira version
        try:
            self.__version = importlib.metadata.version("pytesira")
        except importlib.metadata.PackageNotFoundError:
            # Heads up! This means that the version for local development changes daily
            # and will cause DSP block map caches to expire - this is expected.
            self.__version = f"local-dev-{datetime.today().strftime('%Y-%m-%d')}"

        # Ready for operation?
        self.ready = False

        # Get a local logger first
        self.__logger = logging.getLogger(__name__)
        self.__logger.info(f"PyTesira version {self.__version}")

        # Exit event for child threads, to coordinate a clean shutdown
        self.__exit = Event()

        # Status flags
        self.__connected = Event()              # are we connected to the DSP? If not, many operations are not possible, and any data           # noqa: E116
                                                # we may have cached might be stale. In that case, read/write access to DSP block objects       # noqa: E116
                                                # should raise an exception. Additionally, if the transport status has changed (say, a          # noqa: E116
                                                # re-connection has occured), DSP blocks will need to re-subscribe to TSP data streams.         # noqa: E116

        # Buffers
        self.__rx_buffer = ""                   # "raw" buffer for TTP (Tesira Text Protocol) data we received from device
        self.__rx_cmd_mailbox = None            # "command response" mailbox - here we only handle one command at a time!

        # Block map file
        self.__block_map = block_map

        # Device data refresh interval
        assert 1 <= int(device_refresh_interval), "invalid data refresh interval, must be >= 1"
        self.__device_data_refresh_interval = int(device_refresh_interval)

    # =================================================================================================================

    def connect(self,
        backend: Transport,                          # Backend connection transport to the DSP itself (e.g., SSH, Telnet)
        skip_block_types: list[Block]|None = None,   # Block types to block from loading (can speed up initialization by disabling unused blocks)
    ) -> None:
        """
        Connect to the DSP
        """
        assert not self.__connected.is_set(), "Already connected"
        startup_time = time.perf_counter()

        # Start transport channel
        self.__transport = backend
        self.__transport.start(exit_event = self.__exit, connected_flag = self.__connected)

        # Wait for channel to start
        self.__logger.info("waiting for TTP channel")
        while not self.__connected.is_set():
            time.sleep(0.01)

        # Start listen loop
        self.__rx_thread_handle = Thread(target = self.__rx_loop)
        self.__rx_thread_handle.start()

        # Any blocks that we wouldn't want to load?
        self.__skip_block_types = []
        if skip_block_types is not None and type(skip_block_types) == list:
            self.__skip_block_types = skip_block_types
            self.__logger.info(f"Will skip loading {len(self.__skip_block_types)} DSP block type(s)")
            self.__logger.debug(f"Skip load: {self.__skip_block_types}")

        # Outgoing command queue, this is used so each block can append to it with synchronous
        # DSP command strings it wanted to process, which the main thread (us!) will process
        # in the order in which it was received, to prevent concurrent synchronous access
        self.__command_queue = queue.Queue()

        # Mailbox for synchronous commands executed in the main thread
        self.__sync_cmd_mailbox = None

        # Start thread to process synchronous command requests in local queue
        # after this is started, __sync_command() can and should be used for every
        # TTP command that is to be sent out to the DSP
        self.__sync_cmd_thread_handle = Thread(target = self.__sync_cmd_process_loop)
        self.__sync_cmd_thread_handle.start()

        # Session baseline setup
        self.__sync_command("SESSION set verbose true")
        self.__sync_command("SESSION set detailedResponse false")

        # Basic device statistics
        self.hostname = str(self.__sync_command("DEVICE get hostname").value)
        self.software_version = str(self.__sync_command("DEVICE get version").value)
        self.serial_number = str(self.__sync_command("DEVICE get serialNumber").value)

        # Query DSP aliases/blocks
        self.__dsp_aliases = list(self.__sync_command("SESSION get aliases").value)

        # Information logging for device parameters
        self.__logger.info(f"Connected to '{self.hostname}' (S/N {self.serial_number}; software version {self.software_version}; {len(self.__dsp_aliases)} DSP aliases)")

        # Discovered servers (in configuration)
        self.discovered_servers = self.__sync_command("DEVICE get discoveredServers").value

        # Get DSP block map, either from block map file (if loadable and correct for our DSP) or live query
        self.__block_map = self.__getDSPBlockMap()

        # Subscriptions
        self.__subscriptions = {}

        # Then, for each object in the block map, we initialize it
        self.__logger.info("initializing blocks, please wait")
        self.blocks = {}
        for block_id, block in self.__block_map.items():

            # Get block type
            block_type = block["type"]

            # Is this block type even supported?
            try:

                # Yes, we get a module handle for that block type
                block_module = importlib.import_module(f"pytesira.block.{block_type}", "pytesira")
                block_module_version = str(getattr(block_module, f"{block_type}").VERSION)

                # Do we want to load this block?
                if getattr(block_module, f"{block_type}") in self.__skip_block_types:
                    self.__logger.info(f"'{block_id}' load skipped ({block_type} excluded by user preference)")
                    self.__logger.debug(f"skip module load: {block_id} ({block_type}/{block_module}) (user preference)")
                    continue

                # Pre-mapped "attribute map / initialization helper" to pass along to module initialization?
                block_module_init_helper = None
                if "attributes" in block and type(block["attributes"]) == dict and len(block["attributes"]) >= 1:
                    try:
                        assert block["attributes"]["version"] == block_module_version, "block module version mismatch"
                        assert type(block["attributes"]["helper"]) == dict, "invalid block module map type"
                        block_module_init_helper = block["attributes"]["helper"]

                        # Empty helpers shouldn't be loaded
                        if len(block_module_init_helper) <= 0:
                            block_module_init_helper = None

                    except Exception as e:
                        self.__logger.debug(f"block {block_id} ({block_type}) attribute helper cannot be loaded: {e}")

                # Then, we initialize the module
                self.blocks[block_id] = getattr(block_module, f"{block_type}")(
                    block_id = block_id,                            # block ID on Tesira
                    exit_flag = self.__exit,                        # exit flag to stop the block's threads (sync'd with everything else)
                    connected_flag = self.__connected,              # connected flag (module can refuse to allow access if this is not set)
                    command_queue = self.__command_queue,           # command queue (to run synchronous commands and get results)
                    subscriptions = self.__subscriptions,           # subscriptions container (for routing purposes)
                    init_helper = block_module_init_helper,         # initialization helper, to be used however the module wants
                )

                # At this point we should have initialization helper dict, so we update the block map with that
                self.__block_map[block_id]["attributes"] = self.blocks[block_id].export_init_helper()

                # Set up subscriptions for the module
                self.blocks[block_id].subscribe()

            # No... this module doesn't exist (not supported), so we don't load that
            except ModuleNotFoundError:
                self.__logger.debug(f"Unsupported DSP block type '{block_type}': {block_id}")

        # Start device attribute update loop
        self.__device_data_refresh_loop_handle = Thread(target = self.__device_data_refresh_loop)
        self.__device_data_refresh_loop_handle.start()

        # Now we're done - DSP object should now be ready to use!
        started_in = time.perf_counter() - startup_time
        self.ready = True
        self.__logger.info(f"DSP ready (initialization took {round(started_in, 3)} seconds)")

    # =================================================================================================================

    def close(self) -> None:
        """
        Property terminate connection to the DSP
        """

        # No longer ready
        self.ready = False

        # Set exit flag (should terminate everything)
        self.__exit.set()

        # Wait for threads to terminate
        self.__rx_thread_handle.join()
        self.__sync_cmd_thread_handle.join()
        self.__device_data_refresh_loop_handle.join()

        # Done
        return

    # =================================================================================================================

    def save_block_map(self, output : str) -> None:
        """
        Save active DSP block map to a file
        """
        output = str(output).strip()
        assert output != "", "Output must be specified"

        # Enforce file extension to prevent confusion and inadvertent inclusion in repository
        if not output.endswith(".bmap"):
            output = f"{output}.bmap"

        output = os.path.realpath(str(output))
        assert self.__block_map, "No active DSP block map"
        with open(output, "w") as f:
            json.dump({
                "hostname" : self.hostname,
                "aliases" : sorted(self.__dsp_aliases),
                "blocks" : self.__block_map,
                "pytesira_version" : self.__version
            }, f, indent = 4)
        self.__logger.info(f"DSP block map saved: {output}")

    # =================================================================================================================

    def device_command(self, command : str) -> TTPResponse:
        """
        Send raw command to device
        """
        assert self.ready, "DSP not ready"
        return self.__sync_command(command)

    # =================================================================================================================

    def start_system_audio(self) -> TTPResponse:
        """
        Send system audio start command to device
        """
        return self.device_command("DEVICE startAudio")

    def stop_system_audio(self) -> TTPResponse:
        """
        Send system audio stop command to device
        """
        return self.device_command("DEVICE stopAudio")

    def reboot(self) -> TTPResponse:
        """
        Send reboot (restart) command to device
        """
        return self.device_command("DEVICE reboot")

    # =================================================================================================================

    def __getDSPBlockMap(self) -> dict:
        """
        Get DSP block map, either from the block map file (if one was specified at time of object creation),
        or live query (if none is provided, or there's an error, or the provided block map doesn't line up with
        DSP attributes we've seen so far)

        MUST be called after we know device hostname and has queried for device aliases,
        otherwise this will fail!
        """

        # Return block map
        rtn_map = {}

        # Are we able to load the block map?
        block_map_loaded = False

        # Try to load block map, if one is specified
        if self.__block_map is not None:
            try:
                self.__block_map = os.path.realpath(self.__block_map)
                with open(self.__block_map, "r") as f:
                    bm = json.load(f)

                    assert bm["hostname"] == self.hostname, "hostname mismatch"
                    assert sorted(bm["aliases"]) == sorted(self.__dsp_aliases), "aliases mismatch"
                    assert bm["pytesira_version"] == self.__version, "PyTesira version mismatch"

                    rtn_map = bm["blocks"]
                    block_map_loaded = True
                    self.__logger.info(f"loaded DSP block map from {self.__block_map}")

            except Exception as e:
                self.__logger.warning(f"could not load DSP block map: {e}")

        # If block map isn't yet loaded, there's probably an error in the process somewhere,
        # so we proceed with live query to get latest info
        if not block_map_loaded:
            self.__logger.info("starting DSP block map query")

            # First query for DSP blocks
            for i, block_id in enumerate(self.__dsp_aliases):

                # No need to process device handle
                if block_id == "device":
                    continue

                # Intentionally make an invalid query such that we get the handler response
                # which will specify what type of block this is
                block_type_query_response = self.__sync_command(f'{block_id} get BLOCKTYPE')
                assert block_type_query_response.type == TTPResponseType.CMD_ERROR, "block type query: invalid response type"

                if "::Attributes" not in block_type_query_response.value:
                    # DSP block with no attribute handle... shouldn't happen, 
                    # but if it does we just skip it
                    continue

                # Figure out block interface type, take stuff after last space
                resp = block_type_query_response.value.split(" ")[-1].strip()
                block_type = str(resp).replace("Interface::Attributes", "").strip()
                rtn_map[block_id] = {
                    "type" : str(block_type),       # block type, very important
                    "attributes" : None             # no attributes yet (this will trigger attribute query on supported blocks)
                }
                self.__logger.debug(f"(DSP block discovery: {i + 1}/{len(self.__dsp_aliases)}) {block_id} -> {block_type}")

            self.__logger.info(f"found {len(rtn_map)} DSP blocks")

        # Now we return the block map, and we're done
        return rtn_map

    # =================================================================================================================

    def __sync_cmd_process_loop(self) -> None:
        """
        Synchronous command worker loop. This processes the synchronous command queue,
        which the block objects use to run one-off commands to the DSP and get results.
        """
        self.__logger.info("starting synchronous command processor loop")
        while not self.__exit.is_set():

            # Grab command item from the queue (and expand the tuple)
            try:
                handle, command = self.__command_queue.get(timeout = 0.5)
            except queue.Empty:
                # We didn't get anything, let's just move on to another iteration
                # (by doing so, this evaluates the exit flag at least once every
                #  0.5 seconds, allowing us to kill the thread if needed)
                continue

            # Run the command and return to the correct handle's callback
            # this should be the ONLY place we call transport_send_and_wait!
            response = self.__transport_send_and_wait(command)

            if handle == self:
                # Hey, this is called by us directly, we don't need
                # to callback for this, just write data to local synchronous
                # command mailbox and we'll be done:
                self.__sync_cmd_mailbox = response
                self.__logger.debug("sync command response delivery: main loop sync_cmd_mailbox")
            else:
                # This is called from elsewhere, so we need to invoke
                # the corresponding block's callback:
                handle._sync_command_callback(data = response)
                self.__logger.debug(f"sync command response delivery: callback to {handle}")

            # Notify queue of a completed task
            self.__command_queue.task_done()

        # If we're here, we're exiting
        self.__logger.debug("synchronous command processor loop terminated")
        return

    # =================================================================================================================

    def __device_data_refresh_loop(self) -> None:
        """
        Device data refresh loop. This constantly queries the device for attributes that cannot
        be subscribed to, but nevertheless would be of interest to PyTesira users (e.g., active alarms)

        We simply poll the device (with a configurable interval) for this...
        """
        self.__logger.info("starting device data refresh loop")
        while not self.__exit.is_set():

            # Query active faults
            self.faults = self.__sync_command("DEVICE get activeFaultList").value[0]

            # Query network status
            self.network = self.__sync_command("DEVICE get networkStatus").value

            # For blocks that do support subscription, re-validate the subscriptions to make sure we're
            # still subscribed, even after a system configuration change:
            # (see: https://tesira-help.biamp.com/System_Control/Tesira_Text_Protocol/Subscriptions.htm)
            for block_id in self.blocks.keys():
                if hasattr(self.blocks[block_id], "_register_base_subscriptions"):
                    self.blocks[block_id]._register_base_subscriptions()

            # Throttle query to the interval we're configured for
            # (typicaly 5 seconds, but can be configured to be less or more as needed)
            time.sleep(self.__device_data_refresh_interval)

        # Exit
        self.__logger.debug("device data refresh loop terminated")
        return

    # =================================================================================================================

    def __sync_command(self, command : str, timeout : float = 3.0) -> TTPResponse:
        """
        Command send-and-wait function that uses the main command queue instead of talking
        to the transport channel directly. This should be used after __sync_cmd_process_loop() has
        started running, as it guarantees that only one synchronous command is ever executed at
        a time, preventing conflicts
        """

        # Clean out mailbox
        self.__sync_cmd_mailbox = None

        # Queue command
        self.__command_queue.put((self, command))
        cmd_queued = time.perf_counter()

        # Now we wait until we either get data or timeout occurs, whichever comes first
        while time.perf_counter() - cmd_queued < timeout:

            # Let other tasks run
            time.sleep(0.01)

            # Did we get something?
            if self.__sync_cmd_mailbox:
                cmd_response = self.__sync_cmd_mailbox
                self.__sync_cmd_mailbox = None
                return cmd_response

        # If we're here, we got... nothing
        self.__sync_cmd_mailbox = None
        raise Exception(f"Command timeout: {command}")

    # =================================================================================================================

    def __rx_loop(self) -> None:
        """
        Receive loop, to be run as a thread. Constantly monitors and receives stuff
        from the backend TTP connection.

        Also handles subscription routing (to the right DSP block handler) and
        mailboxing for synchronous (non-subscription) commands

        """
        self.__logger.info("starting TTP receiver loop")
        while not self.__exit.is_set():

            # Let backend I/O run
            time.sleep(0.00001)

            rx = self.__transport_rx()
            if rx:
                # Get something, let's try to parse that
                decoded = TTPResponse(rx)

                # Subscription?
                if decoded.type == TTPResponseType.SUBSCRIPTION:
                    self.__logger.debug(f"rx (sub): {decoded}")

                    # Where did this come from?
                    subscriber = self.__subscriptions[decoded.publish_token]
                    if not subscriber:
                        self.__logger.error(f"subscription callback for invalid subscriber: {decoded.publish_token}")
                    else:
                        # OK, we have a subscriber, let's call their callback so the block code
                        # can figure out what to do with that data
                        sub_handle, _, _, _ = subscriber
                        sub_handle.subscription_callback(decoded)

                else:
                    self.__logger.debug(f"rx (res): {decoded}")
                    self.__rx_cmd_mailbox = decoded                    

        # If we're here, we're exiting
        self.__logger.debug("rx loop terminated")
        return

    # =================================================================================================================

    def __transport_send_and_wait(self, command : str, timeout : float = 3) -> TTPResponse:
        """
        Send TSP command to device and wait for response (with a timeout limit)
        Note: only ONE command should be sent at a time, rapid-fire sends may
              cause the mailbox to get and return wrong data!
        """

        # Send command and mark time sent
        self.__transport.send(command)
        cmd_sent = time.perf_counter()

        # Now we wait until we either get data or timeout occurs, whichever comes first
        while time.perf_counter() - cmd_sent < timeout:

            # Let other tasks run
            time.sleep(0.01)

            # Did we get something?
            if self.__rx_cmd_mailbox:
                cmd_response = self.__rx_cmd_mailbox
                self.__rx_cmd_mailbox = None
                return cmd_response

        # If we're here, we got... nothing
        self.__rx_cmd_mailbox = None
        raise Exception(f"Command timeout: {command}")

    # =================================================================================================================

    def __transport_rx(self) -> str | None:
        """
        Transport receive handler. Connects to the backend transport stream, then tries
        to extract one newline-delimited line from that stream buffer. Call this multiple
        times to get everything

        Note: before calling this function (repeatedly if needed), be sure to do
        a time.sleep(0.00001), so the backend I/O threads (e.g., Paramiko) gets a
        chance to run and return data!
        """

        # Fill buffer from stream
        while self.__transport.recv_ready:
            self.__rx_buffer += str(self.__transport.recv(self.__transport.read_buffer_size))

        # If there us a newline, response has ended. We go through lines until we get something 
        # with either "+OK", "-ERR", or "!" prefixes, those are valid lines. We don't return
        # invalid lines otherwise.
        #
        # Note: we use a while loop here, so this function will run until it either finds a
        # valid line, or it runs out of newlines, whichever comes first
        while "\n" in self.__rx_buffer:
            newline_position = self.__rx_buffer.find("\n")
            line = str(self.__rx_buffer[:newline_position]).strip()
            self.__rx_buffer = self.__rx_buffer[newline_position + 1:]

            if line != "" and (line.startswith("+OK") or line.startswith("-ERR") or line.startswith("!")):
                # Valid line
                return line

        # Out of newlines, so just return nothing
        return None
