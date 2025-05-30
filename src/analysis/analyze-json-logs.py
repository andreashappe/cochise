#!/usr/bin/python3

import argparse

from common import traverse_file, my_mean, my_std_dev

from rich.console import Console
from rich.table import Table

def calc_costs(model, input_tokens, output_tokens, reasoning_tokens, cached_tokens):
    match model:
        case 'o1-2024-12-17':
            return input_tokens/1_000_000*15 - cached_tokens/1_000_000*7.5 + output_tokens/1_000_000*60
        case 'gpt-4o-2024-08-06':
            return input_tokens/1_000_000*2.5 - cached_tokens/1_000_000*1.25 + output_tokens/1_000_000*10
        case _:
            print(f"Unknown model {model} for cost calculation")
            return 0.0

def analysis_run_overview(console, input_files):
    table = Table(title=f"Run Information")

    table.add_column("Filename", justify="right", style="cyan", no_wrap=True)
    table.add_column("Model", style="magenta")
    table.add_column("Duration", justify="right", style="green")
    table.add_column("Rounds", justify="right", style="green")
    table.add_column("Mean Executor-Calls/Round", justify="right", style="green")
    table.add_column("Dev Executor-Calls/Round", justify="right", style="green")
    table.add_column("Mean Commands/Round", justify="right", style="green")
    table.add_column("Dev Commands/Round", justify="right", style="green")
    table.add_column("Planner Input", justify="right", style="green")
    table.add_column("Planner Output", justify="right", style="green")
    table.add_column("Exeuctor Input", justify="right", style="green")
    table.add_column("Executor Output", justify="right", style="green")
    table.add_column("Est. Cost", justify="right", style="green")

    valid = 0
    invalid = 0

    for i in args.input:
        result = traverse_file(i)

        if result.duration > 60*60*1.5 and 'unknown-model' not in result.models and len(result.rounds) > 0:

            executor_calls = [r.executor_llm_calls for r in result.rounds]
            tool_calls = [r.tool_calls for r in result.rounds]

            planner_input = 0
            planner_output = 0
            planner_reasoning = 0
            planner_cached = 0
            executor_input = 0
            executor_output = 0
            executor_reasoning = 0
            executor_cached = 0

            cost = 0
            for prompt, data in result.tokens.items():
                match prompt:
                    case 'strategy_update' | 'strategy_next_task':
                        planner_input += data.prompt_tokens
                        planner_output += data.completion_tokens
                        planner_reasoning += data.reasoning_tokens
                        planner_cached += data.cached_tokens
                        cost += calc_costs(data.model, data.prompt_tokens, data.completion_tokens, data.reasoning_tokens, data.cached_tokens)
                    case _:
                        executor_input += data.prompt_tokens
                        executor_output += data.completion_tokens
                        executor_reasoning += data.reasoning_tokens
                        executor_cached += data.cached_tokens
                        cost += calc_costs(data.model, data.prompt_tokens, data.completion_tokens, data.reasoning_tokens, data.cached_tokens)

            table.add_row(
                result.filename,
                result.models_str(),
                result.duration_str(),
                str(len(result.rounds)),
                str(round(my_mean(executor_calls),2)),
                str(round(my_std_dev(executor_calls),2)),
                str(round(my_mean(tool_calls), 2)),
                str(round(my_std_dev(tool_calls), 2)),
                str(round(planner_input / 1000, 2)),  # Convert to kTokens
                str(round(planner_output / 1000, 2)),  # Convert to kTokens
                str(round(executor_input / 1000, 2)),  # Convert to kTokens
                str(round(executor_output / 1000, 2)),  # Convert to kTokens
                str(round(cost, 2))  # Cost in USD
            )
            valid += 1
        else:
            print(f"- {result.filename} has no valid models or strategy rounds")
            invalid += 1

    console = Console() 
    console.print(table)
    console.print(f"Valid runs: {valid} Invalid runs: {invalid}") 

def analysis_run_stats(console, input_files):
    table = Table(title=f"Run Information")

    table.add_column("Filename", justify="right", style="cyan", no_wrap=True)
    table.add_column("Model", style="magenta")
    table.add_column("Duration", justify="right", style="green")
    table.add_column("Rounds", justify="right", style="green")
    table.add_column("Mean Executor-Calls/Round", justify="right", style="green")
    table.add_column("Dev Executor-Calls/Round", justify="right", style="green")
    table.add_column("Mean Commands/Round", justify="right", style="green")
    table.add_column("Dev Commands/Round", justify="right", style="green")

    valid = 0
    invalid = 0

    for i in args.input:
        result = traverse_file(i)

        if result.duration > 600 and 'unknown-model' not in result.models and len(result.rounds) > 0:

            executor_calls = [r.executor_llm_calls for r in result.rounds]
            tool_calls = [r.tool_calls for r in result.rounds]

            table.add_row(
                result.filename,
                result.models_str(),
                result.duration_str(),
                str(len(result.rounds)),
                str(round(my_mean(executor_calls),2)),
                str(round(my_std_dev(executor_calls),2)),
                str(round(my_mean(tool_calls), 2)),
                str(round(my_std_dev(tool_calls), 2))
            )
            valid += 1
        else:
            print(f"- {result.filename} has no valid models or strategy rounds")
            invalid += 1

    console = Console() 
    console.print(table)
    console.print(f"Valid runs: {valid} Invalid runs: {invalid}") 

def analysis_token_usage(console, input_files):
    for i in input_files:
        results = traverse_file(i)

        table = Table(title=f"Run Information: {results.filename}")
        table.add_column("Prompt", justify="right", style="cyan", no_wrap=True)
        table.add_column("Model", style="magenta")
        table.add_column("Total Tokens", justify="right", style="green")
        table.add_column("Prompt Tokens", justify="right", style="green")
        table.add_column("Completions Tokens", justify="right", style="green")
        table.add_column("Reasoning Tokens", justify="right", style="green")
        table.add_column("Cached Tokens", justify="right", style="green")
        table.add_column("Duration", justify="right", style="green")

        for event ,acc in results.tokens.items():
            table.add_row(
                event,
                acc.model,
                str(acc.total_tokens),
                str(acc.prompt_tokens),
                str(acc.completion_tokens),
                str(acc.reasoning_tokens),
                str(acc.cached_tokens),
                str(round(acc.duration, 2))
            )
        console.print(table)

if __name__=='__main__':

    console = Console()

    parser=argparse.ArgumentParser()
    parser.add_argument('analysis', choices=['run-stats', 'token-usage', 'run-overview'], help='type of analysis to perform')
    parser.add_argument('input', type=argparse.FileType('r'), nargs='+', help='input file to analyze')
    args = parser.parse_args()

    match args.analysis:
        case 'run-stats':
            analysis_run_stats(console, args.input)
        case 'token-usage':
            analysis_token_usage(console, args.input)
        case 'run-overview':
            analysis_run_overview(console, args.input)
        case _:
            print(f"Unknown analysis type: {args.analysis}")
            exit(1)
