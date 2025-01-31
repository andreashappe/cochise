#!/usr/bin/python3

import json
import math
import sys
import matplotlib.pyplot as plt

from dotenv import load_dotenv

from pathlib import Path

from rich.console import Console
from rich.pretty import Pretty

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from pathlib import Path
from pydantic import BaseModel, Field

from common import get_or_fail

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

class CmdResult(BaseModel):
    """Analyze the given command and its result"""

    wrong_format: bool = Field(
            description="The executed command had an invalid parameter and execution was aborted"
    )

    executable_unknown: bool = Field(
            description="The executed command did not exist on the target system."
    )

    successful: bool = Field(
            description="The executed command was successful."
    )

    tactic: str = Field(
            description="This command matches this MITRE ATT&CK tactic"
    )

    technique: str = Field(
            description="This command matches this MITRE ATT&CK technique"
    )

# setup API keys
load_dotenv()
get_or_fail("OPENAI_API_KEY") # langgraph will use this env variable itself
llm = ChatOpenAI(model="gpt-4o", temperature=0)

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

    return mean, variance

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
        gpt4o_token_input = 0
        gpt4o_token_output = 0

        exec_counter = 0
        execs = []

        # per-run
        invalid_cmd_count = 0

        for line in file:
            j = json.loads(line)

            if j['event'] == 'strategy_update':
                strat_updates += 1
                o1_token_input += j['costs']['token_usage']['prompt_tokens']
                o1_token_output += j['costs']['token_usage']['completion_tokens']
                duration_upd = j['duration']

                create_or_append(strat_updates, 'update_duration', [j['costs']['token_usage']['prompt_tokens'], duration_upd])
                create_or_append(strat_updates, 'state', len(j['result']))

            if j['event'] == 'strategy_next_task':
                o1_token_input += j['costs']['token_usage']['prompt_tokens']
                o1_token_output += j['costs']['token_usage']['completion_tokens']
                duration_next_task = j['duration']
                create_or_append(strat_updates, 'state_tokens', j['costs']['token_usage']['prompt_tokens'])
                create_or_append(strat_updates, 'upd_vs_nexttask', duration_upd/duration_next_task)

            # tool calls timed out
            if j['event'] == 'executor_summary_missing':
                executor_decisions += 1
                gpt4o_token_input += j['costs']['token_usage']['prompt_tokens']
                gpt4o_token_output += j['costs']['token_usage']['completion_tokens']

                execs.append(exec_counter)
                exec_counter = 0

            if j['event'] == 'executor_next_cmds':
                executor_decisions += 1
                gpt4o_token_input += j['costs']['token_usage']['prompt_tokens']
                gpt4o_token_output += j['costs']['token_usage']['completion_tokens']

                if len(j['result']['tool_calls']) == 0:
                    execs.append(exec_counter)
                    exec_counter = 0

            if j['event'] == 'executor_cmd':
                cmd_calls += 1
                exec_counter += 1

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

        runs[filename] = {
            'strat_updates': strat_updates,
            'executor_decisions': executor_decisions,
            'cmd_calls': cmd_calls,
            'o1_token_input': o1_token_input,
            'o1_token_output':o1_token_output,
            'gpt4o_token_input': gpt4o_token_input,
            'gpt4o_token_output': gpt4o_token_output,
            'exec_stat_mean': mean,
            'exec_stat_abweich': math.sqrt(variance)
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
for i in top_tools[:15]:
    print(f" - {i[0]} -> {i[1]['count']}")

console.print(Pretty(round))

# update duration depending upon prompt size
x = []
y = []

for idx in round.keys():
    i = round[idx]

    for j in i['update_duration']:
        x.append(j[0])
        y.append(j[1])

plt.scatter(x, y, marker="*")
plt.xlabel('token count in update prompt')
plt.ylabel('duration in sec')
plt.savefig('update_duration.png')
plt.clf()

# state size
x = []
y = []

for idx in round.keys():
    i = round[idx]

    for j in i['state']:
        x.append(idx)
        y.append(j)

plt.scatter(x, y, marker="*")
plt.xlabel('strategy round')
plt.ylabel('state size (plan) in characters')
plt.savefig('state_size.png')
plt.clf()

# state size (using input-tokens for next_task as proxy)
x = []
y = []

for idx in round.keys():
    i = round[idx]

    if 'state_tokens' in i:
        for j in i['state_tokens']:
            x.append(idx)
            y.append(j)

plt.scatter(x, y, marker="*")
plt.xlabel('strategy round')
plt.ylabel('state size in tokens (using input for next_task as proxy)')
plt.savefig('state_size_tokens.png')
plt.clf()

# verhaeltnis update-strategy vs. next-task
x = []
y = []

for idx in round.keys():
    i = round[idx]

    if 'upd_vs_nexttask' in i:
        for j in i['upd_vs_nexttask']:
            x.append(idx)
            y.append(j)

plt.scatter(x, y, marker=".")
plt.axhline(y = 1, color = 'r', linestyle = '-') 
plt.xlabel('strategy round')
plt.ylabel('verhaeltnis zeitverbrauch strategy update zu nexttask')
plt.savefig('relationship_strategy_update_nexttask.png')
plt.clf()

# histogram of amount of tool calls
x = []
for cmd in cmds.keys():
    x.append(cmds[cmd]['count'])

plt.hist(x, bins=50)
plt.title("Tool Call frequency")
plt.savefig('number_of_toolcalls_per_tool.png')
plt.clf()

# tools within runs
x = [0, 0, 0, 0, 0, 0 ,0]

count = 0
for cmd in cmds.keys():
    pos = cmds[cmd]['within_runs_pct'] * 6
    x[int(pos)] += 1
    count += 1

for i in range(1, 7):
    for j in range(i+1, 7):
        x[i] += x[j]

x = list(map(lambda i: i/count, x))
plt.bar( [1, 2, 3, 4, 5, 6], x[1:])
plt.xlabel("Tool was in >= x runs")
plt.ylabel("Percentage of tools")

plt.savefig('tools_within_runs.png')