# file used for running all SPEC benchmarks for a particular platform.

import concurrent.futures
import os
import pdb
import subprocess
import sys
from itertools import product

RUN_NAME = "shitwaves"


spec_root = "/root/gem5/spec_bin/"
benchmark_path = spec_root + "503.bwaves_r/run/run_base_train_main-m64.0000"
spec_cmd = f"{benchmark_path}/bwaves_r_base.main-m64"
# benchmarks = [
#     "503.bwaves_r/run/run_base_bwaves",
# ]

# parser.add_argument(
#     "-F",
#     "--fast-forward",
#     action="store",
#     type=str,
#     default=None,
#     help="Number of instructions to fast forward before switching",
# )


cmd = "./build/X86/gem5.debug --outdir=runs/{}/{}/ configs/rowhammer/latest.py --binary {}"

run_commands = [
    "./speed_bwaves_base.main-m64 bwaves_1 < bwaves_1.in",
]

hit_rates = [
    0.0,
]
# run_params = list(product(binaries, hit_rates, [RUN_NAME]))
# print(run_params)


# print(f"{benchmark_path}")
c = cmd.format("spec", "bwaves_test", spec_cmd)
print(c)
exit()
# print(c.split())
subprocess.run(c.split())

# run shit in parallel
# def execute_binary(params):
#     # pdb.set_trace()
#     print(params[0], params[1])
#     # exit()
#     run_name = params[2].format(str(params[1]).replace('.',''))
#     print(run_name)
#     # exit()

#     # binary_path = f"{bin_path_base}{binary}"
#     result = subprocess.run(cmd.format(run_name, params[0], bin_path_base + params[0], str(params[1])), shell=True, check=True, stderr=subprocess.PIPE)


# with concurrent.futures.ThreadPoolExecutor() as executor:
#     executor.map(execute_binary, run_params, )
