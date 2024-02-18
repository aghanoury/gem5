import re
import argparse
# import matplotlib.pyplot as plt
import json


def read_chunk(fo, size=1024):
    # generator to read a file in chunks
    while True:
        data = fo.read(size)
        if not data:
            break
        yield data


# parsing parameters
TICKS_PER_SECOND = 1000000 # 1 tick = 1 µs
TIMEWINDOW = 1000 # in µs

parser = argparse.ArgumentParser(description='Parse trace files')
# add a mandatory argument (1 or more) trace files
parser.add_argument('trace_file', type=str, help='trace file to parse', nargs='+')

args = parser.parse_args()

# fields to parse
fields = r"^([0-9]+).*mem_side.*MEM\s(\w+)\s\[(\w+):(\w+)\]"

# access addresses over a time window
accessed_addresses = {}

# because these files are huge, we should test our cache we read through the file
initial_timestamp = 0
# time sets. we want to break the traces into 64 milli second chunks
s = set()
print("INFO: parsing files")
for file in args.trace_file:
    counter = 0
    with open(file, 'r') as f:
        for line in f:
            result = re.match(fields, line)
            if result:
                timestamp = int(result[1])
                op = result[2]
                start_address = int(result[3], 16)
                end_address = int(result[4], 16)

                ms_block = timestamp // 64000000000
                s.add(timestamp // 64000000000)
                if counter % 1000000 == 0:
                    print("Progress:", timestamp)
                if len(s) > 3:
                    break
                counter += 1

                if ms_block not in accessed_addresses:
                    accessed_addresses[ms_block] = {}
                accessed_addresses[ms_block][start_address] = accessed_addresses[ms_block].get(start_address, 0) + 1


# sort the accessed addresses list by the most accessed
# print("INFO: sorting dict")
# for chunk in accessed_addresses:
#     print(chunk)

# save the accessed addresses to a json file
print("INFO: saving to json")



exit()

# Regular expression pattern to extract addresses
pattern = r'\[([a-f0-9]+):([a-f0-9]+)\]'

# Dictionary to store addresses and their counts
address_counts = {}

# Open the file and read line by line
with open('traces/gcc_r.trace', 'r') as file:
    for line in file:
        # Check if the line indicates CPU to MEM
        if 'mem_side' in line:
            # Extract addresses using regular expression
            addresses = re.findall(pattern, line)
            # print(line)
            for address_range in addresses:
                # Extract start and end addresses
                start_address = int(address_range[0], 16)
                address_counts[start_address] = address_counts.get(start_address, 0) + 1
                # end_address = int(address_range[1], 16)
                # # Increment count for each address
                # for address in range(start_address, end_address + 1):
                #     address_counts[address] = address_counts.get(address, 0) + 1

# Plotting histogram
print("done parsing")

# bin the address counts in bins ranges of 100
binned_address_counts = {}
for address, count in address_counts.items():
    bin = address // 1000000
    binned_address_counts[bin] = binned_address_counts.get(bin, 0) + count


# sort the binned addressess
binned_address_counts = dict(sorted(binned_address_counts.items(), key=lambda item: item[0], reverse=False))
# print it in json
print(json.dumps(binned_address_counts, indent=4))

# sort address_counts in descending order
address_counts = dict(sorted(address_counts.items(), key=lambda item: item[1], reverse=True))


# print the top 10 in json format
print(json.dumps(dict(list(address_counts.items())[:10]), indent=4))

# histogram plot the top 10 address counts
plt.bar(list(address_counts.keys())[:10], list(address_counts.values())[:10], color='skyblue')
plt.xlabel('Address')
plt.ylabel('Frequency')
plt.title('Histogram of Addresses')
# plt.show()
plt.savefig('address_histogram.pdf')

exit()

# print(json.dumps(address_counts, indent=4))
plt.bar(address_counts.keys(), address_counts.values(), color='skyblue')
plt.xlabel('Address')
plt.ylabel('Frequency')
plt.title('Histogram of Addresses')
# plt.show()
plt.savefig('address_histogram.pdf')