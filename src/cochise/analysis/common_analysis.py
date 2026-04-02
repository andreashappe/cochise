import datetime
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
class LLMCall:
    name:str
    count:int = 0

    models:list[str] = field(default_factory=list)

    prompt_tokens:list[int] = field(default_factory=list)
    completion_tokens:list[int] = field(default_factory=list)
    reasoning_tokens:list[int] = field(default_factory=list)
    cached_tokens:list[int] = field(default_factory=list)

    duration:list[float] = field(default_factory=list)
    cost:list[float] = field(default_factory=list)

@dataclass
class ToolCall:
    name:str
    count:int = 0

    commands:list[str] = field(default_factory=list)
    tactics:list[str] = field(default_factory=list)
    techniques:list[str] = field(default_factory=list)
    procedures:list[str] = field(default_factory=list)
    username:list[str] = field(default_factory=list)
    password:list[str] = field(default_factory=list)

@dataclass
class Agent:
    name:str
    llm_calls:Dict[str, LLMCall] = field(default_factory=dict)
    tool_calls:Dict[str, ToolCall] = field(default_factory=dict)

@dataclass
class Run:
    filename: str
    first_timestamp: datetime.datetime|None = None
    last_timestamp: datetime.datetime|None = None

    agents: Dict[str, Agent] = field(default_factory=dict)
    duration: float = 0.0
    models: Set[str] = field(default_factory=set)

    def models_str(self) -> str:
        return ", ".join(self.models)
    
    def duration_str(self) -> str:
        return f"{self.duration:.2f}s"

    def duration_str_min(self) -> str:
        return f"{(self.duration/60):.2f}m"

def traverse_file(file):

    run = Run(Path(file.name).stem)

    for line in file:

        if len(line) == 0:
            continue

        j = json.loads(line)

        # extract common data from event
        timestamp = parse(j["timestamp"])

        # update run timestamps
        if run.first_timestamp is None:
            run.first_timestamp = timestamp
        run.last_timestamp = timestamp

        agent_id = j.get('agent', None)
        agent = run.agents.get(agent_id, Agent(name=agent_id))
        assert(agent_id)

        model = 'unknown'

        match j['event']:
            case 'configuration':
                if model is not None and model != 'unknown':
                    assert(model == j['model'])
                elif 'model' in j:
                    model = j['model']
            case 'llm_call':
                llm_call = agent.llm_calls.get(j['name'], LLMCall(j['name']))

                llm_call.count += 1

                run.models.add(model)
                llm_call.models.append(model) # TODO: add to logs

                llm_call.prompt_tokens.append(j['costs']['prompt_tokens'])
                llm_call.completion_tokens.append(j['costs']['completion_tokens'])
                llm_call.reasoning_tokens.append(j['costs']['completion_tokens_details']['reasoning_tokens'])
                llm_call.cached_tokens.append(j['costs']['prompt_tokens_details']['cached_tokens'])
                llm_call.duration.append(j['duration'])
                llm_call.cost.append(j['costs']['cost'])

                agent.llm_calls[j['name']] = llm_call
            case 'tool_call':
                tool_call = agent.tool_calls.get(j['tool_name'], ToolCall(j['tool_name']))

                tool_call.count += 1
                assert(tool_call.name == j['tool_name'])
                if 'command' in j['params']:
                    tool_call.commands.append(j['params']['command'])
                if 'mitre_attack_tactic' in j['params']:
                    tool_call.tactics.append(j['params']['mitre_attack_tactic'])
                if 'mitre_attack_technique' in j['params']:
                    tool_call.techniques.append(j['params']['mitre_attack_technique'])
                if 'mitre_attack_procedure' in j['params']:
                    tool_call.procedures.append(j['params']['mitre_attack_procedure'])
                if 'username' in j['params']:
                    tool_call.username.append(j['params']['username'])
                if 'password' in j['params']:
                    tool_call.password.append(j['params']['password'])

                agent.tool_calls[j['tool_name']] = tool_call
            case 'tool_result':
                pass
            case 'starting test-run':
                pass # just debug output
            case 'history_append':
                pass # we are not that interesting into history during replay
            case 'new knowledge':
                pass
            case 'executor':
                pass
            case 'completed':
                pass
            case _:
                raise Exception("unhandled: " + j['event'])

        run.agents[agent_id] = agent

    # needed for filtering, will be calculated in the end
    assert(run.first_timestamp is not None)
    assert(run.last_timestamp is not None)
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
