#!/usr/bin/env python3
#
# Run this with python3 -i to get interactive debug shell!
#
from pytesira.dsp import DSP
from pytesira.transport.ssh import SSH
from pytesira.block.GraphicEqualizer import GraphicEqualizer

import yaml
import logging
import sys

# Logging configuration
debug = False
logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)
try:
    if sys.argv[1] == "debug":
        logging.getLogger().setLevel(logging.DEBUG)
        debug = True
except Exception:
    pass

with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

device = DSP(block_map="dsp_test.bmap")
device.connect(backend=SSH(
                        hostname=config["connection"]["host"],
                        username=config["connection"]["username"], 
                        password=config["connection"]["password"],
                        host_key_check=False
                ), skip_block_types=[
                    GraphicEqualizer
                ])
device.save_block_map(output="dsp_test.bmap")
