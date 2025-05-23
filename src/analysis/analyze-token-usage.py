#!/usr/bin/python3

import argparse
import json

from pathlib import Path

from rich.console import Console
from rich.table import Table

def analyzse_usage_metadata(results, event, j):
    if event in results.keys():
        assert(results[event]['model_name'] == j['costs']['model_name'])
        results[event]['duration'] += j['duration']
        results[event]['total'] += j['costs']['usage_metadata']['total_tokens']
        results[event]['prompt'] += j['costs']['usage_metadata']['input_tokens']
        results[event]['completions'] += j['costs']['usage_metadata']['output_tokens']
        results[event]['reasoning'] += 0
        results[event]['cached'] += 0

    else:
        results[event] = {
            'duration': j['duration'],
            'model_name': j['costs']['model_name'],
            'event': event,
            'total': j['costs']['usage_metadata']['total_tokens'],
            'prompt': j['costs']['usage_metadata']['input_tokens'],
            'completions': j['costs']['usage_metadata']['output_tokens'],
            'reasoning': 0,
            'cached': 0
        }

def analyzse_token_usage(results, event, j):
    if j['costs']['token_usage']['completion_tokens_details'] != None and 'reasoning' in j['costs']['token_usage']['completion_tokens_details']:
        reasoning_tokens = j['costs']['token_usage']['completion_tokens_details']['reasoning_tokens']
    else:
        reasoning_tokens = 0
    
    if event in results.keys():
        assert(results[event]['model_name'] == j['costs']['model_name'])
        results[event]['duration'] += j['duration']
        results[event]['total'] += j['costs']['token_usage']['total_tokens']
        results[event]['prompt'] += j['costs']['token_usage']['prompt_tokens']
        results[event]['completions'] += j['costs']['token_usage']['completion_tokens']
        results[event]['reasoning'] += reasoning_tokens
        results[event]['cached'] += j['costs']['token_usage']['prompt_tokens_details']['cached_tokens']

    else:
        results[event] = {
            'duration': j['duration'],
            'model_name': j['costs']['model_name'],
            'event': event,
            'total': j['costs']['token_usage']['total_tokens'],
            'prompt': j['costs']['token_usage']['prompt_tokens'],
            'completions': j['costs']['token_usage']['completion_tokens'],
            'reasoning': reasoning_tokens,
            'cached': j['costs']['token_usage']['prompt_tokens_details']['cached_tokens'],
        }


def analyzse_file(filename):

    results = {}

    with open(filename, 'r') as file:
        for line in file:
            j = json.loads(line)

            if 'costs' in j:
                event = j['event']

                if 'token_usage' in j['costs']:
                    analyzse_token_usage(results, event, j)
                elif 'usage_metadata' in j['costs']:
                    # if we don't have token usage, we can still get some information from here
                    analyzse_usage_metadata(results, event, j)


    return results

if __name__=='__main__':

    console = Console()

    parser=argparse.ArgumentParser()
    parser.add_argument('-i','--input')
    args = parser.parse_args()

    filename = Path(args.input).stem
    results = analyzse_file(args.input)

    table = Table(title=f"Token Usage for {filename}")

    table.add_column("Prompt", justify="right", style="cyan", no_wrap=True)
    table.add_column("Model", style="magenta")
    table.add_column("Total Tokens", justify="right", style="green")
    table.add_column("Prompt Tokens", justify="right", style="green")
    table.add_column("Completions Tokens", justify="right", style="green")
    table.add_column("Reasoning Tokens", justify="right", style="green")
    table.add_column("Cached Tokens", justify="right", style="green")
    table.add_column("Duration", justify="right", style="green")

    for i in results.values():
        table.add_row(
            i['event'],
            i['model_name'],
            str(i['total']),
            str(i['prompt']),
            str(i['completions']),
            str(i['reasoning']),
            str(i['cached']),
            str(i['duration'])
        )
    console.print(table)