import datetime
from typing import List, Type

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_core.tools.base import BaseModel, Field
from rich.console import Console
from rich.pretty import Pretty
from rich.panel import Panel

from ptt import PlanTestTreeStrategy
from common import Task, is_tool_call

MAX_ROUNDS = 10

class Knowledge:
    def __init__(self):
        self.compromised_accounts = []
        self.entity_information = []

    def add_compromised_account(self, username, password, ctx):
        self.compromised_accounts.append(
            {
                'username': username,
                'password': password,
                'context': ctx
            }
        )

    def add_entity_information(self, entity, information):
        self.entity_information.append({
            'entity': entity,
            'information': information
        })

    def get_compromised_accounts_markdown_table(self) -> str:
        result = "| Username | Password | Context |\n|----------|----------|---------|\n"
        for account in self.compromised_accounts:
            result += f"| {account['username']} | {account['password']} | {account['context']} |\n"
        return result

    def get_entity_information_markdown_table(self) -> str:
        result = "| Entity | Information |\n|----------|---------|\n"
        for entity in self.entity_information:
            result += f"| {entity['entity']} | {entity['information']} |\n"
        return result

    def get_knowledge(self) -> str:
        result = "# Existing Knowledge\n\n"
        if len(self.compromised_accounts) > 0:
            result += "## Compromised Accounts\n\n"
            result += self.get_compromised_accounts_markdown_table()
        if len(self.entity_information) > 0:
            result += "## Entity Information\n\n"
            result += self.get_entity_information_markdown_table()
        result += "\n\n"
        return result

class AddAccoundInformationInput(BaseModel):
    username: str = Field(description="the username of the identified or compromised account")
    credential: str = Field(description="the account's password or password hash")
    ctx: str = Field(description="additional information/context on the compromised account")

class AddAccountInformationTool(BaseTool):
    name: str = "AddAccountInformationTool"
    description: str = "Save information on identified/compromised account, esp. if you a password or hash has been identified."
    args_schema: Type[BaseModel] = AddAccoundInformationInput
    return_direct: bool = False
    knowledge: Knowledge = None

    def __init__(self, knowledge: Knowledge):
        super(AddAccountInformationTool, self).__init__(knowledge=knowledge)

    def _run(self, username: str, credential: str, ctx: str) -> str:
        """Save information on identified/compromised account, esp. if you a password or hash has been identified."""
        self.knowledge.add_compromised_account(username, credential, ctx)
        return f"Account {username} compromised with credential {credential} and context {ctx}"

class AddEntityInformationInput(BaseModel):
    entity: str = Field(description="the respective entity, e.g., an user or system or service.")
    information: str = Field(description="the information about the respective entity")

class AddEntityInformationTool(BaseTool):
    name: str = "AddEntityInformationTool"
    description: str = "Add information about an entity, e.g., user or system or service or vulnerability, that might be relevant for a latter attack."
    args_schema: Type[BaseModel] = AddEntityInformationInput
    return_direct: bool = False
    knowledge: Knowledge = None

    def __init__(self, knowledge: Knowledge):
        super(AddEntityInformationTool, self).__init__(knowledge=knowledge)

    def _run(self, entity: str, information: str) -> str:
        """Note information for an entity (e.g., system or user or service or vulnerability) that might be relevant for a future attack."""
        self.knowledge.add_entity_information(entity, information)
        return f"Information for entity {entity} added: {information}"

class PlanUpdateInput(BaseModel):
    plan: str = Field(description="the new plan.")

class PlanUpdateTool(BaseTool):
    name: str = "PlanUpdateTool"
    description: str = "Update the PTT/Plan with a new version incorporating all newly gathered information."
    args_schema: Type[BaseModel] = PlanUpdateInput
    return_direct: bool = False
    planner: PlanTestTreeStrategy = None

    def __init__(self, planner: PlanTestTreeStrategy):
        super(PlanUpdateTool, self).__init__(planner=planner)

    def _run(self, plan: str) -> str:
        """Replace and Update the current plan with a new plan that incorporates all the new information."""
        self.planner.set_new_plan(plan)
        return f"Plan updated with {plan}"

class AgentAnalyzer:
    def __init__(self, llm, console:Console, logger):
        self.llm = llm
        self.console = console
        self.logger = logger
        self.knowledge = Knowledge()

    def get_knowledge(self) -> str:
        return self.knowledge.get_knowledge()

    def analyze_executor(self, task: Task, result:str, messages:List[str], planner: PlanTestTreeStrategy) -> None:
        # output the result, then return it
        if result!= None and len(result) > 0:
            self.console.print(Panel(result, title="ExecutorAgent Output"))
            messages.append(AIMessage(content=result))
        else:
            self.console.print(Panel('no result summary provided', title="ExecutorAgent Output"))

        tools = [
            AddAccountInformationTool(self.knowledge),
            AddEntityInformationTool(self.knowledge),
            PlanUpdateTool(planner)
        ]
        llm_with_tools = self.llm.bind_tools(tools)

        # create a string -> tool mapping
        mapping = {}
        for tool in tools:
            mapping[tool.__class__.__name__] = tool

        prompt=f"""
Update the task plan (see system message for details).

1. Each time you receive results from the worker you should 

1.1. Analyze the results and identify information that might be relevant for solving your objective through future steps.
1.2. Add new tasks or update existing task information according to the findings.
1.2.1. You can add additional information, e.g., relevant findings, to the tree structure as tree-items too.
1.3. You can mark a task as non-relevant and ignore that task in the future. Only do this if a task is not relevant for reaching the objective anymore. You can always make a task relevant again.
1.4. You must always include the full task plan as answer. If you are working on subquent task groups, still include previous taskgroups, i.e., when you work on task `2.` or `2.1.` you must still include all task groups such as `1.`, `2.`, etc. within the answer.

Initially, you should add information on identified/compromised accounts and entities.

1.1. You should add information on identified/compromised accounts and entities.
1.2. You should add information on vulnerabilities and other entities that might be relevant for a future attack.
1.3. You should add information on successful attacks and other information that might be relevant for a future attack.

Always use the `PlanUpdateTool` to update the task plan. Do not include a title or an appendix.

Make sure to note down all compromised accounts and entities and update the plan before finishing the analysis. As final answer give a summary of the changes to the task plan.
"""

        messages.append(HumanMessage(prompt))

        # try to solve our sub-task
        round = 1
        while round <= MAX_ROUNDS:

            with self.console.status("[bold green]analyst: thinking") as status:
                tik = datetime.datetime.now()
                ai_msg = llm_with_tools.invoke(messages)
                tok = datetime.datetime.now()
                messages.append(ai_msg)

            self.logger.write_llm_call('analyst_next', prompt='',
                                result={
                                    'content': ai_msg.content,
                                    'tool_calls': ai_msg.tool_calls
                                },
                                costs=ai_msg.response_metadata,
                                duration=(tok-tik).total_seconds())

            self.console.log(ai_msg.response_metadata)

            if is_tool_call(ai_msg):
                for tool_call in ai_msg.tool_calls:
                    result = mapping[tool_call["name"]].invoke(tool_call["args"])
                    self.console.print(Panel(Pretty(tool_call['args'] | {'result': result}), title=f"Tool {tool_call['name']}"))
                    messages.append(ToolMessage(content=result, tool_call_id=tool_call['id']))
            else:
                # workaround for gemini output
                if 'type' in ai_msg.content[0] and ai_msg.content[0]['type'] == 'text':
                    summary = ai_msg.content[0]['text']
                else:
                    summary = ai_msg.content
                self.console.print(Panel(summary, title="Summary of updates"))
                break
            round = round + 1