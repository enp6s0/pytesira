#!/usr/bin/env python3
from pytesira.transport.transport import Transport
from threading import Thread, Event
import paramiko
import logging
import traceback
import time

class SSH(Transport):
    """
    PyTesira SSH transport using Paramiko
    """

    def __init__(self,
        hostname: str,                      # Device hostname/IP
        username: str,                      # SSH username
        password: str,                      # SSH password
        port: int = 22,                     # SSH port
        host_key_check: bool = True,        # Enable SSH host key checking?
        connection_timeout: int = 5,        # SSH connection timeout (seconds)
    ) -> None:

        # Base class initialization
        super().__init__()

        # Logger
        self.__logger = logging.getLogger(__name__)

        # Save connection parameters
        self.__hostname = str(hostname)
        self.__username = str(username)
        self.__password = str(password)
        self.__port = int(port)
        self.__host_key_check = bool(host_key_check)
        self.__connection_timeout = int(connection_timeout)
        assert 1 <= self.__port <= 65535, f"Invalid SSH port {self.__port}"
        assert 1 <= self.__connection_timeout, f"Invalid connection timeout {self.__connection_timeout}"

        # Actual connection object (Paramiko channel)
        self.__channel = None

        # Stop Paramiko from flooding the terminal with its debug messages
        # (we typically don't have to debug that deep...)
        logging.getLogger("paramiko.transport").setLevel(logging.INFO)

    # =================================================================================================================

    def start(self,
        exit_event: Event,                  # Core exit event (terminates transport channel too)
        connected_flag: Event,              # Connected flag, lets us tell everyone else the connection status
    ) -> None:
        """
        Actually start the backend transport
        """

        # Save handles to those important event flags!
        self.__exit = exit_event
        self.__connected = connected_flag

        # Start transport thread
        self.__thread = Thread(target = self.__mainThread)
        self.__thread.start()

    # =================================================================================================================

    def assert_device_ready(f):
        """
        Decorator for calls that requires the device to be ready
        """

        def wrapper(self, *args, **kwargs):
            assert self.__channel != None, "Channel not initialized"
            assert self.__channel.active, "Device not ready"
            return f(self, *args, **kwargs)

        return wrapper

    # =================================================================================================================

    @property
    @assert_device_ready
    def recv_ready(self) -> bool:
        """
        Data ready in read buffer?
        """
        return self.__channel.recv_ready()

    # =================================================================================================================

    @assert_device_ready
    def recv(self, buffer_size : int) -> str:
        """
        Read data from RX buffer
        """
        return str(self.__channel.recv(buffer_size).decode())

    # =================================================================================================================

    @assert_device_ready
    def send(self, data : str) -> None:
        """
        Send data to device
        """
        self.__channel.send(f"{data}\n")

    # =================================================================================================================

    def __mainThread(self) -> None:
        """
        Main thread (runs forever until we're told to exit)
        """
        while not self.__exit.is_set():

            try:

                # If channel isn't connected, we connect
                if (not self.__channel) or (self.__channel is not None and self.__channel.closed):
                    self.__connect()

                # Now the thread doesn't have to do anything, since Paramiko will take over
                # we just sleep and stay out of the way
                time.sleep(0.5)

            except Exception as e:
                # Oh no, something bad happened. We log that, and wait for a few seconds
                # before trying to connect again
                self.__connected.clear()
                self.__logger.error(f"Thread exception: {e} ({traceback.format_exc()})")
                time.sleep(2)

        # If we're here, it means the global exit flag has been set,
        # and it's our cue to terminate, so we first close the backend channel if possible:
        if self.__channel is not None:
            self.__channel.close()

        # Then we exit
        return

    # =================================================================================================================

    def __connect(self) -> None:
        """
        Connect (or re-connect) to the SSH channel
        """

        # If there's a lingering session, we'll try to close that if possible. If not - not a big deal:
        try:
            self.__channel.close()
            self.__logger.debug(f"old SSH channel closed")
        except Exception as e:
            pass

        # Start from disconnected state
        self.__connected.clear()

        # Session and channel (Paramiko shell session)
        self.__session = paramiko.SSHClient()    
        self.__session.set_missing_host_key_policy(paramiko.RejectPolicy() if self.__host_key_check else paramiko.WarningPolicy())
        self.__session.connect(
            self.__hostname, 
            self.__port, 
            username = self.__username, 
            password = self.__password, 
            timeout = self.__connection_timeout
        )
        self.__channel = self.__session.invoke_shell()
        self.__logger.debug(f"channel started")

        # Try to connect and wait until we either get the welcome text, or reached timeout
        # limitations, whichever one comes first
        conn_init_time = time.perf_counter()
        welcomed = False
        self.__logger.info(f"waiting for session establishment")
        while time.perf_counter() - conn_init_time < self.__connection_timeout:
            if self.__channel.active:
                time.sleep(0.01)
                if self.__channel.recv_ready():
                    received = self.__channel.recv(self.read_buffer_size).decode()
                    if self.ttp_welcome in received:
                        welcomed = True
                        break
        
        # If there's anything left in the buffer, clear it out (for good measure)
        while self.__channel.recv_ready():
            _ = self.__channel.recv(self.read_buffer_size).decode()

        if not welcomed:
            # Uh oh, we didn't get a valid response from the DSP
            raise Exception(f"timeout waiting for session establishment")
            self.__connected.clear()
        else:
            # Connection OK :)
            self.__logger.info(f"Tesira text protocol session established ({round(time.perf_counter() - conn_init_time, 3)} sec)")
            self.__connected.set()