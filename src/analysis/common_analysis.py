import argparse
import json

from dataclasses import dataclass, field
from dateutil.parser import parse
from pathlib import Path
from statistics import mean, stdev
from typing import Dict, List, Set

@dataclass
class OutputTable:
    title: str
    headers: List[str]
    rows: List[List[str]]
    footers: List[str] = field(default_factory=list)

@dataclass
class StrategyRound:
    timestamp: str
    executor_rounds: int = 0
    executor_llm_calls: int = 0
    tool_calls: int = 0

@dataclass
class LLMAccounting:
    model: str = None
    duration: float = 0
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0 

@dataclass
class Run:
    filename: str = None
    first_timestamp: str = None
    last_timestamp: str = None
    duration: float = 0
    models: Set[str] = field(default_factory=set)
    rounds: List[StrategyRound] = field(default_factory=list)
    tokens: Dict[str, LLMAccounting] = field(default_factory=dict)

    def models_str(self) -> str:
        """Return a string representation of the models used in the run."""
        return ', '.join(self.models)
    
    def duration_str(self) -> str:
        return str(round(float(self.duration), 2))


def add_token_usage_metadata(acc, j):
    if 'model_name' not in j['costs']:
        return
    
    assert(acc.model == j['costs']['model_name'])

    acc.duration += j['duration']
    #print(str(j['costs']['usage_metadata']))
    if 'total_token_count' in j['costs']['usage_metadata']:
        acc.total_tokens += j['costs']['usage_metadata']['total_token_count']
        acc.prompt_tokens += j['costs']['usage_metadata']['prompt_token_count']
        acc.completion_tokens += j['costs']['usage_metadata']['candidates_token_count']
        acc.reasoning_tokens += 0
        acc.cached_tokens += j['costs']['usage_metadata']['cached_content_token_count']
    else:
        acc.total_tokens += j['costs']['usage_metadata']['total_tokens']
        acc.prompt_tokens += j['costs']['usage_metadata']['input_tokens']
        acc.completion_tokens += j['costs']['usage_metadata']['output_tokens']
        acc.reasoning_tokens += j['costs']['usage_metadata']['output_token_details']['reasoning'] if 'output_token_details' in j['costs']['usage_metadata'] else 0
        acc.cached_tokens += j['costs']['usage_metadata']['input_token_details']['cache_read'] if 'input_token_details' in j['costs']['usage_metadata'] else 0


    return acc

def add_token_usage(acc, j):
    if 'model_name' not in j['costs']:
        return
     
    assert(acc.model == j['costs']['model_name'])

    #print(str(j['costs']['token_usage']))
    if 'completion_token_details' in j['costs']['token_usage'] and j['costs']['token_usage']['completion_tokens_details'] != None and 'reasoning' in j['costs']['token_usage']['completion_tokens_details']:
        reasoning_tokens = j['costs']['token_usage']['completion_tokens_details']['reasoning_tokens']
    else:
        reasoning_tokens = 0

    #print(str(j['costs']['token_usage'])) 
    acc.duration += j['duration']
    acc.total_tokens += j['costs']['token_usage']['total_tokens']
    acc.prompt_tokens += j['costs']['token_usage']['prompt_tokens']
    acc.completion_tokens += j['costs']['token_usage']['completion_tokens']
    acc.reasoning_tokens += reasoning_tokens
    acc.cached_tokens += j['costs']['token_usage']['prompt_tokens_details']['cached_tokens'] if 'prompt_tokens_details' in j['costs']['token_usage'] and j['costs']['token_usage']['prompt_tokens_details'] != None else 0

    return acc

def traverse_file(file):

    current_strategy_round = None
    run = Run(filename=Path(file.name).stem)

    for line in file:
        j = json.loads(line)
        event = j['event']

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

            acc = run.tokens.get(event, LLMAccounting(model=model))
            if 'token_usage' in j['costs']:
                add_token_usage(acc, j)
            elif 'usage_metadata' in j['costs']:
                # if we don't have token usage, we can still get some information from here
                add_token_usage_metadata(acc, j)
            run.tokens[event] = acc

        match event:
            case 'strategy_update':
                if not current_strategy_round is None:
                    run.rounds.append(current_strategy_round)
                current_strategy_round = StrategyRound(timestamp=timestamp)
            case 'strategy_next_task':
                current_strategy_round = StrategyRound(timestamp=timestamp)
                assert current_strategy_round is not None, "Strategy next task without a strategy update"
                assert current_strategy_round.executor_llm_calls == 0, "New Round should have no executor calls"
                assert current_strategy_round.tool_calls == 0, "New Round should have no tool calls"
                assert current_strategy_round.executor_rounds == 0, "New Round should have no executor rounds"
            case 'executor_summary_missing':
                # this means the executor finished without producing a result
                current_strategy_round.executor_llm_calls += 1
            case 'executor_next_cmds':
                if current_strategy_round is None:
                    print("Warning: executor_next_cmds without a strategy update, wintermute?")
                    current_strategy_round = StrategyRound(timestamp=timestamp)
                # executor issued a new round of command(s)
                current_strategy_round.executor_llm_calls += 1
                current_strategy_round.executor_rounds += 1
            case 'executor_cmd':
                # tool-call was performed (actually finished)
                current_strategy_round.tool_calls += 1
  
    # add the final strategy round if we stopped during a run
    if current_strategy_round not in run.rounds:
        run.rounds.append(current_strategy_round)
    
    if run.last_timestamp is not None and run.first_timestamp is not None:
        run.duration = (run.last_timestamp - run.first_timestamp).total_seconds()
    
    return run

def my_std_dev(data: List[int]) -> float:
    if len(data) < 2:
        return 0.0
    else:
        return stdev(data)

def my_mean(data: List[int]) -> float:
    if len(data) == 0:
        return 0.0
    else:
        return mean(data)
