import argparse
import concurrent.futures
import os
import pdb
import subprocess
import sys
from datetime import datetime
from itertools import product

parser = argparse.ArgumentParser()
parser.add_argument(
    "--dry-run",
    action="store_true",
    default=False,
    help="Dry run the command",
)
parser.add_argument(
    "-b",
    "--bench",
    "--benchmark",
    help="Benchmark to run. Without this, program runs all by default",
)
parser.add_argument(
    "-r",
    "--redirect",
    action="store_true",
    default=False,
    help="Redirect output to file",
)

# Set up argument parser
parser = argparse.ArgumentParser()
parser.add_argument(
    "--dry-run", action="store_true", default=False, help="Dry run the command"
)
parser.add_argument(
    "-b",
    "--bench",
    "--benchmark",
    nargs="+",
    help="Benchmark to run[^1^][1]. Without this, program runs all by default",
)
parser.add_argument(
    "-r",
    "--redirect",
    action="store_true",
    default=False,
    help="Redirect output to file",
)
args = parser.parse_args()

args = parser.parse_args()

bin_path_base = "microbench/"
binaries = ["mm", "lfsr", "merge", "sieve", "spmv"]

read_latencies = {
    "baseline": 0,
    "multiply_128": 108 - 42 - 7,
    "multiply_256": 209 - 42 - 7,
    "sha_256": 267 - 42 - 7,
    "aes_128": 276 - 42 - 7,
    "aes_256": 411 - 42 - 7,
}


run_params = list(product(binaries, read_latencies))
# print("Run Params", run_params)

session_dir = f"raven/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
cmd_strs = []

for bench in binaries:
    for hash, latency in read_latencies.items():
        output_dir = session_dir + f"/{bench}/{hash}"
        rl_str = f"--read_latency {latency}"
        cmd = f"build/X86/gem5.debug --outdir={output_dir}/ configs/malware_detection/latest.py {rl_str} --binary {bin_path_base + bench} --cache"
        # if args.redirect:
        #     cmd += f"1> {output_dir}/output.stdout 2> {output_dir}/output.stderr"
        cmd_strs.append(cmd)


def execute(cmd_str):
    print(cmd_str.split())
    if args.dry_run:
        return
    result = subprocess.run(cmd_str, shell=True)
    print("INFO: process exited with code", result.returncode)


with concurrent.futures.ThreadPoolExecutor() as executor:
    executor.map(execute, cmd_strs)

print(f"INFO: Done running all benchmarks. Exiting.")
print(
    f"INFO: trace files are stored in {session_dir}. It is highly recommended to move them to a different location or rename the folder."
)
exit(0)
