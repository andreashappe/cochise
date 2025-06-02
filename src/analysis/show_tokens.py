from rich.console import Console
from typing import List

from analysis.common_analysis import traverse_file, OutputTable

def show_tokens(console:Console, input_files, filter_results):

    tables : List[OutputTable] = []

    for i in input_files:
        results = traverse_file(i)
        rows : List[List[str]] = []

        if filter_results(results):
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
            console.print(f"{results.filename} duration <= minimum-duration")

    return tables
