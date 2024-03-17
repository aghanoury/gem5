import glob
import json
import re
import pdb
import numpy as np
import concurrent.futures
import os
import time

# custom imports
from cache import Cache
from rowcounters import RowCounters

from IPython.core.debugger import set_trace


# loop through all files in the directory
TRACE_FILES = glob.glob(
    "/data/pooya/gem5/runs/rowhammer/2024-03-11_10-51-12/traces/*.stdout"
)
# TRACE_FILE = "/data/pooya/gem5_1/runs/mem_pipe/2024-03-02_23-28-15/traces/cactuBSSN_r_0.stdout"

for TRACE_FILE in TRACE_FILES:
    # parse each line with regex
    fields = r"^([0-9]+).*mem_side.*MEM\s(\w+)\s\[(\w+):(\w+)\]"
    benchmark = TRACE_FILE.split("/")[-1].split("_")[0]
    # all accessed_addressed
    accessed_addresses = {}
    sorted_addresses = {}  # the same thing but sorted :p
    clocked_accesses = {}  # list of lists

    init_timestamp = 0
    inter_timestamp = 0
    prev_ms_block = 0

    avg_dram_latency = 25000

    s = set()
    print("INFO: parsing from file. this could a minute or two...")
    counter = 0
    with open(TRACE_FILE) as f:
        print(f"INFO: parsing {TRACE_FILE}")
        # parse out the first line to get initial timestamp

        # declare a new cache
        cache = Cache(size=2**15)
        row_counters = RowCounters()

        while True:
            for line in f:
                result = re.match(fields, line)
                if result:
                    init_timestamp = int(result[1])
                    inter_timestamp = init_timestamp
                    timestamp = int(result[1])
                    op = result[2]
                    start_address = int(result[3], 16)
                    end_address = int(result[4], 16)
                    ms_block = (timestamp - init_timestamp) // 64000000000
                    prev_ms_block = ms_block
                    break
            break

        for line in f:
            result = re.match(fields, line)
            if result:
                timestamp, op, start_address, end_address = (
                    int(result[1]),
                    result[2],
                    int(result[3], 16),
                    int(result[4], 16),
                )

                row = start_address >> 13

                ms_block = (timestamp - init_timestamp) // 64000000000

                if ms_block != prev_ms_block:
                    stats = cache.get_stats()
                    tot = (
                        stats.read_hits
                        + stats.read_misses
                        + stats.write_hits
                        + stats.write_misses
                    )
                    t = timestamp - inter_timestamp
                    print(f"INFO: block duration {t/10**9} ms")

                    # calculate overheads
                    extra_refreshes = stats.read_misses + stats.write_misses

                    # reset the cache
                    cache.flush()
                    prev_ms_block = ms_block
                    inter_timestamp = timestamp

                # counter cache
                if "Read" in op:
                    # print("READ", op)
                    stat = cache.read(row, timestamp)
                    if not stat:
                        cache.write(row, 1, timestamp)
                else:
                    cache.write(row, 1, timestamp)

                # row counters
                # row_counters[row] += 1
