#!/usr/bin/python3

import argparse
import json

from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty


def tc_create(data, name, params):
    tmp = {}
    for param in params:
        tmp[param] = data[param]

    return {
        "tool_name": name,
    } | tmp

def analyze_replay(console, file):

    tool_calls = {}

    for line in file:
        j = json.loads(line)
        match j['event']:
            case 'configuration':
                data = {
                    'model': j['model'],
                    'ssh-host': j['ssh-host'],
                    'ssh-user': j['ssh-user'],
                    'max_runtime': j['max_runtime']
                }
                tmp = "\n".join([f"{k}: {v}" for k, v in data.items()])
                console.print(Panel(tmp, title="Configuraton"))
            case 'planner_initial_plan':
                console.print(Panel(j['result'], title="Intial Plan"))
            case 'compact_history':
                console.print(Panel(j['result'], title="Compacted Plan"))
            case 'planner_task_selection':
                console.print("Asking Planner for the next task..")
            case 'tool_call':
                match j['tool_name']:
                    case 'perform_task':
                        p = j['params']
                        text = f"# {p['next_step']} ({p['mitre_attack_tactic']}/{p['mitre_attack_technique']})\n\n{p['next_step_context']}"
                        console.print(Panel(text, title="Starting Tool Call: perform_task"))
                        tool_calls[j['tool_call_id']] = tc_create(j['params'], 'perform_task', ['mitre_attack_tactic', 'mitre_attack_technique', 'next_step', 'next_step_context'])
                    case 'execute_command':
                        tool_calls[j['tool_call_id']] = tc_create(j['params'], 'execute_command', ['mitre_attack_technique', 'mitre_attack_procedure', 'command'])
                    case 'add_entity_information':
                        tool_calls[j['tool_call_id']] = tc_create(j['params'], 'add_entity_information', ['entity', 'information'])
                    case 'add_compromised_account':
                        tool_calls[j['tool_call_id']] = tc_create(j['params'], 'add_compromised_account', ['username', 'password', 'context'])
                    case 'update_entity_information':
                        tool_calls[j['tool_call_id']] = tc_create(j['params'], 'update_entity_information', ['entity', 'information'])
                    case 'update_compromised_account':
                        tool_calls[j['tool_call_id']] = tc_create(j['params'], 'update_compromised_account', ['username', 'password', 'context'])
                    case _:
                        raise Exception("unhandled tool-call: " + j['tool_name'])

            case 'executor_next_cmds':
                console.print("Asking Executor for the next step..")
            case 'tool_result':
                assert(j['tool_call_id'] in tool_calls)

                tc = tool_calls[j['tool_call_id']]
                match tc['tool_name']:
                    case 'perform_task':
                        text = f"# {tc['next_step']} ({tc['mitre_attack_tactic']}/{tc['mitre_attack_technique']})\n\n{tc['next_step_context']}\n\n# Result\n{j['result']}"
                        console.print(Panel(text, title="Tool Call: perform_task"))
                    case 'execute_command':
                        text = f"technique: {tc['mitre_attack_technique']}\nprocedure: {tc['mitre_attack_procedure']})\n{tc['command']}\n\n# Result\n{j['result']}"
                        console.print(Panel(text, title="tool_call: execute_command"))
                    case 'add_entity_information':
                        console.print(Panel(f"entity: {tc['entity']}\ninformation: {tc['information']}", title="tool_call: add_entity_information"))
                    case 'add_compromised_account':
                        text = f"user: {tc['username']}\npassword: {tc['password']}\ncontext:{tc['context']}"
                        console.print(Panel(text, title="tool_call: add_compromised_account"))
                    case 'update_entity_information':
                        console.print(Panel(f"entity: {tc['entity']}\ninformation: {tc['information']}", title="tool_call: update_entity_information"))
                    case 'update_compromised_account':
                        console.print(Panel(f"user: {tc['username']}\npassword: {tc['password']}\ncontext:{tc['context']}", title="tool_call: update_compromised_account"))
                    case _:
                        raise Exception("unhandled tool-call: " + j['tool_name'])
                del tool_calls[j['tool_call_id']]
            case 'executor_no_summary':
                console.print(Panel(j['result'], title="Executor Ran Out-of-Rounds, Create Summary"))
            case 'starting test-run':
                pass # just debug output
            case 'history_append':
                pass # we are not that interesting into history during replay
            case 'new knowledge':
                console.print(Panel(j['content'], title="New Knowledge"))
                pass
            case 'executor':
                console.print("Staring new Executor..")
            case 'completed':
                console.print("replay done!")
            case _:
                raise Exception("unhandled: " + j['event'])
            
    if len(tool_calls) > 0:
        console.print(Panel(Pretty(tool_calls), title="Unfinished Tool Calls"))

def main():
    console = Console()

    parser=argparse.ArgumentParser()
    parser.add_argument('input', type=argparse.FileType('r'), help='input file to analyze')
    args = parser.parse_args()

    analyze_replay(console, args.input)

if __name__=='__main__':
    main()
