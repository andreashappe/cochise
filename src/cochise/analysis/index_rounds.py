from rich.console import Console
from typing import List

from analysis.common_analysis import traverse_file, my_mean, my_std_dev, OutputTable


def index_rounds(console:Console, input_files, filter_result):
    valid = 0
    invalid = 0

    rows : List[List[str]] = []

    for i in input_files:
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
            console.print(f"- {result.filename} has no valid models or strategy rounds")
            invalid += 1

    console.print(f"Valid runs: {valid} Invalid runs: {invalid}") 
    return [OutputTable(
        title =f"Run Information",
        headers = ["Filename", "Model", "Duration", "Rounds", "Mean Executor-Calls/Round", "Dev Executor-Calls/Round", "Mean Commands/Round", "Dev Commands/Round"],
        rows = rows
    )]
