import math
from types import SimpleNamespace
import numpy as np
import pdb


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
                {"way": x, "tag": 0, "valid": 0, "data": [0 for ], "last_access": 0}
                for x in range(self.set_assoc)
            ]
            for _ in range(self.num_sets)
        ]

        self.init_stats()

    def flush(self):
        self.sets = [
            [
                {"way": x, "tag": 0, "valid": 0, "data": 0, "last_access": 0}
                for x in range(self.set_assoc)
            ]
            for _ in range(self.num_sets)
        ]
        self.init_stats()

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
