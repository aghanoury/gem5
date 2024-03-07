import glob
import json
import math
import re
from types import SimpleNamespace

import numpy as np
from IPython.core.debugger import set_trace

# define a cache


class Cache:
    def __init__(self, size=2**15, set_assoc=8, line_size=8):
        # cache lines are just tuples, where first elemetnt is tag, second is valid bit, and third is the data
        # it's a list and indexed by the set index
        # each set then contains a list of ways

        # sanity checks
        if size % line_size != 0:
            raise ValueError("Cache size must be divisible by line size")
        if size % set_assoc != 0:
            raise ValueError(
                "Cache size must be divisible by set associativity"
            )
        if line_size % 2 != 0:
            raise ValueError("Line size must be divisible by 2")

        self.size = size
        self.set_assoc = set_assoc
        self.line_size = line_size
        self.num_lines = size // line_size
        self.num_sets = self.num_lines // self.set_assoc

        self.bo_size = int(math.log2(self.line_size))
        self.bo_bit_mask = (1 << self.bo_size) - 1

        self.set_index_size = int(math.log2(self.num_lines // self.set_assoc))
        self.set_index_bit_mask = (1 << self.set_index_size) - 1

        self.tag_shift_size = self.set_index_size + self.bo_size
        # no need for a tag bit mask
        # print(self.bo_size, self.set_index_size, self.tag_size)

        self.sets = [
            [
                {"way": x, "tag": 0, "valid": 0, "data": 0, "last_access": 0}
                for x in range(self.set_assoc)
            ]
            for _ in range(self.num_sets)
        ]

        self.init_stats()

        print("INFO: Cache initialized")
        print(
            f"INFO: cache params: size: {self.size} set_assoc: {self.set_assoc} line_size: {self.line_size}, num_lines: {self.num_lines}, num_sets: {self.num_sets}"
        )

        # self.sets = [CacheSet(SET_ASSOCIATIVITY) for _ in range(NUM_LINES // SET_ASSOCIATIVITY)]

    def read(self, address, timestamp):
        """Access the cache at the given address. Returns data if hit, False if miss."""

        block_bits = address & self.bo_bit_mask
        set_index = (address >> self.bo_size) & self.set_index_bit_mask
        tag_bits = address >> self.tag_shift_size

        for i in self.sets[set_index]:
            if i["tag"] == tag_bits and i["valid"] == 1:
                # sanity check
                if i["last_access"] > timestamp:
                    raise ValueError(
                        "Timestamps are not monotonically increasing"
                    )
                i["last_access"] = timestamp
                self.read_hits += 1
                return i["data"]  # return the data

        self.read_misses += 1
        return False

    def write(self, address, data, timestamp):
        """Write to the cache at the given address. Returns None if the write was successful (write hit) returns the address and data of the evicted line."""

        block_bits = address & self.bo_bit_mask
        set_index = (address >> self.bo_size) & self.set_index_bit_mask
        tag_bits = address >> self.tag_shift_size

        # the write policy should write to the first way that is invalid
        s = self.sets[set_index]

        # first check the tags, the line is already in the cache, just write to it
        for i in self.sets[set_index]:
            if i["tag"] == tag_bits and i["valid"] == 1:
                i["data"] = data
                i["last_access"] = timestamp
                self.write_hits += 1
                return None
        for i in self.sets[set_index]:
            if i["valid"] == 0:
                # print("found invalid line")
                c = i.copy()
                i["valid"] = 1
                i["tag"] = tag_bits
                i["data"] = data
                i["last_access"] = timestamp
                self.write_misses += 1
                return c

        # if we reach this point, every line is valid, and we need to evict one
        self.write_misses += 1
        self.write_evictions += 1
        # find LRU
        lru = math.inf
        evicted = None
        for i in self.sets[set_index]:
            if i["last_access"] < lru:
                lru = i["last_access"]
                evicted = i.copy()
        for i in self.sets[set_index]:
            if i["last_access"] == lru:
                i["tag"] = tag_bits
                i["data"] = data
                i["last_access"] = timestamp

        return evicted

    def print_set(self, set_index):
        """Print the contents of a set"""
        s = self.sets[set_index]
        print(f"Set {set_index}")
        print(json.dumps(s))

    def dump_contents(self):
        """Dump contents for debugging"""

        for i, s in enumerate(self.sets):
            print("Set", i)
            for k in s:
                print(k)

    def init_stats(self):
        print("INFO: init stats")
        self.read_hits = 0
        self.read_misses = 0

        self.write_hits = 0
        self.write_misses = 0
        self.write_evictions = 0

    # return a namespace of the stats
    def get_stats(self):
        return SimpleNamespace(
            **{
                "read_hits": self.read_hits,
                "read_misses": self.read_misses,
                "write_hits": self.write_hits,
                "write_misses": self.write_misses,
                "write_evictions": self.write_evictions,
            }
        )

    def print_stats(self):
        print("INFO: read hits:", self.read_hits)
        print("INFO: read misses:", self.read_misses)
        print("INFO: write hits:", self.write_hits)
        print("INFO: write misses:", self.write_misses)
        print("INFO: write evictions:", self.write_evictions)


# loop through all files in the directory
TRACE_FILES = glob.glob(
    "/data/pooya/gem5_1/runs/mem_pipe/2024-03-02_23-28-15/traces/*.stdout"
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

    first_lined = False
    init_timestamp = 0

    s = set()
    if ".json" in TRACE_FILE:
        print("INFO: loading from json")
        accessed_addresses = json.load(open(TRACE_FILE))
    else:
        print("INFO: parsing from file. this could a minute or two...")
        counter = 0
        with open(TRACE_FILE) as f:
            # parse out the first line for some key numbers
            while True:
                for line in f:
                    result = re.match(fields, line)
                    if result:
                        init_timestamp = int(result[1])
                        timestamp = int(result[1])
                        op = result[2]
                        start_address = int(result[3], 16)
                        end_address = int(result[4], 16)
                        ms_block = (timestamp - init_timestamp) // 64000000000
                        break
                break

            for line in f:
                result = re.match(fields, line)
                if result:
                    timestamp = int(result[1])
                    op = result[2]
                    start_address = int(result[3], 16)
                    end_address = int(result[4], 16)

                    ms_block = (timestamp - init_timestamp) // 64000000000
                    s.add(ms_block)
                    if ms_block not in clocked_accesses:
                        clocked_accesses[ms_block] = []
                    clocked_accesses[ms_block].append(
                        (timestamp, start_address, end_address, op)
                    )

                    if ms_block not in accessed_addresses:
                        accessed_addresses[ms_block] = {}
                    accessed_addresses[ms_block][start_address] = (
                        accessed_addresses[ms_block].get(start_address, 0) + 1
                    )

        # print("INFO: saving to json")
        # with open('accessed_addresses.json', 'w') as f:
        #     json.dump(accessed_addresses, f, indent=4)

    # get average mem access time accross entire trace

    fields = r"^([0-9]+).*(\w\w\w)_side.*MEM\s(\w+)\s\[(\w+):(\w+)\]"
    counter = 0
    matches = {}
    latency_sum = 0

    with open(TRACE_FILE) as f:
        for line in f:
            result = re.match(fields, line)
            if result:
                timestamp = int(result[1])
                tp = result[2]
                op = result[3]
                start_address = int(result[4], 16)
                end_address = int(result[5], 16)
                counter += 1
                try:
                    if tp == "mem":
                        matches[start_address] = timestamp
                    else:
                        latency_sum += timestamp - matches[start_address]
                        # remove that address from the list
                        # matches.pop(start_address, None)
                        del matches[start_address]
                except:
                    pass
                if counter > 5000000:
                    break

        avg_dram_latency = latency_sum / counter
        print("Average latency: ", avg_dram_latency)

    # save the accessed addresses to a json file
    # sorted_accesses = {}
    # for chunk in accessed_addresses.items():
    #     sorted_dict = dict(sorted(chunk[1].items(), key=lambda item: item[1], reverse=True))
    #     sorted_accesses[chunk[0]] = sorted_dict

    # print the top 10 items in the sorted dict
    # save the sorted_access json to a file
    # print("Saving ")
    # with open('sorted_accesses.json', 'w') as f:
    #     json.dump(sorted_accesses, f, indent=4)

    cache = Cache(size=2**15)
    for i in clocked_accesses[0]:
        timestamp = i[0]
        start_addr = i[1]
        end_addr = i[2]
        op = i[3]

        # convert start_addr to row_address
        addr = start_addr >> 13
        if "Read" in op:
            # print("READ", op)
            stat = cache.read(addr, timestamp)
            if not stat:
                cache.write(addr, 1, timestamp)
        else:
            # print("WRITE", op)
            cache.write(addr, 1, timestamp)

    cache.print_stats()

    # next, we need to simulate a cache.
    # we have the clocked accesses.
    # start with the second block, since the first is almost garuenteed to not the full 64ms window

    # how does our methodology work?
    # 1. Upon if we have a cache hit, return data to cpu and issue REFs to nearby rows, reset counter
    # 2. maintain counters per row
    # 3. perhaps not on every access do we need to cache the data. but maybe we cache it whenever a certain value on the counter is reached

    # 32 GB of memory space = 8M lines
    DRAM_SIZE = 32 * 2**30
    ROW_SIZE = 8 * 2**10
    NUM_ROWS = DRAM_SIZE // ROW_SIZE
    WIDTH = 8  # in bits

    # a row counter object. we will then have a list of these
    class RowCounters:
        def __init__(self):
            self._width = 8  # in bits
            self._counters = [0 for _ in range(NUM_ROWS)]

        def __getitem__(self, index):
            # TODO: support slicing at some point
            return self._counters[index]

        def __setitem__(self, index, value):
            # TODO: support slicing at some point
            if index < 0 or index >= NUM_ROWS:
                raise IndexError("Index out of bounds")
            # if value > 2**WIDTH-1:
            #     print("WARNING: counter spill over")
            self._counters[index] = value

        def __contains__(self, index):
            if index < 0 or index >= NUM_ROWS:
                return False
            else:
                return True

        def __len__(self):
            return NUM_ROWS

        def convert_address_to_row(self, address) -> int:
            """Returns a row index given an address."""
            return address // ROW_SIZE

        def check_counters(self, threshold=2 ** (WIDTH - 1)) -> list:
            """Returns a list of indeces of rows that have reached the threshold."""
            # check if any counters
            ind = []
            for i in range(NUM_ROWS):
                if self[i] >= threshold:
                    ind.append(i)
            return ind

        def clear_all(self):
            for i in range(NUM_ROWS):
                self[i] = 0

        def get_sorted(self):
            """returns a dictionary sorted by the counter value"""
            d = {}
            for i in range(NUM_ROWS):
                d[i] = self[i]
            return dict(
                sorted(d.items(), key=lambda item: item[1], reverse=True)
            )

    c = RowCounters()

    for access in clocked_accesses[0]:
        timestamp = access[0]
        start_address = access[1]
        end_address = access[2]
        op = access[3]

        row = c.convert_address_to_row(start_address)
        c[row] += 1

    accesses_per_row = {}
    row_accesses = c.get_sorted()  # get the sorted list of rows
    for s in row_accesses:
        if c[s] != 0:
            accesses_per_row[s] = {}
            accesses_per_row[s]["total count"] = c[s]

    # now loop through all accesses and count them
    for access in accessed_addresses[0]:
        row = c.convert_address_to_row(access)
        if row in accesses_per_row:
            accesses_per_row[row][access] = accessed_addresses[0][access]

    # calculate feasability

    stats = cache.get_stats()

    # total mem accesses in a 64ms period
    tot_num_mem_accesses = len(clocked_accesses[0])
    tot = (
        stats.read_hits
        + stats.read_misses
        + stats.write_hits
        + stats.write_misses
    )

    print("INFO: total mem accesses in a 64ms period", tot_num_mem_accesses)
    print("INFO: total cache accesses in a 64ms period", tot)

    num_row_accessed = len(accessed_addresses[0])
    print(
        "INFO: total number of rows accessed in a 64ms period",
        num_row_accessed,
    )

    # baseline refreshes that must always occur
    extra_refreshes = stats.read_misses + stats.write_misses

    bs = (
        (stats.read_hits + stats.write_hits) / num_row_accessed
    ) // 250 + extra_refreshes
    ws = (stats.read_hits + stats.write_hits) / 250 + extra_refreshes

    print(bs, ws)

    # worst case extra latency
    # bs_el = bs * avg_dram_latency / 1000
    ws_el = ws * avg_dram_latency / 1000 / 1000 / 1000 * 8
    ws_overhead = ws_el / 64 * 100

    # more realistic refreshes
    for i, v in accesses_per_row.items():
        c = v["total count"] // 50
        extra_refreshes += c

    real_overhead = (
        extra_refreshes * avg_dram_latency / 1000 / 1000 / 1000 / 64 * 100 * 8
    )
    print("INFO: Worst case extra latency", round(ws_el, 2))
    print(f"INFO: Worst case overhead: {round(ws_overhead, 2)}%")
    print(
        f"INFO:ℹ️ BENCHMARK: {benchmark} Realistic overhead: {round(real_overhead, 2)}%"
    )
