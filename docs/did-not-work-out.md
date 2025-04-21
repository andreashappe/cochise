# What ideas did not work out (yet)?

## Capture of invalid commands during `summarizer`

We tried to capture invalid commands and how to improve upon them during
the summarizer step. The data structure used was a list of `InvalidCommands`:

```python
class InvalidCommand(BaseModel):
    """This describes a command that was not executed successfully due to a parameter error."""

    command: str = Field(
        description="The command that was not executed successfully."
    )

    problem: str = Field(
        description="The problem that occured during execution. Start with the basename of the involved command, followed by a ':'"
    )


    #fixed_command: str = Field(
    #    description="An example how the command should be correctly executed."
    #)
```

Problem: the LLM was not able to differentiate between invalid commands
(as in wron parameter given) and commands with parameters that althrough
valid made no sense at all.

Removed for now.

## Split up knowledge base into assumptions and knowledge

- quality did not look well when using `o4-mini`
- LLM might have been overwhelmed with the differentiation into knowledge and assumptions
- removed