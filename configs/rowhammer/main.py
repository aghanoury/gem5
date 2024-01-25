""" This file creates a barebones system and executes 'hello', a simple Hello
World application. Adds a simple memobj between the CPU and the membus.

This config file assumes that the x86 ISA was built.

Author: Pooya Aghanoury
"""

import argparse
import os
import pdb
import sys

import m5
from m5.defines import buildEnv
from m5.objects import *
from m5.params import NULL
from m5.util import (
    addToPath,
    fatal,
    warn,
)

from gem5.isas import ISA

addToPath("../")
from common import (
    CacheConfig,
    CpuConfig,
    MemConfig,
    ObjectList,
    Options,
    Simulation,
)
from common.Caches import *

# pdb.set_trace()
parser = argparse.ArgumentParser()
# Options.addCommonOptions(parser)
# Options.addSEOptions(parser)

# add argument options
parser.add_argument(
    "--cache", help="type of cache to run", action="store_true"
)
parser.add_argument(
    "--chlink",
    help="add chiplet link between membus and main memory",
    action="store_true",
)

args = parser.parse_args()

# INIT SYSTEM
system = System()

# warn("Using default option set from old se.py, but we're not parsing for all"
#      " of those options. e.g. specify --cpu-type to set the CPU type won't work")

# SET CLK DOMAIN
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = "1GHz"
system.clk_domain.voltage_domain = VoltageDomain()

# SYSTEM TYPE
system.mem_mode = "timing"  # Use timing accesses
# TODO: update addr range
system.mem_ranges = [AddrRange("512MB")]  # Create an address range

# DECLARE THE CPU
system.cpu = X86TimingSimpleCPU()
# system.cpu = O3CPU() # use the out-of-order model

# ADD CACHES
# L1 CACHE OPTS
opts = {}
opts["assoc"] = 8
opts["size"] = "1kB"

# opts["prefetcher"] = None
# system.cpu.addPrivateSplitL1Caches(dcache, icache)

system.membus = SystemXBar()

if args.cache:
    system.cpu.icache = L1_ICache(**opts)
    system.cpu.dcache = L1_DCache(**opts)

    system.cpu.icache.cpu_side = system.cpu.icache_port
    system.cpu.dcache.cpu_side = system.cpu.dcache_port

    system.cpu.icache.mem_side = system.membus.cpu_side_ports
    system.cpu.dcache.mem_side = system.membus.cpu_side_ports

else:
    system.cpu.icache_port = system.membus.cpu_side_ports
    system.cpu.dcache_port = system.membus.cpu_side_ports


# create the interrupt controller for the CPU and connect to the membus
system.cpu.createInterruptController()
system.cpu.interrupts[0].pio = system.membus.mem_side_ports
system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports


# Create a DDR3 memory controller and connect it to the membus
system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR3_1600_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]

# system.mem_ctrl.port = system.chlink.mem_side

# Create the link object
if args.chlink:
    system.chlink = ChLink(latency=1)
    # Create a memory bus, a coherent crossbar, in this case
    system.membus.mem_side_ports = system.chlink.cpu_side
    system.mem_ctrl.port = system.chlink.mem_side
else:
    system.membus.mem_side_ports = system.mem_ctrl.port


# Create a process for a simple "Hello World" application
process = Process()
# Set the command
# grab the specific path to the binary
thispath = os.path.dirname(os.path.realpath(__file__))
binpath = os.path.join(
    thispath, "../../", "tests/test-progs/hello/bin/x86/linux/hello"
)
# cmd is a list which begins with the executable (like argv)
process.cmd = [binpath]
# Set the cpu to use the process as its workload and create thread contexts
system.cpu.workload = process
system.cpu.createThreads()

system.workload = SEWorkload.init_compatible(binpath)

# set up the root SimObject and start the simulation
root = Root(full_system=False, system=system)
# instantiate all of the objects we've created above
m5.instantiate()

print(f"Beginning simulation!")
exit_event = m5.simulate()
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
