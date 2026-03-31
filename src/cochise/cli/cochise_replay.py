#!/usr/bin/python3

import argparse
import json

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.pretty import Pretty


def analyze_replay(console, file):

    ptt:int = 0

    for line in file:
        j = json.loads(line)

        if 'result' in j:
            result = j['result']

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
                # TODO: create a collection so that we can output tool_call + tool_result at the same time
                # TODO: also output if there is a missing tool-result for a tool-call at the end (or a tool-result without tool-acll)
                match j['tool_name']:
                    case 'perform_task':
                        p = j['params']
                        tactic = p['mitre_attack_tactic']
                        technique = p['mitre_attack_technique']
                        next_step = p['next_step']
                        context = p['next_step_context']

                        text = f"# {next_step} ({tactic}/{technique})\n\n{context}"
                        console.print(Panel(Markdown(text), title="Perform Task"))
                    case 'execute_command':
                        p = j['params']
                        technique = p['mitre_attack_technique']
                        procedure = p['mitre_attack_procedure']
                        command = p['command']
                        console.print(Panel(command, title="tool_call: execute_command"))
                    case 'add_entity_information':
                        p = j['params']
                        entity = p['entity']
                        information = p['information']
                        console.print(Panel(f"entity: {entity}\ninformation:{information}", title=f"tool_call: add_entity_information"))
                    case 'add_compromised_account':
                        p = j['params']
                        username = p['username']
                        password = p['password']
                        context = p['context']
                        text = f"user: {username}\npassword: {password}\ncontext:{context}"
                        console.print(Panel(text, title=f"tool_call: update_compromised_account"))
                    case 'update_entity_information':
                        p = j['params']
                        entity = p['entity']
                        information = p['information']
                        console.print(Panel(f"entity: {entity}\ninformation: {information}", title=f"tool_call: add_entity_information"))
                    case 'update_compromised_account':
                        p = j['params']
                        username = p['username']
                        password = p['password']
                        context = p['context']
                        text = f"user: {username}\npassword: {password}\ncontext:{context}"
                        console.print(Panel(text, title=f"tool_call: update_compromised_account"))
                    case _:
                     raise Exception("unhandled tool-call: " + j['tool_name'])

            case 'executor_next_cmds':
                console.print("Asking Executor for the next step..")
            case 'tool_result':
                console.print(Panel(j['result'], title="tool_result"))
            case 'executor_no_summary':
                console.print(Panel(j['result'], title="Executor Ran Out-of-Rounds, Create Summary"))
            case 'compact_history':
                console.print(Panel(j['result'], title="Compacted History"))
            case 'starting test-run':
                pass # just debug output
            case 'history_append':
                pass # we are not that interesting into history during replay
            case 'new knowledge':
                # TODO: why is this empty?
                # console.print(Panel(j['content'], title="New Knowledge"))
                pass
            case 'executor':
                console.print("Staring new Executor..")
            case 'completed':
                console.print("replay done!")
            case _:
                raise Exception("unhandled: " + j['event'])


def main():
    console = Console()

    parser=argparse.ArgumentParser()
    parser.add_argument('input', type=argparse.FileType('r'), help='input file to analyze')
    args = parser.parse_args()

    analyze_replay(console, args.input)

if __name__=='__main__':
    main()