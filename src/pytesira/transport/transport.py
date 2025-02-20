#!/usr/bin/env python3
from threading import Event


class Transport:
    """
    PyTesira transport base class

    This acts as a starting point for transport-type-specific channel implementations (e.g., SSH or Serial)
    which has their own methods and requirements. Note that authentication schemes are implemented directly
    in the subclass (since this can be very different from method to method)
    """

    def __init__(self):
        """
        Initialize base transport class
        """

        # Read buffer size (bytes)
        self.read_buffer_size = 4096

        # "Connected" text that confirms transport is ready
        self.ttp_welcome = "Welcome to the Tesira Text Protocol Server..." 

    def start(self,
        exit_event: Event,         # Core exit event (terminates transport channel too)
        connected_flag: Event,     # Connected flag, lets us tell everyone else the connection status
    ):
        """
        Actually start the backend transport. This will be called by the DSP class and is not
        intended to be called directly elsewhere
        """
        raise NotImplementedError

    @property
    def recv_ready(self) -> bool:
        """
        Data ready in read buffer?
        """
        raise NotImplementedError

    def recv(self, buffer_size : int) -> str:
        """
        Read data from RX buffer
        """
        raise NotImplementedError

    def send(self, data : str) -> None:
        """
        Send data to device
        """
        raise NotImplementedError
