#!/usr/bin/python3

import json
import math

from pathlib import Path
from rich.console import Console
from rich.pretty import Pretty

files = [
    'examples/test-runs/initial-setup/run-20250128-181630.json',
    'examples/test-runs/first-round/run-20250128-203002.json',
    'examples/test-runs/first-round/run-20250129-152651.json',
    # 'examples/test-runs/first-round/run-20250129-074136.json', # just one hour
    #'examples/test-runs/first-round/run-20250129-172241.json', # just one hour
    'examples/test-runs/first-round/run-20250129-085237.json',
    'examples/test-runs/first-round/run-20250129-194248.json',
    'examples/test-runs/first-round/run-20250129-110006.json'

]

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

        filename = Path(filename).stem

        strat_updates = 0
        executor_decisions = 0
        cmd_calls = 0

        # do we need to remove the cached tokens from input?
        o1_token_input = 0
        o1_token_output = 0
        o1_cached_tokens = 0
        gpt4o_token_input = 0
        gpt4o_token_output = 0
        gpt4o_cached_tokens = 0

        exec_counter = 0
        execs = []
        cmd_counter = 0
        exec_cmds = []

        # per-run
        invalid_cmd_count = 0
        cmd_counter = 0

        for line in file:
            j = json.loads(line)

            if j['event'] == 'strategy_update':


                strat_updates += 1
                o1_token_input += j['costs']['token_usage']['prompt_tokens']
                o1_token_output += j['costs']['token_usage']['completion_tokens']
                o1_cached_tokens += j['costs']['token_usage']['prompt_tokens_details']['cached_tokens']
                duration_upd = j['duration']
                exec_counter = 0

                create_or_append(strat_updates, 'update_duration', [j['costs']['token_usage']['prompt_tokens'], duration_upd])
                create_or_append(strat_updates, 'state', len(j['result']))

            if j['event'] == 'strategy_next_task':
                o1_token_input += j['costs']['token_usage']['prompt_tokens']
                o1_token_output += j['costs']['token_usage']['completion_tokens']
                o1_cached_tokens += j['costs']['token_usage']['prompt_tokens_details']['cached_tokens']
                duration_next_task = j['duration']
                create_or_append(strat_updates, 'state_tokens', j['costs']['token_usage']['prompt_tokens'])
                create_or_append(strat_updates, 'upd_vs_nexttask', duration_upd/duration_next_task)

            # tool calls timed out
            if j['event'] == 'executor_summary_missing':
                executor_decisions += 1
                exec_counter += 1

                gpt4o_token_input += j['costs']['token_usage']['prompt_tokens']
                gpt4o_token_output += j['costs']['token_usage']['completion_tokens']
                gpt4o_cached_tokens += j['costs']['token_usage']['prompt_tokens_details']['cached_tokens']

                execs.append(exec_counter)
                exec_cmds.append(cmd_counter)
                exec_counter = 0
                cmd_counter = 0

            if j['event'] == 'executor_next_cmds':
                executor_decisions += 1
                exec_counter += 1

                gpt4o_token_input += j['costs']['token_usage']['prompt_tokens']
                gpt4o_token_output += j['costs']['token_usage']['completion_tokens']
                gpt4o_cached_tokens += j['costs']['token_usage']['prompt_tokens_details']['cached_tokens']

                if len(j['result']['tool_calls']) == 0:
                    execs.append(exec_counter)
                    exec_cmds.append(cmd_counter)
                    exec_counter = 0
                    cmd_counter  = 0

            if j['event'] == 'executor_cmd':
                cmd_calls += 1
                cmd_counter += 1
                cmd = j['cmd'].split(' ')[0]

                # increase counter
                if not cmd in cmds:
                    cmds[cmd] = {
                        'count': 1
                    }
                else:
                    cmds[cmd]['count'] += 1


                if not cmd in tools_used_within_run:
                    tools_used_within_run[cmd] = {
                        filename: True
                    }
                else:
                    tools_used_within_run[cmd][filename] = True

        mean, variance = std_dev(execs)
        cmd_mean, cmd_var = std_dev(exec_cmds)

        runs[filename] = {
            'strat_updates': strat_updates,
            'executor_decisions': executor_decisions,
            'cmd_calls': cmd_calls,
            'o1_token_input': o1_token_input,
            'o1_token_output':o1_token_output,
            'o1_cached_tokens': o1_cached_tokens,
            'gpt4o_token_input': gpt4o_token_input,
            'gpt4o_token_output': gpt4o_token_output,
            'gpt4o_cached_tokens': gpt4o_cached_tokens,
            'executor_commands': execs,
            'executed_commands': exec_cmds,
            'exec_stat_mean': mean,
            'exec_stat_abweich': math.sqrt(variance),
            'cmd_stat_mean': cmd_mean,
            'cmd_stat_abweich': math.sqrt(cmd_var)
        }

for filename in files:
    analyze_file(filename)

for tool in tools_used_within_run.keys():
    tool_runs  = tools_used_within_run[tool]
    cmds[tool]['within_runs_pct'] = len(tool_runs) / len(files)

console.print(Pretty(runs))

console.print(Pretty(cmds))
console.print(f"different tools: {len(cmds)}")


top_tools = sorted(cmds.items(), key=lambda x:x[1]['count'], reverse=True)
for i in top_tools[:16]:
    print(f" - {i[0]} -> {i[1]['count']}; run-pct: {i[1]['within_runs_pct']}")

console.print(Pretty(round))

print(str(', '.join(sorted(cmds.keys()))))

overall_costs = 0

o1_input = []
o1_output = []
gpt4o_input = []
gpt4o_output = []

execs = []
exec_cmds = []
for run in runs.keys():
    data = runs[run]
    print(str(data))

    cost = data['o1_token_input']/1_000_000*15 - data['o1_cached_tokens']/1_000_000*7.5 + data['o1_token_output']/1_000_000*60 + data['gpt4o_token_input']/1_000_000*2.5 - data['gpt4o_cached_tokens']/1_000_000*1.25 + data['gpt4o_token_output']/1_000_000*10 
    overall_costs += cost
    print(str(cost))

    o1_input.append(data['o1_token_input'])
    o1_output.append(data['o1_token_output'])
    gpt4o_input.append(data['gpt4o_token_input'])
    gpt4o_output.append(data['gpt4o_token_output'])
    execs += data['executor_commands']
    exec_cmds += data['executed_commands']

print(overall_costs/6)

print(str(std_dev(o1_input)))
print(str(std_dev(o1_output)))
print(str(std_dev(gpt4o_input)))
print(str(std_dev(gpt4o_output)))

print(str(execs))
print(str(exec_cmds))

print(str(std_dev(execs)))
print(str(std_dev(exec_cmds)))