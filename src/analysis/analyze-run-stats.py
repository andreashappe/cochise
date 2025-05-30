#!/usr/bin/python3

import argparse

from common import traverse_file, my_mean, my_std_dev
from rich.console import Console
from rich.table import Table

if __name__=='__main__':

    console = Console()

    parser=argparse.ArgumentParser()
    parser.add_argument('input', type=argparse.FileType('r'), nargs='+', help='input file to analyze')
    args = parser.parse_args()

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

    print(f"Valid runs: {valid} Invalid runs: {invalid}") 