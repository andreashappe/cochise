from rich.console import Console

from analysis.common_analysis import my_mean, traverse_file, OutputTable

def index_duration(console:Console, input_files, filter_result):

    rows = []

    all_planner = []
    all_executor = []
    all_command = []

    for file in input_files:
        result = traverse_file(file)

        if filter_result(result):
            overall_duration = result.duration
            planner_duration = result.tokens['strategy_update'].duration + result.tokens['strategy_next_task'].duration
            executor_duration = result.tokens['executor_next_cmds'].duration
            if 'executor_summary_missing' in result.tokens:
                executor_duration += result.tokens['executor_summary_missing'].duration
            commands_duration = overall_duration - planner_duration - executor_duration

            all_planner.append(float(planner_duration)/overall_duration)
            all_executor.append(float(executor_duration)/overall_duration)
            all_command.append(float(commands_duration)/overall_duration)

            rows.append([   result.filename,
                            result.models_str(),
                            str(overall_duration),
                            str(planner_duration/overall_duration),
                            str(executor_duration/overall_duration),
                            str(commands_duration/overall_duration)
            ])

        print(f"Overall Duration: {overall_duration} seconds, Planner Duration: {planner_duration} seconds, Executor Duration: {executor_duration} seconds"),

    return [OutputTable(
        title="Run Information",
        headers = ["Filename", "Model", "Duration", "% Planner", "% Executor", "% Commands"],
        footers = [ "Average", "", "",
                   f"{round(my_mean(all_planner), 4):.2%}",
                   f"{round(my_mean(all_executor), 4):.2%}",
                   f"{round(my_mean(all_command), 4):.2%}"
        ],
        rows = rows
    )]