#!/usr/bin/python3

import argparse
import json
import matplotlib.pyplot as plt

from rich.console import Console
from statistics import mean

from analysis.common_analysis import LLMAccounting, add_token_usage, add_token_usage_metadata

def executor_size(console, input_files):

    models = {}

    for file in input_files:
        round = 1
        for line in file:
            j = json.loads(line)
            event = j['event']
            match event:
                case 'strategy_next_task':
                    round =1 
                case 'executor_next_cmds':
                    assert('costs' in j)

                    # this means this was a LLM callout
                    if 'costs' in j:
                        # add model name to the run metadata
                        if 'model_name' in j['costs']:
                            model = j['costs']['model_name']
                        else:
                            model = 'unknown-model'

                        if 'token_usage' in j['costs']:
                            prompt_tokens = j['costs']['token_usage']['prompt_tokens']
                            cached_tokens = j['costs']['token_usage']['prompt_tokens_details']['cached_tokens'] if 'prompt_tokens_details' in j['costs']['token_usage'] and j['costs']['token_usage']['prompt_tokens_details'] != None else 0
                        elif 'usage_metadata' in j['costs'] and j['costs']['usage_metadata'] is not None:
                            if 'total_token_count' in j['costs']['usage_metadata']:
                                prompt_tokens = j['costs']['usage_metadata']['prompt_token_count']
                                cached_tokens = j['costs']['usage_metadata']['cached_content_token_count']
                            else:
                                prompt_tokens = j['costs']['usage_metadata']['input_tokens']
                                cached_tokens = j['costs']['usage_metadata']['input_token_details']['cache_read'] if 'input_token_details' in j['costs']['usage_metadata'] else 0

                        if model != 'qwen3:235b-a22b' and model != 'unknown-model':
                            if model not in models:
                                models[model] = {}
                            if round not in models[model]:
                                models[model][round] = []
                            models[model][round].append(prompt_tokens)
                            round += 1

    colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray']

    for model in models.keys():
        x = []
        y = []

        print(f"Model: {model} rounds: {len(models[model].keys())}")
        max_round = len(models[model].keys())
        
        for i in range(max_round):
            x.append(i+1)
            y.append(mean(models[model][i+1]))

        plt.scatter(x, y, marker="*", label=model, color=colors.pop(0))

    plt.legend() 
    plt.xlabel('Executor Round')
    plt.xticks(range(0, 10, 1), range(0, 10, 1))
    plt.ylabel('Executor Input Size (Tokens)')
    plt.savefig('executor_input_size.png')
    plt.clf()

    return None

def ptt_size(console, input_files):

    models = {}

    for file in input_files:
        round = 1
        for line in file:
            j = json.loads(line)
            event = j['event']
            match event:
                case 'strategy_update':
                    assert('costs' in j)

                    # this means this was a LLM callout
                    if 'costs' in j:
                        # add model name to the run metadata
                        if 'model_name' in j['costs']:
                            model = j['costs']['model_name']
                        else:
                            model = 'unknown-model'

                        if 'token_usage' in j['costs']:
                            size = j['costs']['token_usage']['completion_tokens']
                        elif 'usage_metadata' in j['costs'] and j['costs']['usage_metadata'] is not None:
                            if 'total_token_count' in j['costs']['usage_metadata']:
                                size = j['costs']['usage_metadata']['candidates_token_count']
                            else:
                                size = j['costs']['usage_metadata']['output_tokens']

                        if model != 'qwen3:235b-a22b' and model != 'unknown-model':
                            if model not in models:
                                models[model] = {}
                            if round not in models[model]:
                                models[model][round] = []
                            models[model][round].append(size)
                            print(f"Model: {model} size: {size}")
                            round += 1

    print(str(models))

    colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray']

    for model in models.keys():
        x = []
        y = []

        print(f"Model: {model} rounds: {len(models[model].keys())}")
        max_round = len(models[model].keys())
        
        for i in range(max_round):
            x.append(i+1)
            y.append(mean(models[model][i+1]))

        plt.scatter(x, y, marker="*", label=model, color=colors.pop(0))

    plt.legend() 
    plt.xlabel('Planner Round')
    plt.xticks(range(0, 100, 10), range(0, 100, 10))
    plt.ylabel('State/Pentest-Task_Tree Size (Bytes)')
    plt.savefig('state_size.png')
    plt.clf()

    return None

def llm_performance(console, input_files):

    results = {}

    for file in input_files:
        for line in file:
            j = json.loads(line)

            # this means this was a LLM callout
            if 'costs' in j:
                # add model name to the run metadata
                if 'model_name' in j['costs']:
                    model = j['costs']['model_name']
                else:
                    model = 'unknown-model'

                if model == 'unknown-model' or model == 'qwen3:235b-a22b' or model == 'qwen3:32b':
                    continue  # skip unknown models

                coll = results.get(model, [])
                acc = LLMAccounting(model=model)
                if 'token_usage' in j['costs']:
                    add_token_usage(acc, j)
                elif 'usage_metadata' in j['costs']:
                    # if we don't have token usage, we can still get some information from here
                    add_token_usage_metadata(acc, j)
                coll.append(acc)
                results[model] = coll
    
    for model, accs in results.items():
        x = []
        y = []

        for acc in accs:
            # remove outliers
            if acc.duration <= 500 and acc.total_tokens <= 100000:
                x.append(acc.total_tokens)
                y.append(acc.duration)

        plt.scatter(x, y, marker="*", label=model)

    plt.scatter(x, y, marker="*")
    plt.xlabel('Total Token Count of Query (Sum of Prompt and Completion Tokens)')
    plt.ylabel('Query Round-Trip Time in Seconds')
    plt.legend()
    plt.savefig('tokens_vs_duration.png')
    plt.clf()


analysis_functions = {
    'ptt_size': ptt_size,
    'llm_performance': llm_performance,
    'executor_size': executor_size,
}

if __name__=='__main__':

    console = Console()

    parser=argparse.ArgumentParser()
    parser.add_argument('analysis', choices=analysis_functions.keys(), help='type of analysis to perform')
    parser.add_argument('input', type=argparse.FileType('r'), nargs='+', help='input file to analyze')
    args = parser.parse_args()

    if args.analysis in analysis_functions.keys():
        results = analysis_functions[args.analysis](console, args.input)
    else:
        console.print(f"Unknown analysis type: {args.analysis}")
        exit(1)