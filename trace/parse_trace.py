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
    "/data/pooya/gem5/runs/mem_pipe/2024-03-03_15-57-32/traces/*.stdout"
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

    # fields = r"^([0-9]+).*(\w\w\w)_side.*MEM\s(\w+)\s\[(\w+):(\w+)\]"
    # counter = 0
    # matches = {}
    # latency_sum = 0

    # with open(TRACE_FILE) as f:
    #     for line in f:
    #         result = re.match(fields, line)
    #         if result:
    #             timestamp = int(result[1])
    #             tp = result[2]
    #             op = result[3]
    #             start_address = int(result[4], 16)
    #             end_address = int(result[5], 16)
    #             counter += 1
    #             try:
    #                 if tp == "mem":
    #                     matches[start_address] = timestamp
    #                 else:
    #                     latency_sum += timestamp - matches[start_address]
    #                     # remove that address from the list
    #                     # matches.pop(start_address, None)
    #                     del matches[start_address]
    #             except:
    #                 pass
    #             if counter > 5000000:
    #                 break

    #     avg_dram_latency = latency_sum / counter
    #     print("Average latency: ", avg_dram_latency)

    avg_dram_latency = 25000
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

    # print("INFO: total mem accesses in a 64ms period", tot_num_mem_accesses)
    # print("INFO: total cache accesses in a 64ms period", tot)

    # total time simulation executed in ticks
    total_time = clocked_accesses[0][-1][0] - clocked_accesses[0][0][0]

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
    trh = 250
    for i, v in accesses_per_row.items():
        c = v["total count"] // trh
        extra_refreshes += c

    real_overhead = extra_refreshes * avg_dram_latency / total_time * 8 * 100
    # print("INFO: Worst case extra latency", round(ws_el, 2))
    # print(f"INFO: Worst case overhead: {round(ws_overhead, 2)}%")
    print(f"INFO:{benchmark} real_overhead: {round(real_overhead, 2)}%")

# num_threads = len(TRACE_FILES)
# with concurrent.futures.ThreadPoolExecutor(
#     max_workers=os.cpu_count()
# ) as executor:
#     # Record the start time for each thread and submit the tasks
#     start_times = [time.time() for _ in range(num_threads)]
#     end_times = [0 for _ in range(num_threads)]
#     futures = [
#         executor.submit(
#             execute,
#             cmd_strs[i],
#         )
#         for i in range(num_threads)
#     ]

#     # update simulation status
#     try:
#         while True:
#             # Move the cursor up by 'num_threads' lines to update the statuses in place
#             print(f"\033[{num_threads}A", end="")

#             for i, future in enumerate(futures):
#                 # elapsed_time = time.time() - start_times[i]
#                 if future.running():
#                     end_times[i] = time.time()
#                     elapsed_time = end_times[i] - start_times[i]
#                     status = "Running ⏳"
#                 elif future.done():
#                     elapsed_time = end_times[i] - start_times[i]
#                     if future.result() == 0:
#                         status = "Done ✅"
#                     else:
#                         status = f"Failed ❌"
#                 else:
#                     status = "Waiting 🕑"
#                     start_times[i] = time.time()
#                     elapsed_time = 0
#                 print(
#                     f"{cmd_strs[i][1]:<15} {i+1:<3} | {'Status':<10} {status:<10} | {'Elapsed Time':<15} {elapsed_time:0.0f}s | "
#                 )

#             if all(future.done() for future in futures):
#                 break
#             time.sleep(1)  # Wait for 1 second before the next status update

#     except KeyboardInterrupt:
#         print(
#             "\n❌ Keyboard interrupt received, cancelling tasks...\nYou may need to run `pkill gem5` to make sure all threads are taken care of! 🚨"
#         )
#         for future in futures:
#             future.cancel()  # Attempt to cancel each future
