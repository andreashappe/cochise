import asyncssh
from asyncssh import SSHClientConnection, SSHCompletedProcess

from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Optional, Type

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool

from common import get_or_fail

@dataclass
class SSHConnection:
    host: str
    username: str
    password: str
    port: int = 22

    _conn: SSHClientConnection = None

    async def connect(self):
        self._conn = await asyncssh.connect(self.host, port=self.port, username=self.username, password=self.password)

    async def run(self, cmd, timeout=300) -> SSHCompletedProcess:
        if self._conn is None:
            raise Exception("SSH Connection not established")

        return await self._conn.run(cmd, timeout=timeout, stderr=asyncssh.STDOUT)

class SshExecuteInput(BaseModel):
    command: str= Field(description="the command to execute")

# Note: It's important that every field has type hints. BaseTool is a
# Pydantic class and not having type hints can lead to unexpected behavior.
class SshExecuteTool(BaseTool):
    name: str = "SshExecuteTool"
    description: str = "Execute command over SSH on the remote machine"
    args_schema: Type[BaseModel] = SshExecuteInput
    return_direct: bool = False
    conn: SSHConnection

    def __init__(self, conn: SSHConnection):
        super(SshExecuteTool, self).__init__(conn=conn)

    def _run(self, command:str):
        raise "cannot be called synchronously"

    async def _arun(self, command:str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        """Run the command over the (already established) SSH connection."""
        try:
            result = await self.conn.run(command)
        except asyncssh.process.TimeoutError:
            return "Timeout during SSH command execution"
        return result.stdout
    
def get_ssh_connection_from_env() -> SSHConnection:
    host = get_or_fail("TARGET_HOST")
    username = get_or_fail("TARGET_USERNAME")
    password = get_or_fail("TARGET_PASSWORD")

    return SSHConnection(host=host, username=username, password=password)