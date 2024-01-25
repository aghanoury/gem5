from m5.objects.ClockedObject import ClockedObject
from m5.params import *
from m5.SimObject import SimObject


class ChLink(ClockedObject):
    type = "ChLink"
    cxx_header = "rowhammer/src/ch_link.hh"
    cxx_class = "gem5::ChLink"

    cpu_side = ResponsePort("CPU side port, receives requests")

    mem_side = RequestPort("Memory side port, sends requests")

    latency = Param.Cycles(1, "Cycles taken on a hit or to resolve a miss")
