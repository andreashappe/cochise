import datetime

import pathlib
from typing import List
from langchain_core.prompts import PromptTemplate

TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
TEMPLATE_KNOWLEDGE = PromptTemplate.from_file(str(TEMPLATE_DIR / 'update_knowledge.md.jinja2'), template_format='jinja2')
TEMPLATE_KNOWLEDGE_TO_PLAN = PromptTemplate.from_file(str(TEMPLATE_DIR / 'suggest_attack_plan_changes.md.jinja2'), template_format='jinja2')

def update_knowledge(llm, logger, knowledge:str, new_knowledge:List[str], vulnerabilities:List[str]) -> str:

    input = {
            'exisiting_knowledge': knowledge,
            'new_knowledge': new_knowledge,
            'vulnerabilities': vulnerabilities
    }

    # try to get a list of findings (disabled for now)
    summarizer = TEMPLATE_KNOWLEDGE| llm

    tik = datetime.datetime.now()
    result = summarizer.invoke(input)
    tok = datetime.datetime.now()

    logger.write_llm_call('update_knowledge', prompt='',
                      result=result.content,
                      costs=result.response_metadata,
                      duration=(tok-tik).total_seconds())

    return result.content

def knowlege_to_attack_plan(llm, logger, scenario:str, knowledge:str, plan:str) -> str:

    input = {
            'SCENARIO': scenario,
            'knowledge': knowledge,
            'plan': plan
    }

    # try to get a list of findings (disabled for now)
    summarizer = TEMPLATE_KNOWLEDGE_TO_PLAN| llm

    tik = datetime.datetime.now()
    result = summarizer.invoke(input)
    tok = datetime.datetime.now()

    logger.write_llm_call('knowledge_to_attack', prompt='',
                      result=result.content,
                      costs=result.response_metadata,
                      duration=(tok-tik).total_seconds())

    print(str(result.content))