#!/usr/bin/python3

import argparse
import json
import math

from pathlib import Path
from rich.console import Console
from rich.pretty import Pretty

console = Console()

strat_updates = None
next_tast = None
tool_calls = None

# cmd.split(' ')[0] -> usage count, failed_count
cmds = {}

tools_used_within_run = {}  # tools -> run

runs = {}

def std_dev(dataset):
    # Calculate mean
    length = len(dataset)
    mean = sum(dataset) / length

    # Calculate variance
    squared_diffs = [(x - mean) ** 2 for x in dataset]
    variance = sum(squared_diffs) / length

    return mean, math.sqrt(variance)

round = {}

def create_or_append(run, key, value):

    run = str(run)

    if not run in round:
        round[run] = {}
    
    if not key in round[run]:
        round[run][key] = []

    round[run][key].append(value) 


def analyze_file(filename):
    with open(filename, 'r') as file:

        strat_updates = 0
        executor_decisions = 0
        cmd_calls = 0

        exec_counter = 0
        execs = []
        cmd_counter = 0
        exec_cmds = []

        # per-run
        cmd_counter = 0

        for line in file:
            j = json.loads(line)

            if j['event'] == 'strategy_update':
                strat_updates += 1

            if j['event'] == 'strategy_next_task':
                exec_counter = 0

            # tool calls timed out
            if j['event'] == 'executor_summary_missing':
                executor_decisions += 1
                exec_counter += 1

                execs.append(exec_counter)
                exec_cmds.append(cmd_counter)
                exec_counter = 0
                cmd_counter = 0

            if j['event'] == 'executor_next_cmds':
                executor_decisions += 1
                exec_counter += 1

                if len(j['result']['tool_calls']) == 0:
                    execs.append(exec_counter)
                    exec_cmds.append(cmd_counter)
                    exec_counter = 0
                    cmd_counter  = 0

            if j['event'] == 'executor_cmd':
                cmd_calls += 1
                cmd_counter += 1

        mean, variance = std_dev(execs)
        cmd_mean, cmd_var = std_dev(exec_cmds)

        return {
            'strat_updates': strat_updates,
            'executor_decisions': executor_decisions,
            'cmd_calls': cmd_calls,
            'executor_commands': execs,
            'executed_commands': exec_cmds,
            'exec_stat_mean': mean,
            'exec_stat_abweich': math.sqrt(variance),
            'cmd_stat_mean': cmd_mean,
            'cmd_stat_abweich': math.sqrt(cmd_var)
        }

if __name__=='__main__':

    console = Console()

    parser=argparse.ArgumentParser()
    parser.add_argument('-i','--input')
    args = parser.parse_args()

    result = analyze_file(args.input)
    print(str(result))

    print(f"Strategy rounds: {result['strat_updates']}")
    print(f"Executor calls/Strategy-round: mean: {result['exec_stat_mean']}, std: {result['exec_stat_abweich']}")
    print(f"Command calls/Strategy-round: mean: {result['cmd_stat_mean']}, std: {result['cmd_stat_abweich']}")
    