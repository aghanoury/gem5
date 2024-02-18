# file used for running all SPEC benchmarks for a particular platform.

import concurrent.futures
import os
import pdb
import subprocess
import sys
from itertools import product
import argparse
from datetime import datetime

# RUN_NAME = "shitwaves"


# spec_root = "/root/gem5/spec_bin/"
# benchmark_path = spec_root + "503.bwaves_r/run/run_base_train_main-m64.0000"
# spec_cmd = f"{benchmark_path}/bwaves_r_base.main-m64"
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
parser = argparse.ArgumentParser()
parser.add_argument(
    "--dry-run",
    action="store_true",
    default=False,
    help="Dry run the command",
)

args = parser.parse_args()


# spec commands
# ../run_base_train_main-m64.0000/perlbench_r_base.main-m64 -I. -I./lib suns.pl > suns.out 2>> suns.err
# ../run_base_train_main-m64.0000/cpugcc_r_base.main-m64 train01.c -O3 -finline-limit=50000 -o train01.opts-O3_-finline-limit_50000.s > train01.opts-O3_-finline-limit_50000.out 2>> train01.opts-O3_-finline-limit_50000.err
# ../run_base_train_main-m64.0000/bwaves_r_base.main-m64 bwaves_2 < bwaves_2.in > bwaves_2.out 2>> bwaves_2.err
# ../run_base_train_main-m64.0000/mcf_r_base.main-m64 inp.in  > inp.out 2>> inp.err
# ../run_base_train_main-m64.0000/cactusBSSN_r_base.main-m64 spec_train.par   > spec_train.out 2>> spec_train.err
# ../run_base_train_main-m64.0000/namd_r_base.main-m64 --input apoa1.input --iterations 7 --output apoa1.train.output > namd.out 2>> namd.err
# ../run_base_train_main-m64.0000/parest_r_base.main-m64 train.prm > train.out 2>> train.err
# ../run_base_train_main-m64.0000/povray_r_base.main-m64 SPEC-benchmark-train.ini > SPEC-benchmark-train.stdout 2>> SPEC-benchmark-train.stderr
# ../run_base_train_main-m64.0000/lbm_r_base.main-m64 300 reference.dat 0 1 100_100_130_cf_b.of > lbm.out 2>> lbm.err
# ../run_base_train_main-m64.0000/omnetpp_r_base.main-m64 -c General -r 0 > omnetpp.General-0.out 2>> omnetpp.General-0.err
# ../run_base_train_main-m64.0000/wrf_r_base.main-m64 > rsl.out.0000 2>> wrf.err
# ../run_base_train_main-m64.0000/wrf_r_base.main-m64 > rsl.out.0000 2>> wrf.err


spec_cmds = [
    # {
    #     "name": "perlbench_r",
    #     "path": "spec_bin/500.perlbench_r/run/run_base_train_main-m64.0000/",
    #     "bin": "perlbench_r_base.main-m64",
    #     "options": "\"\"-I. -I./lib\"\"",
    #     "inputs": "suns.pl",},
        
        {"name": "gcc_r",
        "path": "spec_bin/502.gcc_r/run/run_base_train_main-m64.0000/",
        "bin": "cpugcc_r_base.main-m64",
        "options": "\"-O3 -finline-limit=50000 -o train01.opts-O3_-finline-limit_50000.s\"",
        "inputs": "train01.c",},

        {"name": "povray_r",
        "path": "spec_bin/511.povray_r/run/run_base_train_main-m64.0000/",
        "bin": "povray_r_base.main-m64",
        "options": None,
        "inputs": "SPEC-benchmark-train.ini",},

        {"name": "lbm_r",
        "path": "spec_bin/519.lbm_r/run/run_base_train_main-m64.0000/",
        "bin": "lbm_r_base.main-m64",
        "options": "\"\\\"300 reference.dat 0 1\\\"\"",
        "inputs": "100_100_130_cf_b.of",},

        {"name": "mcf_r",
        "path": "spec_bin/505.mcf_r/run/run_base_train_main-m64.0000/",
        "bin": "mcf_r_base.main-m64",
        "options": None,
        "inputs": "inp.in",},

        {"name": "cactuBSSN_r",
        "path": "spec_bin/507.cactuBSSN_r/run/run_base_train_main-m64.0000/",
        "bin": "cactusBSSN_r_base.main-m64",
        "options": None,
        "inputs": "spec_train.par",},

        {"name": "wrf_r",
        "path": "spec_bin/521.wrf_r/run/run_base_train_main-m64.0000/",
        "bin": "wrf_r_base.main-m64",
        "options": None,
        "inputs": "",},
]


fast_forward = 100000000
maxinsts =     250000000
# fast_forward = 25000
# maxinsts =     25000
redirect=True

cmd_strs = []

def execute(cmd_str):
    print(cmd_str)
    if args.dry_run:
        return
    result = subprocess.run(cmd_str, shell=True)
    print(result)

# create the session directory, composed of current date and time
session_dir = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
if not os.path.exists(f"traces/{session_dir}"):
    os.mkdir(f"traces/{session_dir}")
for c in spec_cmds:
    run_dir = c["name"]
    cmd = c["path"] + c["bin"]
    opts = c["options"]
    ipts = c["path"] + c["inputs"]

    cmd_str = f"./build/X86/gem5.debug --debug-flags MemPipe --outdir=runs/{session_dir}/{run_dir}/ configs/mem_pipe/se_deriv.py --cmd {cmd} --mem_pipe --fast-forward {fast_forward} --maxinsts {maxinsts}"

    if ipts:
        cmd_str += f" -i {ipts} "
    if opts:
        cmd_str += f" --options {opts} "

    if redirect:
        cmd_str += f"1> traces/{session_dir}/{run_dir}.trace 2> traces/{session_dir}/{run_dir}.err"

    cmd_strs.append(cmd_str)
    # result = subprocess.run(cmd_str, shell=True)
    # stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # print(result)

with concurrent.futures.ThreadPoolExecutor() as executor:
    executor.map(execute,cmd_strs)

exit(0)

# run_commands = [
#     "./speed_bwaves_base.main-m64 bwaves_1 < bwaves_1.in",
# ]

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
