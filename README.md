# PyTesira
Control your Biamp Tesira DSPs directly from Python!

*work in progress!* stuff might break, please don't rely on this for anything critical... yet

> Obligatory disclaimer: this is an unofficial project which is not in any way affiliated with, or endorsed by, Biamp Systems

## Architecture
PyTesira adopts a modular design where the `DSP` class (`src/pytesira/dsp.py`) acts as the hub for everything.

![PyTesira architecture](./docs/img/pytesira-architecture.png)

A `Transport` channel (such as `SSH`) is used for connection to the Tesira DSP device (using the Tesira Text Protocol). 
Currently, `SSH` is the only supported transport (other transports are planned - feel free to submit a pull request also!).

Upon connection, PyTesira tries to create a *block map* of available DSP blocks. For each supported block type, it also
attempts to query that block's *attributes* (e.g., number of channels and their labels). This can be exported and re-imported
to shorten startup time (querying is slow - especially on a complex setup with many nodes).

A `Block` represents a type of DSP block available (e.g., `LevelControl` or `SourceSelector`). It handles everything that
has to do with that specific DSP block - setting up subscriptions, updating state, handling update requests, and more.

## Supported blocks and features

* `LevelControl`     : read/write mute status, read/write levels
* `MuteControl`      : read/write mute status
* `SourceSelector`   : read/write mute status (output), set source and output levels, read levels, read and select active source
* `DanteInput`       : read/write mute status, read/write levels, read/write invert setting, read/write fault-on-inactive setting
* `DanteOutput`      : read/write mute status, read/write levels, read/write invert setting, read/write fault-on-inactive setting
* `AudioOutput`      : read/write mute status, read/write levels, read/write invert setting
* `GraphicEqualizer` : read/write global bypass, read/write band bypass, read/write band gain
* `Ducker`           : read/write most attributes (except logic configuration)
* `PassFilter`       : read all attributes, write cutoff frequency
* `UsbInput`         : read connected/streaming states, read/write DSP side level/mute, read host side mute/level
* `UsbOutput`        : read connected/streaming states, read/write DSP side level/mute, read host side mute/level
* `NoiseGenerator`   : read/write level, read/write noise type (`white`/`pink`), read/write mute status

## Supported device-level features

* Start/stop system audio (`dsp.start_system_audio()` and `dsp.stop_system_audio()`)
* Reboot device (`dsp.reboot()`)
* Execute arbitrary commands (`dsp.device_command(command : str)`)

## Tested on

* TesiraFORTÉ DAN (software version `4.11.1.2`)

## How to use

Install latest version from the [PyPI release](https://pypi.org/project/pytesira/)
```sh
pip3 install pytesira
```

Simple usage example:
```py
from pytesira.dsp import DSP
from pytesira.transport.ssh import SSH
from pytesira.block.GraphicEqualizer import GraphicEqualizer

# Connect to the device, but skip initializing GraphicEqualizer blocks
# (as that's VERY slow - only enable if you really need that support!)
device = DSP()
device.connect(backend = SSH(
                        hostname = "tesira.device.lan",
                        username = "admin", 
                        password = "forgetme",
                        host_key_check = False # Bad option! Bad! Change this in production!
                ),
                skip_block_types = [
                    GraphicEqualizer
                ])

# Note: at this point, we need to wait for the DSP to be fully connected/ready. 
# To do so, we can simply check for the boolean flag `device.ready`
while not device.ready:
    pass

# Save block map, which can then be loaded by specifying `block_map`
# next time when we load the class like so: DSP(block_map = "dsp_test.bmap")
device.save_block_map(output = "dsp_test.bmap")

# Get system info
print(device.hostname)
print(device.serial_number)
print(device.software_version)

# Get faults and network status
print(device.faults)
print(device.network)

# Assuming a 2-channel level control block named `LevelTest`,
# we first look at its channel status
print(device.blocks["LevelTest"].channels)

# Get and change level state for channel 2
print(device.blocks["LevelTest"].channels[2].level)
device.blocks["LevelTest"].channels[2].level = -12.0

# Same thing with mute states
print(device.blocks["LevelTest"].channels[2].muted)
device.blocks["LevelTest"].channels[2].muted = True

# Get information on a source selector block named `SourceTest`
# (this includes all channels and their levels, as well as currently selected source)
print(device.blocks["SourceTest"].sources)

# Get currently selected source and select a new one
# (source 0 = unselect everything)
print(device.blocks["SourceTest"].selected_source)
device.blocks["SourceTest"].selected_source = 4

# Get and adjust cutoff frequency on a pass filter block
print(device.blocks["PassFilterTest"].cutoff_frequency)
device.blocks["PassFilterTest"].cutoff_frequency = 60.0

# We can also bypass pass filters as needed
device.blocks["PassFilterTest"].bypass = True

# DSP blocks also come with callbacks! Here we'll demonstrate a simple callback,
# which will get called whenever a value on the block changes (the entire block object
# is passed back to us as a parameter):
def test_cb(block):
    print(type(block), block.channels)

# Note that specifying a key is optional, but if set, allows for the callback
# to be dynamically unregistered with unregister_callback() - or replaced by
# simply registering another callback with the same key!
device.blocks["LevelTest"].register_callback(callback = test_cb, key = "test_callback")

```