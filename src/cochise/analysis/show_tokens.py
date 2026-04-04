from rich.console import Console
from typing import List

from cochise.analysis.common_analysis import traverse_file, OutputTable

def show_tokens(console:Console, input_files, filter_results):

    tables : List[OutputTable] = []

    for i in input_files:
        results = traverse_file(i)
        rows : List[List[str]] = []

        prompts = {}

        # TODO: support multi-model
        if filter_results(results):
            for a in results.agents.values():
                for llm_call in a.llm_calls.values():
                    if a.name == 'main':
                        name = f'planner-{llm_call.name}'
                    else:
                        name = f'executor-{llm_call.name}'

                    prompt = prompts.get(name, { 'name': name, 'prompt': 0, 'completion': 0, 'reasoning': 0, 'cached': 0, 'duration': 0, 'costs': 0 })

                    prompt['prompt'] += sum(llm_call.prompt_tokens)
                    prompt['completion'] += sum(llm_call.completion_tokens)
                    prompt['reasoning'] += sum(llm_call.reasoning_tokens)
                    prompt['cached'] += sum(llm_call.cached_tokens)
                    prompt['duration'] += sum(llm_call.duration)
                    prompt['costs'] += sum(llm_call.cost)
                    prompts[name] = prompt

            for i in prompts.values():
                rows.append([
                    i['name'],
                    results.models_str(), # TODO: fix multi-model support
                    str(i['prompt'] + i['completion']), # total tokens (including cached)
                    str(i['prompt']),
                    str(i['completion']),
                    str(i['reasoning']),
                    str(i['cached']),
                    str(round(i['duration'], 2)),
                    str(round(i['costs'], 2))
                ])

            tables.append(OutputTable(
                title=f"Run Information: {results.filename}",
                headers=["Prompt", "Model", "Total Tokens", "Prompt Tokens", "Completions Tokens", "Reasoning Tokens", "Cached Tokens", "Duration", "Costs"],
                rows=rows
            ))
        else:
            console.print(f"{results.filename} duration <= minimum-duration")

    return tables
