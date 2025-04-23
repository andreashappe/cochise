import datetime

import pathlib
from typing import List
from pydantic import BaseModel, Field
from langchain_core.prompts import PromptTemplate

TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
TEMPLATE_KNOWLEDGE = PromptTemplate.from_file(str(TEMPLATE_DIR / 'update_knowledge.md.jinja2'), template_format='jinja2')

class KnowledgeUpdate(BaseModel):
    """Result of integrating new data into existing knowledge."""

    knowledge: str = Field(
        description="""
        Concrete knowledge about hte target environment including concrete findings, verified credentials, etc.
        """
    )

def update_knowledge(llm, logger, knowledge:str, new_knowledge:List[str], vulnerabilities:List[str]) -> str:

    input = {
            'exisiting_knowledge': knowledge,
            'new_knowledge': new_knowledge,
            'vulnerabilities': vulnerabilities
    }

    # try to get a list of findings (disabled for now)
    summarizer = TEMPLATE_KNOWLEDGE| llm.with_structured_output(KnowledgeUpdate, include_raw=True)

    tik = datetime.datetime.now()
    result = summarizer.invoke(input)
    tok = datetime.datetime.now()

    aggregated = result['parsed']

    if aggregated == None:
        print(str(result))

    logger.write_llm_call('update_knowledge', prompt='',
                      result=aggregated,
                      costs=result['raw'].response_metadata,
                      duration=(tok-tik).total_seconds())

    return aggregated.knowledge
