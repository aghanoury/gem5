from m5.objects.ClockedObject import ClockedObject
from m5.params import *
from m5.SimObject import SimObject


class MemPipe(ClockedObject):
    type = "MemPipe"
    cxx_header = "mem_pipe/src/mem_pipe.hh"
    cxx_class = "gem5::MemPipe"

    cpu_side = ResponsePort("CPU side port, receives requests")
    mem_side = RequestPort("Memory side port, sends requests")