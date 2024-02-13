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
parser.add_argument(
    "--binary",
    help="binary to run",
    default="tests/test-progs/hello/bin/x86/linux/hello",
)
parser.add_argument(
    "--options",
    help="options to pass to the binary",
    default="",
)
parser.add_argument(
    "--sm_cache_hitrate",
    help="Hitrate of the secure module cache. Use 0 to disable the cache",
    default=0.5,
)
parser.add_argument(
    "--fast-forward",
    help="Number of instructions to fast forward before switching",
    default=None,
    type=int,
)
parser.add_argument(
    "--max-instructions",
    help="Maximum number of instructions to execute",
    default=None,
    type=int,
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
system.mem_ranges = [AddrRange("4GB")]  # Create an address range


switch_cpu = None
# do we need a fast forward CPU?
if args.fast_forward:
    system.cpu = [AtomicSimpleCPU()]
    switch_cpu = DerivO3CPU()
    system.cpu[0].max_insts_any_thread = args.fast_forward
    system.mem_mode = "atomic"

    if args.max_instructions:
        switch_cpu.max_insts_any_thread = args.max_instructions
else:
    system.cpu[0] = DerivO3CPU()
    switch_cpu = None
    if args.max_instructions:
        system.cpu[0].max_insts_any_thread = args.max_instructions

system.cpu[0].cpu_id = 0


# ADD CACHES
# L1 CACHE OPTS
opts = {}
opts["assoc"] = 8
opts["size"] = "16kB"

# opts["prefetcher"] = None
# system.main_cpu.addPrivateSplitL1Caches(dcache, icache)

system.membus = SystemXBar()

if args.cache:

    icache = L1_ICache(**opts)
    dcache = L1_DCache(**opts)
    iwalkcache = PageTableWalkerCache()
    dwalkcache = PageTableWalkerCache()
    
    system.cpu[0].addPrivateSplitL1Caches(
        icache, dcache, iwalkcache, dwalkcache
    )

    # system.cpu[0].icache.cpu_side = system.cpu[0].icache_port
    # system.cpu[0].dcache.cpu_side = system.cpu[0].dcache_port

    # system.cpu[0].icache.mem_side = system.membus.cpu_side_ports
    # system.cpu[0].dcache.mem_side = system.membus.cpu_side_ports

else:
    system.cpu[0].icache_port = system.membus.cpu_side_ports
    system.cpu[0].dcache_port = system.membus.cpu_side_ports


# create the interrupt controller for the system.cpu[0] and connect to the membus
system.cpu[0].createInterruptController()
system.cpu[0].interrupts[0].pio = system.membus.mem_side_ports
system.cpu[0].interrupts[0].int_requestor = system.membus.cpu_side_ports
system.cpu[0].interrupts[0].int_responder = system.membus.mem_side_ports


# Create a DDR3 memory controller and connect it to the membus
system.mem_ctrl = MemCtrl()
# system.mem_ctrl.dram = DDR3_1600_8x8()
system.mem_ctrl.dram = DDR4_2400_16x4()
system.mem_ctrl.dram.range = system.mem_ranges[0]

# system.mem_ctrl.port = system.chlink.mem_side

# Create the link object
args.mem_pipe = False  # always set to true for now
# args.mem_pipe = False # or set to false to skip this stuff for now
if args.mem_pipe:
    system.mem_pipe = MemPipe()
    # Create a memory bus, a coherent crossbar, in this case
    system.membus.mem_side_ports = system.mem_pipe.cpu_side
    system.mem_ctrl.port = system.mem_pipe.mem_side
else:
    system.membus.mem_side_ports = system.mem_ctrl.port


# system.switch_cpu = switch_cpu




# Create a process for a simple "Hello World" application
process = Process()
# Set the command
# grab the specific path to the binary
binpath = args.binary
options = args.options

# thispath = os.path.dirname(os.path.realpath(__file__))
# binpath = os.path.join(
#     # thispath, "../../", "tests/test-progs/hello/bin/x86/linux/hello"
#     thispath, "../../", "microbench/mm"
# )
# cmd is a list which begins with the executable (like argv)
process.cmd = [binpath, options]
# Set the cpu to use the process as its workload and create thread contexts
system.cpu[0].workload = process
system.cpu[0].createThreads()

system.workload = SEWorkload.init_compatible(binpath)

# configure the rest of the system with the switch cpu
# pdb.set_trace()
if switch_cpu:
    switch_cpu.system = system
    switch_cpu.workload = system.cpu[0].workload
    switch_cpu.clk_domain = system.cpu[0].clk_domain
    switch_cpu.progress_interval = system.cpu[0].progress_interval
    switch_cpu.isa = system.cpu[0].isa
    switch_cpu.switched_out = True
    switch_cpu.cpu_id = 0

    # switch_cpu.
    # simulation period
    # Add checker cpu if selected
    system.switch_cpus = [switch_cpu]
    switch_cpu.createThreads()


# set up the root SimObject and start the simulation
root = Root(full_system=False, system=system)
# instantiate all of the objects we've created above
m5.instantiate()
pdb.set_trace()

print(f"Beginning simulation!")
exit_event = m5.simulate()
m5.stats.reset()
print("BEGIN REAL SIM")
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
m5.switchCpus(system, [(system.cpu[0], switch_cpu)])
exit_event = m5.simulate(1000000000000000000 - m5.curTick())
