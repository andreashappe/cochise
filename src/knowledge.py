import datetime

import pathlib
from typing import List
from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty
from langchain_core.prompts import PromptTemplate

TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
TEMPLATE_KNOWLEDGE = PromptTemplate.from_file(str(TEMPLATE_DIR / 'update_knowledge.md.jinja2'), template_format='jinja2')

def update_knowledge(console:Console, llm, knowledge:str, new_knowledge:List[str]) -> str:

    console.print(Panel(knowledge, title='Old Knowledge'))
    console.print(Panel(Pretty(new_knowledge), title='New Knowledge'))

    input = {
            'exisiting_knowledge': knowledge,
            'new_knowledge': new_knowledge
    }

    # try to get a list of findings (disabled for now)
    tik = datetime.datetime.now()
    summarizer = TEMPLATE_KNOWLEDGE| llm
    aggregated = summarizer.invoke(input).content
    tok = datetime.datetime.now()

    console.print(Panel(aggregated, title='Aggregated Knowledge'))

    return aggregated