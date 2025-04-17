import datetime
import pathlib

from langchain_core.prompts import PromptTemplate

from common import Task, AnalyzedExecution
from rich.pretty import Pretty
from rich.panel import Panel

TEMPLATE_DIR = pathlib.Path(__file__).parent.parent / "templates"
TEMPLATE_RESULT = PromptTemplate.from_file(str(TEMPLATE_DIR / 'summarizer.md.jinja2'), template_format='jinja2')

def summarize(console, llm, logger, task:Task, summary:str, messages, history) -> AnalyzedExecution:

    # output the result, then return it
    if summary != None:
        console.print(Panel(summary, title="ExecutorAgent Output"))
    else:
        console.print(Panel('no summary provided', title="ExecutorAgent Output"))

    input = {
            'task': task,
            'summary': summary,
            'history': history
    }

    # try to get a list of findings (disabled for now)
    tik = datetime.datetime.now()
    summarizer = TEMPLATE_RESULT| llm.with_structured_output(AnalyzedExecution, include_raw=True)
    result = summarizer.invoke(input)
    analyzed = result['parsed']
    tok = datetime.datetime.now()

    print(str(result['raw'].response_metadata))
    logger.write_llm_call('summarizer', prompt='',
                      result=analyzed,
                      costs=result['raw'].response_metadata,
                      duration=(tok-tik).total_seconds())
    console.print(Pretty(analyzed))
    console.log("Finished low-level executor run..")

    return analyzed