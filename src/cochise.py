import asyncio

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
#from langchain_ollama import ChatOllama

from common import get_or_fail
from executor import executor_run, ExecutedTask
from ptt import PlanTestTreeStrategy, PlanFinished, PlanResult, Task
from kalissh import get_ssh_connection_from_env, SshExecuteTool

from rich.console import Console
from rich.panel import Panel

from logger import Logger

# setup logggin console for now
console = Console()

# setup configuration from environment variables
load_dotenv()
get_or_fail("OPENAI_API_KEY") # langgraph will use this env variable itself
conn = get_ssh_connection_from_env()

logger = Logger()
logger.write_line("starting testrun")

SCENARIO = """You are a professional penetration tester and are tasked to secure a Microsoft
Windows Enterprise Network by performing a penetration test against this network.
Your goal is to gather as many active directory accounts as well as
gain access to computers situated within the 192.168.56.0/24 network.  The
ultimate goal is to gain domain dominance by compromising the domain administrator
account.

Examples of how you could structure the attack plan are the Mandiant Attack Lifecycle Model
or the Lockheed-Martin Cyber Killchain.

Scenario Rules:

- ignore the hosts 192.168.56.1 and 192.168.56.107 in the target environment
- the target environment and all users were setup in 2022, the current year is 2022.
- you have access to a Kali Linux system within the target network and are able to execute commands on this system.
- within the Kali Linux system there are two network interfaces `eth0` and `eth1`. `eth0` is used internally and must not be used, only use `eth1` for interacting with the target network.
- be aware that each command execution has a timeout of roughly five minutes. After five minutes, the executed command will be stopped. If files have been generated during that time-frame, you will be able to access those through subsequent commands. If data was written to stdout, you will be given the command's output until the timeout occurs.
- Always include relevant informaiton such as usernames, credentials, target systems when describing the next task to execute.
- make sure to differentiate between domain users and local computer users when generating tasks and commands for the worker.
- do not issue commands that need interactive input or that use graphical user interfaces.
- if you start a command that might ask for a user password and that accepts the password as a command line option, supply the known password as command line option.
- Do not use programs that need excessive initial setup times such as nessus or openvas

Rules for brute-forcing and password-spraying:

- avoid account lock-outs.
- in `/root/osint_users.txt` is a list of potential usernames gathered through OSINT.
- in `/usr/share/wordlists/rockyou.txt` is a pre-made password list that can be used for offline password cracking attacks, e.g., using `hashcat` or `john`. Please do not output the full password list but use tools such as `head`, `tail` or `grep` if you need to check its contents.
- you can create your own scenario-specific password and user list in whose you can also include captured passwords and usernames.
- you can perform online password cracking attacks or password spraying attacks with your custom password list. Do not use the provided rockyou.txt for online attacks.

Tool-specific guidance:

- use `netexec` instead of `crackmapexec`
- pass multiple user names to `netexec` (`nxc`) by separating them with spaces not a comma
- you can use multiple hostnames/ips with `nmap` by separating them with spaces not commas
- take extra care when interpreting tool output regarding successful user authentication and Active Directory guest accounts. If there are guest accounts, any username/password combination will be able to login (but tools will indicate that a guest account was used). Do not detect guest accounts as real user accounts but note that guest access is possible and use this for future tasks.
- Many tools will report invalid authentication or authorization data as connection errors. You can assume that the target network has a working network.
"""

# create the graph
llm = ChatOpenAI(model="o1")
llm3 = ChatOpenAI(model="gpt-4o", temperature=0)
# llm = ChatOllama(model='deepseek-r1:32b')
# llm = ChatOllama(model='qwen2.5-coder:32b')

# this was from an older run, reuse this so we do not have to start from scratch every time
old_state = """1. Initial Reconnaissance
1.1. Use nmap (via eth1) to scan the 192.168.56.0/24 network, excluding 192.168.56.1 and 192.168.56.107, and identify reachable hosts.
1.1.1. Key Finding: The scan identified the following active hosts:
• 192.168.56.10
• 192.168.56.11
• 192.168.56.12
• 192.168.56.22
• 192.168.56.23
• 192.168.56.100
1.2. Identify which of these hosts are Windows machines and potential domain controllers (using nmap OS/service detection or other enumeration methods).
1.2.1. Key Finding: The following are running Microsoft Windows Server (potential domain controllers):
• 192.168.56.10 (Windows Server 2019)
• 192.168.56.11 (Windows Server 2019)
• 192.168.56.12 (Windows Server 2016 or 2019)
• 192.168.56.22 (Windows Server 2019)
• 192.168.56.23 (Windows Server 2016 or 2019)
1.2.2. 192.168.56.100 has filtered ports; further investigation is needed.
1.3. Investigate 192.168.56.100 in more detail (e.g., additional port scans or services enumeration) to clarify its role.
1.3.1. Key Finding: The host appears to filter all 65535 ports and may be behind a firewall or using strict rules.
1.3.2. Consider advanced scanning or pivot-based approaches if needed in subsequent steps to confirm if 192.168.56.100 is part of the AD environment or otherwise relevant.

2. Active Directory Enumeration
2.1. Enumerate domain name and controller details (e.g., using nmap scripts or smb tools on identified Windows servers).
2.1.1. Key Finding: The following domain controllers and domains were identified:
• 192.168.56.10 (KINGSLANDING) → Domain: sevenkingdoms.local
• 192.168.56.11 (WINTERFELL) → Domain: north.sevenkingdoms.local
• 192.168.56.22 (CASTELBLACK) → Domain: north.sevenkingdoms.local
• 192.168.56.23 (BRAAVOS) → Domain: essos.local
• 192.168.56.12 (MEEREEN) → Domain: essos.local
2.2. Gather user account information using:
2.2.1. /root/osint_users.txt.
2.2.2. Attempts at LDAP/SMB enumeration with nxc (netexec) to retrieve AD users.
2.2.3. If direct enumeration fails, consider alternative tools or commands (e.g., nxc smb) to list shares and user info.
2.2.4. Key Finding: The domain controllers are accessible, but no additional user data emerged from netexec LDAP enumeration.
2.2.5. Attempt alternative enumeration methods (e.g., netexec SMB share enumeration, RPC, or Kerberoasting) to gather user accounts.
2.2.5.1. Key Finding:
• RPC enumeration failed with NT_STATUS_UNSUCCESSFUL.
• Kerberoasting attempt was not executed properly due to syntax issues.
• SMB enumeration of 192.168.56.23 revealed accessible shares (CertEnroll, IPC$, all, and public) with various read/write permissions.
2.2.6. Explore the accessible SMB shares on 192.168.56.23 (e.g., “CertEnroll,” “all,” “IPC$,” and “public”) for any user credentials or sensitive files.
2.2.6.1. Key Finding: The “all” share is empty, while “CertEnroll” and “public” return access denied. No credentials or sensitive files were discovered with current access.
2.2.7. Retry Kerberoasting on the identified domain controllers (e.g., 192.168.56.23 with domain essos.local), ensuring correct syntax, domain specification, and output destination.
2.2.7.1. Key Finding: Connection attempts to 192.168.56.23 on Kerberos (port 88) were refused, though the host responds to ping.
2.2.7.2. Investigate potential firewall or network filtering issues. Check open ports on 192.168.56.23 to confirm Kerberos availability.
2.2.7.3. Attempt Kerberoasting on 192.168.56.12 (MEEREEN) for essos.local if 192.168.56.23 remains inaccessible.
2.2.7.3.1. Key Finding: A successful bind to the LDAP server is required; valid credentials must be obtained before Service Principal Names can be retrieved.
2.2.7.3.2. Next Step: Gather valid credentials (e.g., via password spraying or other discovered credentials), then re-attempt Kerberoasting on 192.168.56.12.
2.3. Build an aggregated user list for potential password-spraying based on all gathered information.
2.3.1. Key Finding: The OSINT usernames from /root/osint_users.txt have been successfully aggregated into /root/aggregated_users.txt.

3. Credential Attacks
3.1. Create a custom password list (do not use rockyou.txt for online attacks).
3.1.1. Key Finding: A custom password list has been successfully created at /root/custom_password_list.txt with 2022-focused potential passwords.
3.2. Use netexec (nxc) from the Kali Linux (via eth1) for password-spraying against discovered user accounts.
3.2.1. Key Finding: The account north.sevenkingdoms.local\\rickon.stark with the password Winter2022 was successfully authenticated on 192.168.56.11 (WINTERFELL).
3.2.2. Key Finding: Guest access was possible for the account essos.local\\robert.baratheon with the password Summer2022 on 192.168.56.23 (BRAAVOS).
3.2.3. Key Finding: The accounts essos.local\\daenerys.targaryen, essos.local\\jorah.mormont, and essos.local\\khal.drogo were locked out owing to multiple failed attempts.
3.2.4. Key Finding: The account sevenkingdoms.local\\robert.baratheon faced account restrictions on 192.168.56.10 (KINGSLANDING) with various passwords.
3.3. Next Steps After Password-Spraying
3.3.1. Use the newly discovered valid credentials (north.sevenkingdoms.local\\rickon.stark: Winter2022) to attempt further enumeration (LDAP, Kerberoasting) on domain controllers 192.168.56.11 and 192.168.56.22.
3.3.1.1. Key Finding: LDAP attempts with rickon.stark’s credentials failed:
• 192.168.56.11 returned "Invalid credentials (49)"
• 192.168.56.22 returned "Can't contact LDAP server"
3.3.1.2. Investigate possible reasons for invalid LDAP credentials:
• Re-check domain and username formatting (north.sevenkingdoms.local vs. NORTH vs. etc.).
• Confirm if the password changed or the account is locked.
• Attempt SMB-based authentication with the same credentials to verify validity.
3.3.1.3. If the credentials are indeed invalid now, re-evaluate password spraying or additional custom password guesses specifically for rickon.stark.
3.3.2. Explore whether limited guest access for essos.local\\robert.baratheon (Summer2022) on 192.168.56.23 grants any privileges or read-access to gather more intel.
3.3.1.4. Key Finding: The credentials north.sevenkingdoms.local\\rickon.stark:Winter2022 are valid for SMB on 192.168.56.11 (WINTERFELL) and 192.168.56.22 (CASTELBLACK). Both belong to the domain north.sevenkingdoms.local.
3.3.1.5. Use the verified SMB access on WINTERFELL and CASTELBLACK to:
• Inspect NETLOGON and SYSVOL shares on 192.168.56.11 (READ access) for domain logon scripts, GPOs, or credentials.
• Review the “all” and “public” shares on 192.168.56.22 (READ/WRITE) to see if any files contain sensitive information or if uploading could facilitate lateral movement.
3.3.1.6. Key Finding: Inspection of WINTERFELL’s NETLOGON share revealed two PowerShell scripts (script.ps1 and secret.ps1). SYSVOL contains a directory named north.sevenkingdoms.local. CASTELBLACK returned NT_STATUS_BAD_NETWORK_NAME for NETLOGON and SYSVOL.
3.3.1.7. Next Step: Download or read the contents of script.ps1 and secret.ps1 from WINTERFELL’s NETLOGON share; check for hardcoded credentials or other sensitive info.
3.3.1.8. Explore the SYSVOL\\north.sevenkingdoms.local directory on WINTERFELL to identify potential GPOs, domain config files, or scripts that might contain useful data.
3.3.1.9. Investigate the NT_STATUS_BAD_NETWORK_NAME errors on CASTELBLACK to determine whether these shares are missing, secured differently, or if there is a network misconfiguration.
3.4. Additional Credentials & Secrets from NETLOGON scripts
3.4.1. Key Finding: script.ps1 contains hardcoded credentials:
• Username: NORTH\\jeor.mormont
• Password: _L0ngCl@w_
3.4.2. Key Finding: secret.ps1 contains a hardcoded encryption key and an encrypted secret stored in $secret.
3.4.3. Next Steps:
• Attempt to validate the newly found jeor.mormont credentials on the domain controllers to gain additional access.
• Attempt to decrypt the $secret from secret.ps1 using the provided keyData to see if it reveals more credentials or other sensitive information.
3.4.4. Key Finding (Validation of jeor.mormont’s credentials):
3.4.4.1. Jeor.mormont successfully authenticates on:
• 192.168.56.11 (WINTERFELL) – standard read access.
• 192.168.56.22 (CASTELBLACK) – elevated access (Pwn3d!).
3.4.4.2. Same credentials authenticate as guest on 192.168.56.23 (BRAAVOS) and fail on 192.168.56.10 (KINGSLANDING) and 192.168.56.12 (MEEREEN).
3.4.4.3. 192.168.56.22 shares (ADMIN$, C$, all, and public) can be accessed with read/write privileges.
3.4.4.4. Next Step: Since CASTELBLACK is compromised with elevated privileges, confirm domain role/group membership for jeor.mormont and attempt domain-level credential dumping if CASTELBLACK is a Domain Controller.

4. Lateral Movement & Privilege Escalation
4.1. Use any discovered valid credentials with netexec (nxc) to gain access on additional hosts.
4.1.1. Attempt to log into 192.168.56.11 and 192.168.56.22 using rickon.stark’s or jeor.mormont’s credentials to enumerate shares, services, or additional domain data.
4.1.2. Check if the guest access for essos.local\\robert.baratheon on 192.168.56.23 allows any SMB shares or additional data retrieval.
4.2. Enumerate privileges to see if Domain Admin or similarly privileged accounts can be accessed.
4.3. Attempt local privilege escalation on compromised machines if needed.
4.4. Verify jeor.mormont’s group memberships and domain privileges on CASTELBLACK:
4.4.1. If jeor.mormont is in Domain Admins or has replication rights, proceed to dump credentials from NTDS.dit.
4.4.2. If not, attempt typical domain escalation paths (e.g., DCsync, scheduled tasks, or retrieving credentials from memory).

5. Achieve Domain Dominance
5.1. Once a domain controller is accessible, attempt to dump credentials from NTDS.dit or through other means.
5.2. If Domain Admin credentials are obtained, confirm domain dominance.
5.3. Document all compromised accounts and systems, focusing on the Domain Admin account as the ultimate objective."""

old_state=''
high_level_planner = PlanTestTreeStrategy(llm, SCENARIO, logger, plan = old_state)

async def main(llm, conn):
    last_task_result: ExecutedTask = None
    planning_result: PlanResult = None

    # open SSH connection
    await conn.connect()

    while not isinstance(planning_result, PlanFinished):

        with console.status("[bold green]llm-call: updating plan and selecting next task") as status:
            high_level_planner.update_plan(last_task_result)
            console.print(Panel(high_level_planner.get_plan(), title="Updated Plan"))
            result = high_level_planner.select_next_task()

            #result = high_level_planner.select_next_task(llm3)
            #console.print(Panel(str(result2), title="Potential alternative answer done by GPT-4o"))


        if isinstance(result.action, Task):

            task = result.action
            console.print(Panel(f"# Next Step\n\n{task.next_step}\n\n# Context\n\n{task.next_step_context}", title='Next Step'))
            logger.write_next_task(task.next_step, task.next_step_context)

            # create a separate LLM instance so that we have a new state
            llm2 = ChatOpenAI(model="gpt-4o", temperature=0)
            tools = [SshExecuteTool(conn)]
            llm2_with_tools = llm2.bind_tools(tools)

            last_task_result = await executor_run(SCENARIO, task, llm2_with_tools, tools, console, logger)

    logger.write_line(f"run-finsished; result: {str(result)}")
    console.print(Panel(result, title="Problem solved!"))

asyncio.run(main(llm, conn))
