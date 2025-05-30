import argparse
import json

from dataclasses import dataclass, field
from dateutil.parser import parse
from pathlib import Path
from statistics import mean, pstdev
from typing import List, Set

# remove this after conversion
from rich.console import Console
from rich.table import Table
from dateutil.parser import parse

@dataclass
class StrategyRound:
    timestamp: str
    executor_rounds: int = 0
    executor_llm_calls: int = 0
    tool_calls: int = 0

@dataclass
class Run:
    filename: str = None
    first_timestamp: str = None
    last_timestamp: str = None
    duration: float = 0
    models: Set[str] = field(default_factory=set)
    rounds: List[StrategyRound] = field(default_factory=list)

    def models_str(self) -> str:
        """Return a string representation of the models used in the run."""
        return ', '.join(self.models)
    
    def duration_str(self) -> str:
        return str(round(float(self.duration), 2))

def traverse_file(file):

    current_strategy_round = None
    run = Run(filename=Path(file.name).stem)

    for line in file:
        j = json.loads(line)

        # extract common data from event
        timestamp = parse(j["timestamp"])

        # update run timestamps
        if run.first_timestamp is None:
            run.first_timestamp = timestamp
        run.last_timestamp = timestamp

        # this means this was a LLM callout
        if 'costs' in j:
            # add model name to the run metadata
            if 'model_name' in j['costs']:
                model = j['costs']['model_name']
            else:
                model = 'unknown-model'
            run.models.add(model)

        match j['event']:
            case 'strategy_update':
                if not current_strategy_round is None:
                    run.rounds.append(current_strategy_round)
                current_strategy_round = StrategyRound(timestamp=timestamp)
            case 'strategy_next_task':
                assert current_strategy_round is not None, "Strategy next task without a strategy update"
                assert current_strategy_round.executor_llm_calls == 0, "New Round should have no executor calls"
                assert current_strategy_round.tool_calls == 0, "New Round should have no tool calls"
                assert current_strategy_round.executor_rounds == 0, "New Round should have no executor rounds"
            case 'executor_summary_missing':
                # this means the executor finished without producing a result
                current_strategy_round.executor_llm_calls += 1
            case 'executor_next_cmds':
                # executor issued a new round of command(s)
                current_strategy_round.executor_llm_calls += 1
                current_strategy_round.executor_rounds += 1
            case 'executor_cmd':
                # tool-call was performed (actually finished)
                current_strategy_round.tool_calls += 1
    
    if run.last_timestamp is not None and run.first_timestamp is not None:
        run.duration = (run.last_timestamp - run.first_timestamp).total_seconds()
    
    return run

def my_std_dev(data: List[int]) -> float:
    if len(data) < 2:
        return 0.0
    else:
        return pstdev(data)

def my_mean(data: List[int]) -> float:
    if len(data) == 0:
        return 0.0
    else:
        return mean(data)

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