class Knowledge:
    def __init__(self):
        self.compromised_accounts = []
        self.entity_information = []

    def add_compromised_account(self, username:str, password:str, additional_information:str):
        """Save information on identified/compromised account, esp. if you a password or hash has been identified.

        Parameters
        ----------
        username : str
            the username of the identified or compromised account.
        password : str
            the account's password or password hash.
        additional_information : str
            additional information/context on the compromised account.
        """
        self.compromised_accounts.append(
            {
                'username': username,
                'password': password,
                'context': additional_information
            }
        )

    def add_entity_information(self, entity:str, information:str):
        """Note information for an entity (e.g., system or user or service or vulnerability) that might be relevant for a future attack.

        Parameters
        ----------
        entity : str 
            The respective entity, e.g., an user or system or service.
        information : str
            The information about the respective entity.
        """ 
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
