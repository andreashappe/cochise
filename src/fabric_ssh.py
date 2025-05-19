import invoke

from dataclasses import dataclass
from fabric import Connection
from invoke import Responder
from io import StringIO
from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional, Tuple, Type

@dataclass
class SSHConnection:
    host: str
    username: str
    password: str
    port: int = 22
    timeout: int = 90

    _conn: Connection = None

    async def connect(self):
        self._conn = Connection(
                f"{self.username}@{self.host}:{self.port}",
                connect_kwargs={"password": self.password, "look_for_keys": False, "allow_agent": False},
        )
        self._conn.open()

    def run(self, cmd, *args, **kwargs) -> Tuple[str, str, int]:

        if self._conn is None:
            raise Exception("SSH Connection not established, call .connect() first")

        res: Optional[invoke.Result] = self._conn.run(cmd, *args, **kwargs)
        return res.stdout, res.stderr, res.return_code

class FabricSshExecuteInput(BaseModel):
    command: str= Field(description="the command to execute") 

# Note: It's important that every field has type hints. BaseTool is a
# Pydantic class and not having type hints can lead to unexpected behavior.
class SshExecuteTool(BaseTool):
    name: str = "SshExecuteTool"
    description: str = "Execute command over SSH on the remote machine"
    args_schema: Type[BaseModel] = FabricSshExecuteInput
    return_direct: bool = False
    conn: SSHConnection

    def __init__(self, conn: SSHConnection):
        super(SshExecuteTool, self).__init__(conn=conn)

    def _run(self, command:str):
        raise "cannot be called synchronously"

    async def _arun(self, command:str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        """Run the command over the (already established) SSH connection."""

        sudo_pass = Responder(
            pattern=r"\[sudo\] password for " + self.conn.username + ":",
            response=self.conn.password + "\n",
        )

        out = StringIO()

        try:
            self.conn.run(command, pty=True, warn=True, out_stream=out, watchers=[sudo_pass], timeout=self.conn.timeout)
        except Exception:
            print("TIMEOUT! Could we have become root?")
        
        out.seek(0)
        tmp = ""
        for line in out.readlines():
            if not line.startswith("[sudo] password for " + self.conn.username + ":"):
                line.replace("\r", "")
                tmp = tmp + line

        return tmp