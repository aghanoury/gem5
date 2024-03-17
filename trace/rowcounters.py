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
        return dict(sorted(d.items(), key=lambda item: item[1], reverse=True))
