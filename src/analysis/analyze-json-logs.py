#!/usr/bin/python3

import argparse

from common import traverse_file, my_mean, my_std_dev
from dataclasses import dataclass, field
from rich.console import Console
from rich.table import Table
from typing import Dict, List, Set

@dataclass
class OutputTable:
    title: str
    headers: List[str]
    rows: List[List[str]]

def calc_costs(model, input_tokens, output_tokens, reasoning_tokens, cached_tokens):
    match model:
        case 'o1-2024-12-17':
            return input_tokens/1_000_000*15 - cached_tokens/1_000_000*7.5 + output_tokens/1_000_000*60
        case 'gpt-4o-2024-08-06':
            return input_tokens/1_000_000*2.5 - cached_tokens/1_000_000*1.25 + output_tokens/1_000_000*10
        case 'deepseek-chat':
            return input_tokens/1_000_000*0.27 - cached_tokens/1_000_000*0.2 + output_tokens/1_000_000*1.1
        case 'models/gemini-2.5-flash-preview-04-17':
            return input_tokens/1_000_000*0.15 - cached_tokens/1_000_000*(0.15-0.0375) + output_tokens/1_000_000*0.6 + reasoning_tokens/1_000_000*3.5
        case _:
            print(f"Unknown model {model} for cost calculation")
            return 0.0

def analysis_run_overview(console, input_files, filter_result) -> List[OutputTable]:
    valid = 0
    invalid = 0
    rows : List[List[str]] = []

    for i in args.input:
        result = traverse_file(i)

        if filter_result(result):

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

            rows.append([
                result.filename,
                result.models_str(),
                result.duration_str(),
                str(len(result.rounds)),
                f"{round(my_mean(executor_calls),2)} +/- {round(my_std_dev(executor_calls),2)}",
                f"{round(my_mean(tool_calls), 2)} +/- {round(my_std_dev(tool_calls), 2)}",
                str(round(planner_input / 1000, 2)),  # Convert to kTokens
                str(round(planner_output / 1000, 2)),  # Convert to kTokens
                str(round(executor_input / 1000, 2)),  # Convert to kTokens
                str(round(executor_output / 1000, 2)),  # Convert to kTokens
                str(round(cost, 2))  # Cost in USD
            ])
            valid += 1
        else:
            print(f"- {result.filename} has no valid models or strategy rounds")
            invalid += 1

    print(f"Valid runs: {valid} Invalid runs: {invalid}") 
    return [OutputTable(
        title="Run Information",
        headers = ["Filename", "Model", "Duration", "Rounds", "Executor-Calls/Round (Mean/Dev)", "Commands/Round (Mean/Dev)", "Planner Input", "Planner Output", "Exeuctor Input", "Executor Output", "Est. Cost"],
        rows = rows
    )]

def analysis_run_stats(console, input_files, filter_result):
    valid = 0
    invalid = 0

    rows : List[List[str]] = []

    for i in args.input:
        result = traverse_file(i)

        if filter_result(result):

            executor_calls = [r.executor_llm_calls for r in result.rounds]
            tool_calls = [r.tool_calls for r in result.rounds]

            rows.append([
                result.filename,
                result.models_str(),
                result.duration_str(),
                str(len(result.rounds)),
                str(round(my_mean(executor_calls),2)),
                str(round(my_std_dev(executor_calls),2)),
                str(round(my_mean(tool_calls), 2)),
                str(round(my_std_dev(tool_calls), 2))
            ])
            valid += 1
        else:
            print(f"- {result.filename} has no valid models or strategy rounds")
            invalid += 1

    print(f"Valid runs: {valid} Invalid runs: {invalid}") 
    return [OutputTable(
        title =f"Run Information",
        headers = ["Filename", "Model", "Duration", "Rounds", "Mean Executor-Calls/Round", "Dev Executor-Calls/Round", "Mean Commands/Round", "Dev Commands/Round"],
        rows = rows
    )]

def analysis_token_usage(console, input_files):

    tables : List[OutputTable] = []

    for i in input_files:
        results = traverse_file(i)
        rows : List[List[str]] = []

        if filter_result(results):
            for event ,acc in results.tokens.items():
                rows.append([
                    event,
                    acc.model,
                    str(acc.total_tokens),
                    str(acc.prompt_tokens),
                    str(acc.completion_tokens),
                    str(acc.reasoning_tokens),
                    str(acc.cached_tokens),
                    str(round(acc.duration, 2))
                ])

            tables.append(OutputTable(
                title=f"Run Information: {results.filename}",
                headers=["Prompt", "Model", "Total Tokens", "Prompt Tokens", "Completions Tokens", "Reasoning Tokens", "Cached Tokens", "Duration"],
                rows=rows
            ))
        else:
            print(f"{results.filename} duration <= minimum-duration")

    return tables

analysis_functions = {
        'index-rounds': analysis_run_stats,
        'index-rounds-and-tokens': analysis_run_overview,
        'show-tokens': analysis_token_usage
}

if __name__=='__main__':

    console = Console()

    parser=argparse.ArgumentParser()
    parser.add_argument('analysis', choices=analysis_functions.keys(), help='type of analysis to perform')
    parser.add_argument('input', type=argparse.FileType('r'), nargs='+', help='input file to analyze')
    parser.add_argument('--latex', action='store_true')
    parser.add_argument('--duration-min', default=600, type=int)
    parser.add_argument('--model-eq', default=None, type=str)
    parser.add_argument('--model-substr', default=None, type=str)
    args = parser.parse_args()

    def filter_result(result):
        if args.model_eq != None:
            if ','.join(sorted(result.models)) != args.model_eq:
                return False
        if args.model_substr != None:
            if args.model_substr not in (','.join(sorted(result.models))):
                return False
        return result.duration >= args.duration_min

    console = Console() 
    results = []

    if args.analysis in analysis_functions.keys():
        results = analysis_functions[args.analysis](console, args.input, filter_result)
    else:
        console.print(f"Unknown analysis type: {args.analysis}")
        exit(1)

    if args.latex == True:
        print("now doing latex output...")

        for table in results:
            print("\\begin{tabular}{c%s}" % ('r'*len(table.headers)))
            print("\\toprule")
            print(" & ".join(map(lambda i: "\\textbf{%s}" % (i), table.headers)), "\\\\")
            print("\\midrule")
            for r in table.rows:
                print( " & ".join(r), "\\\\\\hdashline")
            print("\\bottomrule")
            print("\\end{tabular}")
    else:
        for table in results:
            t = Table(title=table.title)
            for h in table.headers:
                t.add_column(h)
            for r in table.rows:
                t.add_row(*r)
            console.print(t)

