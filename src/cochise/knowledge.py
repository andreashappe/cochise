class Knowledge:
    def __init__(self):
        self.compromised_accounts = {}
        self.entity_information = {}
        self.counter = 1

    def merge(self, other_knowledge):
        """Merge another Knowledge instance into this one, combining compromised accounts and entity information.

        Parameters
        ----------
        other_knowledge : Knowledge
            Another Knowledge instance whose information should be merged into this one.
        """

        if not other_knowledge:
            return

        for key, value in other_knowledge.compromised_accounts.items():
            if value['dirty']:
                self.counter = int(key) if int(key) > self.counter
                self.compromised_accounts[key] = value
                self.compromised_accounts[key]['dirty'] = False
        
        for key, value in other_knowledge.entity_information.items():
            if value['dirty']:
                self.counter = int(key) if int(key) > self.counter
                self.entity_information[key] = value
                self.entity_information[key]['dirty'] = False

    async def add_compromised_account(self, username:str, password:str, context:str):
        """Save information on identified/compromised account, esp. if you a password or hash has been identified.

        Parameters
        ----------
        username : str
            the username of the identified or compromised account.
        password : str
            the account's password or password hash.
        context : str
            additional information/context on the compromised account.
        """
        self.compromised_accounts[str(self.counter)] = {
                'username': username,
                'password': password,
                'context': context,
                'dirty': True
        }
        self.counter += 1

        return f"noted compromised account {username} with context: {context}"

    async def update_compromised_account(self, key:str, username:str, password:str, context:str):
        """Update saved information of a compromised account identified by its numeric id, esp. if you a password or hash has been identified.

        Parameters
        ----------
        key :str
            the account id as given in the overview table
        username : str
            the username of the identified or compromised account.
        password : str
            the account's password or password hash.
        context : str
            additional information/context on the compromised account.
        """
        self.compromised_accounts[key] = {
                'username': username,
                'password': password,
                'context': context,
                'dirty': True
        }
        return f"updated account {username} with context: {context}"


    async def add_entity_information(self, entity:str, information:str):
        """Note information for an entity (e.g., system or user or service or vulnerability or lead) that might be relevant for a future attack.

        Parameters
        ----------
        entity : str 
            The respective entity, e.g., an user or system or service.
        information : str
            The information about the respective entity.
        """ 
        self.entity_information[str(self.counter)]={
            'entity': entity,
            'information': information,
            'dirty': True
        }
        self.counter += 1
        return f"noted information for entity {entity}: {information}"

    async def update_entity_information(self, key: str, entity:str, information:str):
        """Update information for an entity (e.g., system or user or service or vulnerability or lead) that might be relevant for a future attack.

        Parameters
        ----------
        key: str
            the entity id as given in the overview table  
        entity : str 
            The respective entity, e.g., an user or system or service.
        information : str
            The information about the respective entity.
        """ 
        self.entity_information[key]={
            'entity': entity,
            'information': information,
            'dirty': True
        }
        return f"noted information for entity {entity}: {information}"


    def get_compromised_accounts_markdown_table(self) -> str:
        result = "| Id | Username | Password | Context |\n|-----|----------|----------|---------|\n"
        for key, account in self.compromised_accounts.items():
            result += f"| {key} | {account['username']} | {account['password']} | {account['context']} |\n"
        return result

    def get_entity_information_markdown_table(self) -> str:
        result = "| Id | Entity | Information |\n|---|----------|---------|\n"
        for key, entity in self.entity_information.items():
            result += f"| {key} | {entity['entity']} | {entity['information']} |\n"
        return result

    def get_knowledge(self) -> str:
        result = ''
        if len(self.compromised_accounts) > 0:
            result += "## Compromised Accounts\n\n"
            result += self.get_compromised_accounts_markdown_table()
            result += '\n\n'
        if len(self.entity_information) > 0:
            result += "## Entity Information\n\n"
            result += self.get_entity_information_markdown_table()
            result += "\n\n"
        return result
