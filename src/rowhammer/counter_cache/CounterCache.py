from m5.objects.ClockedObject import ClockedObject
from m5.params import *
from m5.SimObject import SimObject


class CounterCache(ClockedObject):
    type = "CounterCache"
    cxx_header = "rowhammer/counter_cache/counter_cache.hh"
    cxx_class = "gem5::CounterCache"

    cpu_side = ResponsePort("CPU side port, receives requests")

    mem_side = RequestPort("Memory side port, sends requests")

    # baseline
    mem_issue_latency = Param.Cycles(
        1, "Baseline latency for any read/write operation"
    )
    read_issue_latency = Param.Cycles(1, "Latency for a read operation")
    write_issue_latency = Param.Cycles(1, "Latency for a write operation")

    # read_verif_tags_cycles = Param.Cycles(
    #     1, "Cycles take for the module to verify the tag on a read"
    # )

    # write_calc_tags_cycles = Param.Cycles(
    #     1, "Cycles take for the module to calculate the tag on a write"
    # )

    # key_tag_cache_access_latency = Param.Cycles(
    #     1, "Cycles taken for the module to access the key tag cache"
    # )

    # sm_cache_hitrate = Param.Float(0.5, "Hitrate of the secure module cache")

    # dram_avg_access_latency = Param.Latency(
    #     "Average access latency for the DRAM"
    # )

    request_queue_size = Param.Unsigned(32, "Size of the request queue")

    response_queue_size = Param.Unsigned(32, "Size of the response queue")
