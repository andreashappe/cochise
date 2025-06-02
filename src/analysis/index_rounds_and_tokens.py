from rich.console import Console
from typing import List

from analysis.common_analysis import traverse_file, my_mean, my_std_dev, OutputTable

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

def index_rounds_and_tokens(console:Console, input_files, filter_result) -> List[OutputTable]:
    valid = 0
    invalid = 0
    rows : List[List[str]] = []

    for i in input_files:
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
            console.print(f"- {result.filename} has no valid models or strategy rounds")
            invalid += 1

    console.print(f"Valid runs: {valid} Invalid runs: {invalid}") 
    return [OutputTable(
        title="Run Information",
        headers = ["Filename", "Model", "Duration", "Rounds", "Executor-Calls/Round (Mean/Dev)", "Commands/Round (Mean/Dev)", "Planner Input", "Planner Output", "Exeuctor Input", "Executor Output", "Est. Cost"],
        rows = rows
    )]
