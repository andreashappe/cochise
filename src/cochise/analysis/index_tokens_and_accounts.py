from rich.console import Console
from typing import List

from rich.panel import Panel
from rich.pretty import Pretty

from cochise.analysis.common_analysis import traverse_file, my_mean, my_std_dev, OutputTable

def index_tokens_and_accounts(console:Console, input_files, filter_result) -> List[OutputTable]:
    valid = 0
    invalid = 0
    rows : List[List[str]] = []

    all_durations = []
    all_tasks_executor = []
    all_commands = []
    all_prompt_tokens = []
    all_completion_tokens = []
    all_cached_tokens = []
    all_cost = []
    all_compromised_accounts = []

    for i in input_files:
        result = traverse_file(i)

        if filter_result(result):

            main = result.agents['main']
            executors = [a for a in result.agents.values() if a.name != 'main']

            tasks_executor = main.tool_calls['perform_task'].count
            commands_executed = [r.tool_calls['execute_command'].count for r in executors if 'execute_command' in r.tool_calls]

            prompt_tokens = 0
            completion_tokens = 0
            cached_tokens = 0
            cost = 0
            compromised_accounts = set()

            for a in result.agents.values():
                prompt_tokens += sum([sum(i.prompt_tokens) for i in a.llm_calls.values()])
                completion_tokens += sum([sum(i.completion_tokens) for i in a.llm_calls.values()])
                cached_tokens += sum([sum(i.cached_tokens) for i in a.llm_calls.values()])
                cost += sum([sum(i.cost) for i in a.llm_calls.values()])

                if 'add_compromised_account' in a.tool_calls:
                    compromised_accounts |= set(a.tool_calls['add_compromised_account'].username)
                if 'update_compromised_account' in a.tool_calls:
                    compromised_accounts |= set(a.tool_calls['update_compromised_account'].username)

            console.print(Panel(Pretty(compromised_accounts), title=f"Compromised Accounts in {result.filename}"))

            rows.append([
                result.filename,
                result.models_str(),
                result.duration_str_min(),
                str(tasks_executor),
                f"{round(my_mean(commands_executed),2)} +/- {round(my_std_dev(commands_executed),2)}",
                str(round(prompt_tokens / 1000, 2)),  # Convert to kTokens
                str(round(cached_tokens / 1000, 2)),  # Convert to kTokens
                str(round(completion_tokens / 1000, 2)),  # Convert to kTokens
                str(round(cost, 2)),  # Cost in USD
                str(len(compromised_accounts)),
            ])
            valid += 1

            all_durations.append(result.duration)
            all_tasks_executor.append(tasks_executor)
            all_commands.extend(commands_executed)
            all_prompt_tokens.append(prompt_tokens / 1000)
            all_cached_tokens.append(cached_tokens / 1000)
            all_completion_tokens.append(completion_tokens / 1000)
            all_cost.append(cost)
            all_compromised_accounts.append(len(compromised_accounts))
        else:
            console.print(f"- {result.filename} has no valid models or strategy rounds")
            invalid += 1

    console.print(f"Valid runs: {valid} Invalid runs: {invalid}")

    return [OutputTable(
        title="Run Information (Input/Output in kTokens, Cost in USD (or EUR?))",
        headers = ["Filename", "Model", "Duration (Minutes)", "Tasks(Exec)", "Commands/Exec (Mean/Dev)", "Prompt Tokens", "Cached Tokens", "Completion Tokens", "Cost", "Compromised Accounts"],
        footers = ["Average", "",
                   str(round(my_mean(all_durations)/60, 2)),
                   str(round(my_mean(all_tasks_executor), 2)),
                    f"{round(my_mean(all_commands),2)} +/- {round(my_std_dev(all_commands),2)}",
                    f"{round(my_mean(all_prompt_tokens), 2)} +/- {round(my_std_dev(all_prompt_tokens), 2)}",
                    f"{round(my_mean(all_cached_tokens), 2)} +/- {round(my_std_dev(all_cached_tokens), 2)}",
                    f"{round(my_mean(all_completion_tokens), 2)} +/- {round(my_std_dev(all_completion_tokens), 2)}",
                    f"{round(my_mean(all_cost), 2)} +/- {round(my_std_dev(all_cost), 2)}",
                    f"{round(my_mean(all_compromised_accounts), 2)} +/- {round(my_std_dev(all_compromised_accounts), 2)}"
        ], 
        rows = rows
    )]
