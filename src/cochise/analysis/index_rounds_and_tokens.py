from rich.console import Console
from typing import List

from cochise.analysis.common_analysis import traverse_file, my_mean, my_std_dev, OutputTable

def index_rounds_and_tokens(console:Console, input_files, filter_result) -> List[OutputTable]:
    valid = 0
    invalid = 0
    rows : List[List[str]] = []

    all_durations = []
    all_tasks_executor = []
    all_commands = []
    all_planner_input = []
    all_planner_output = []
    all_planner_costs = []
    all_executor_input = []
    all_executor_output = []
    all_executor_costs = []

    for i in input_files:
        result = traverse_file(i)

        if filter_result(result):

            main = result.agents['main']
            executors = [a for a in result.agents.values() if a.name != 'main']

            tasks_executor = main.tool_calls['perform_task'].count
            commands_executed = [r.tool_calls['execute_command'].count for r in executors]

            planner_input = sum([(sum(i.prompt_tokens) - sum(i.cached_tokens)) for i in main.llm_calls.values()])
            planner_output = sum([sum(i.completion_tokens) for i in main.llm_calls.values()])
            planner_costs = sum([sum(i.cost) for i in main.llm_calls.values()])

            executor_input = 0
            executor_output = 0
            executor_costs = 0

            for e in executors:
                executor_input += sum([(sum(i.prompt_tokens) - sum(i.cached_tokens)) for i in e.llm_calls.values()])
                executor_output += sum([sum(i.completion_tokens) for i in e.llm_calls.values()])
                executor_costs += sum([sum(i.cost) for i in e.llm_calls.values()])

            rows.append([
                result.filename,
                result.models_str(),
                result.duration_str(),
                str(tasks_executor),
                f"{round(my_mean(commands_executed),2)} +/- {round(my_std_dev(commands_executed),2)}",
                str(round(planner_input / 1000, 2)),  # Convert to kTokens
                str(round(planner_output / 1000, 2)),  # Convert to kTokens
                str(round(planner_costs, 2)),  # Cost in USD
                str(round(executor_input / 1000, 2)),  # Convert to kTokens
                str(round(executor_output / 1000, 2)),  # Convert to kTokens
                str(round(executor_costs, 2))  # Cost in USD
            ])
            valid += 1

            all_durations.append(result.duration)
            all_tasks_executor.append(tasks_executor)
            all_commands.extend(commands_executed)

            all_planner_input.append(planner_input/1000)
            all_planner_output.append(planner_output/1000)
            all_planner_costs.append(planner_costs)

            all_executor_input.append(executor_input/1000)
            all_executor_output.append(executor_output/1000)
            all_executor_costs.append(executor_costs)
        else:
            console.print(f"- {result.filename} has no valid models or strategy rounds")
            invalid += 1

    console.print(f"Valid runs: {valid} Invalid runs: {invalid}") 
    return [OutputTable(
        title="Run Information (Input/Output in kTokens, Cost in USD (or EUR?))",
        headers = ["Filename", "Model", "Duration", "Tasks(Exec)", "Commands/Exec (Mean/Dev)", "Planner Input", "Planner Output", "Planner Cost", "Exeuctor Input", "Executor Output", "Executor Cost"],
        footers = ["Average", "",
                   str(round(my_mean(all_durations), 2)),
                   str(round(my_mean(all_tasks_executor), 2)),
                    f"{round(my_mean(all_commands),2)} +/- {round(my_std_dev(all_commands),2)}",
                    f"{round(my_mean(all_planner_input), 2)} +/- {round(my_std_dev(all_planner_input), 2)}",
                    f"{round(my_mean(all_planner_output), 2)} +/- {round(my_std_dev(all_planner_output), 2)}",
                    f"{round(my_mean(all_planner_costs), 2)} +/- {round(my_std_dev(all_planner_costs), 2)}",
                    f"{round(my_mean(all_executor_input), 2)} +/- {round(my_std_dev(all_executor_input), 2)}",
                    f"{round(my_mean(all_executor_output), 2)} +/- {round(my_std_dev(all_executor_output), 2)}",
                    f"{round(my_mean(all_executor_costs), 2)} +/- {round(my_std_dev(all_executor_costs), 2)}"],
        rows = rows
    )]
