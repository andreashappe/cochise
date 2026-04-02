#!/usr/bin/python3

import argparse
import matplotlib.pyplot as plt

from rich.console import Console
from statistics import mean

from cochise.analysis.common_analysis import traverse_file

def executor_input_size(console, input_files):

    models = {}

    max_length = 0
    for i in input_files:
        result = traverse_file(i)

        executors = [a for a in result.agents.values() if a.name != 'main']

        for e in executors:
            llm_calls = e.llm_calls['executor_next_cmds']

            model = None
            for i in range(0, len(llm_calls.prompt_tokens)):
                if model is None: # TODO: multi-model support
                    model = llm_calls.models[i]
                else:
                    assert(model == llm_calls.models[i])

                tmp = models.get(model, {})
                if i not in tmp:
                    tmp[i] = [llm_calls.prompt_tokens[i]]
                else:
                    tmp[i].append(llm_calls.prompt_tokens[i])
                models[model] = tmp
                max_length = max(max_length, len(tmp.keys()))

    for model in models.keys():
        x = []
        y = []

        print(f"Model: {model} rounds: {len(models[model].keys())}")
        max_round = len(models[model].keys())
        
        for i in range(max_round):
            x.append(i)
            # IDEA: instead of average, display the range
            y.append(mean(models[model][i]))

        plt.scatter(x, y, marker="*", label=model)

    plt.legend() 
    plt.xlabel('Executor Round')
    plt.xticks(range(0, max_length, 10), range(0, max_length, 10))
    plt.ylabel('Executor Input Size in Tokens')
    plt.savefig('executor_input_size.pdf', format='pdf')
    plt.clf()

def executor_cache_size(console, input_files):

    models = {}

    max_length = 0
    for i in input_files:
        result = traverse_file(i)

        executors = [a for a in result.agents.values() if a.name != 'main']

        for e in executors:
            llm_calls = e.llm_calls['executor_next_cmds']

            model = None
            for i in range(0, len(llm_calls.cached_tokens)):
                if model is None: # TODO: multi-model support
                    model = llm_calls.models[i]
                else:
                    assert(model == llm_calls.models[i])

                tmp = models.get(model, {})
                if i not in tmp:
                    tmp[i] = [llm_calls.cached_tokens[i]]
                else:
                    tmp[i].append(llm_calls.cached_tokens[i])
                models[model] = tmp
                max_length = max(max_length, len(tmp.keys()))

    for model in models.keys():
        x = []
        y = []

        print(f"Model: {model} rounds: {len(models[model].keys())}")
        max_round = len(models[model].keys())
        
        for i in range(max_round):
            x.append(i)
            # IDEA: instead of average, display the range
            y.append(mean(models[model][i]))

        plt.scatter(x, y, marker="*", label=model)

    plt.legend() 
    plt.xlabel('Executor Round')
    plt.xticks(range(0, max_length, 10), range(0, max_length, 10))
    plt.ylabel('Executor Cache Size in Tokens')
    plt.savefig('executor_cache_size.pdf', format='pdf')
    plt.clf()

    return None


def planner_input_size(console, input_files):

    models = {}
    max_length = 0

    for i in input_files:
        result = traverse_file(i)

        llm_calls = result.agents['main'].llm_calls['planner_task_selection']

        model = None
        for i in range(0, len(llm_calls.prompt_tokens)):
            if model is None: # TODO: multi-model support
                model = llm_calls.models[i]
            else:
                assert(model == llm_calls.models[i])

            tmp = models.get(model, {})
            if i not in tmp:
                tmp[i] = [llm_calls.prompt_tokens[i]]
            else:
                tmp[i].append(llm_calls.prompt_tokens[i])
            models[model] = tmp
            max_length = max(max_length, len(tmp.keys()))

    for model in models.keys():
        x = []
        y = []

        print(f"Model: {model} rounds: {len(models[model].keys())}")
        max_round = len(models[model].keys())
        
        for i in range(max_round):
            x.append(i)
            y.append(mean(models[model][i]))

        plt.scatter(x, y, marker="*", label=model)

    plt.legend() 
    plt.xlabel('Planner Task-Round')
    plt.xticks(range(0, max_length, 10), range(0, max_length, 10))
    plt.ylabel('Planner Input History Size in Tokens')
    plt.savefig('planner_input_size.pdf', format='pdf')
    plt.clf()


def llm_duration_vs_tokens(console, input_files):

    models = {}

    for i in input_files:
        result = traverse_file(i)

        model = None
        for a in result.agents.values():
            for llm_call in a.llm_calls.values():
                for i in range(0, len(llm_call.models)):
                    if model is None: # TODO: multi-model support
                        model = llm_call.models[i]
                    else:
                        assert(model == llm_call.models[i])

                    tmp = models.get(model, { 'input': [], 'output': [], 'duration': [], 'price': [] })

                    tmp['input'].append(llm_call.prompt_tokens[i])
                    tmp['output'].append(llm_call.completion_tokens[i])
                    tmp['price'].append(llm_call.cost[i])
                    tmp['duration'].append(llm_call.duration[i])

                    models[model] = tmp

    # input tokens vs duration
    for model, values in models.items():
        x = []
        y = []

        assert(len(values['input']) == len(values['duration']))
        for i in range(0, len(values['input'])):
            x.append(values['input'][i])
            y.append(values['duration'][i])

        plt.scatter(x, y, marker="*", label=model)

    plt.xlabel('Input Tokens)')
    plt.ylabel('Query Duration in Seconds')
    plt.legend()
    plt.savefig('input_tokens_vs_duration.pdf', format='pdf')
    plt.clf()

    # output tokens vs duration
    for model, values in models.items():
        x = []
        y = []

        assert(len(values['output']) == len(values['duration']))
        for i in range(0, len(values['output'])):
            x.append(values['output'][i])
            y.append(values['duration'][i])

        plt.scatter(x, y, marker="*", label=model)

    plt.xlabel('Output Tokens)')
    plt.ylabel('Query Duration in Seconds')
    plt.legend()
    plt.savefig('output_tokens_vs_duration.pdf', format='pdf')
    plt.clf()

    # input tokens vs price
    for model, values in models.items():
        x = []
        y = []

        assert(len(values['input']) == len(values['price']))
        for i in range(0, len(values['input'])):
            x.append(values['input'][i])
            y.append(values['price'][i])

        plt.scatter(x, y, marker="*", label=model)

    plt.xlabel('Input Tokens)')
    plt.ylabel('Query Price')
    plt.legend()
    plt.savefig('input_tokens_vs_price.pdf', format='pdf')
    plt.clf()


    # output tokens vs price
    for model, values in models.items():
        x = []
        y = []

        assert(len(values['output']) == len(values['price']))
        for i in range(0, len(values['output'])):
            x.append(values['output'][i])
            y.append(values['price'][i])

        plt.scatter(x, y, marker="*", label=model)

    plt.xlabel('Output Tokens)')
    plt.ylabel('Query Price')
    plt.legend()
    plt.savefig('output_tokens_vs_price.pdf', format='pdf')
    plt.clf()


analysis_functions = {
    'planner_input_size': planner_input_size,
    'llm_duration_vs_tokens': llm_duration_vs_tokens,
    'executor_input_size': executor_input_size,
    'executor_cache_size': executor_cache_size,
}

def main() -> None:
    console = Console()

    parser=argparse.ArgumentParser()
    parser.add_argument('analysis', choices=analysis_functions.keys(), help='type of analysis to perform')
    parser.add_argument('input', type=argparse.FileType('r'), nargs='+', help='input file to analyze')
    args = parser.parse_args()

    if args.analysis in analysis_functions.keys():
        analysis_functions[args.analysis](console, args.input)
    else:
        console.print(f"Unknown analysis type: {args.analysis}")
        exit(1)

if __name__=='__main__':
    main()