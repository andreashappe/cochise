#!/usr/bin/python3

import argparse

from common import traverse_file

from rich.console import Console
from rich.table import Table

if __name__=='__main__':

    console = Console()

    parser=argparse.ArgumentParser()
    parser.add_argument('input', type=argparse.FileType('r'), help='input file to analyze')
    args = parser.parse_args()

    results = traverse_file(args.input)

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