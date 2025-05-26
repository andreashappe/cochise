#!/usr/bin/python3

import json

class JSONLogWalker:
    """
    Simple JSON log walker that iterates through each JSON line
    in the provided file and dispatches it to registered handlers.
    """
    def __init__(self, path):
        self.path = path
        self.handlers = []

    def register(self, handler):
        """Register a handler function that takes a JSON object."""
        self.handlers.append(handler)

    def walk(self):
        """
        Iterate through each line in the log file, parse it as JSON,
        and dispatch to all registered handlers.
        """
        with open(self.path, 'r') as f:
            for line in f:
                data = json.loads(line)
                for handler in self.handlers:
                    handler(data)
