# Installation and Reproduction Report

This is a markdown conversion of my RCR report submitted to TOSEM.

This section provides a brief summary of the motivation and contribution
of the paper behind this RCR
report [@happe2025llmshackenterprisenetworks]. The vast majority of the
setup time for our prototype is spent on installing and configuring the
existing third-party GOAD testbed. To allow for easier analysis, we
include log data from our test-runs within the provided *cochise*
repository. If the creation of the whole GOAD testbed is infeasible due
to its resource usage, these log files can be used to perform the data
analysis as detailed in
Section [5.2](#data_analysis){reference-type="ref"
reference="data_analysis"}.

## Paper Motivation

Attackers will gain access to internal organization networks. Modern
defensive techniques, e.g, Zero-Trust Architectures [@stafford2020zero],
accept this and try to minimize the potential impact that an attacker
can inflict within internal networks. Typically, organizations perform
*Assumed Breach Simulations* to find potential security vulnerabilities,
and subsequently fix them. The *Simulation* in *Assumed Breach
Simulation* stands for simulating attackers; all performed operations
are real hacking operations performed against the live organization
network. This does not happen regularly due to the high cost of
performing security-testing.

The motivation for our research is multi-fold:

-   to evaluate the capabilities of LLMs to perform Assumed Breach
    Simulations against live networks. This implies that we will use a
    realistic and complex testbed for our *Capability Evaluation*.

-   to investigate the costs of using LLM-powered security testing. Are
    they a viable alternative for SME and NGOs which often cannot afford
    human penetration-testers?

-   to raise awareness about LLM's offensive capabilities, esp. with LLM
    providers and LLM creators. If off-the-shelf LLMs are capable of
    penetration-testing, future LLMs should include safe rails to
    prevent abuse.

## Paper Contribution

This paper includes the following contributions:

-   **A Novel Autonomous Prototype for Penetration-Testing.** We
    introduce a novel prototype that autonomously conducts complex
    penetration-tests on live enterprise networks using the ubiquitous
    Microsoft Active Directory. Our system is designed to automate a
    complex and human-intensive software security task.

-   **Comprehensive Evaluation of LLM Capabilities in Real-Life
    Scenarios.** We provide a comprehensive evaluation of LLM
    capabilities in penetration-testing, detailing both strengths and
    limitations in real-life contexts. The deliberate choice of a
    "messy" live testing environment addresses known concerns about the
    limitations of synthetic testbeds for real-life security impact
    evaluations [@sommer2010outside; @lukošiūtė2025llmcyberevaluationsdont].

-   **Systematic Quantitative and Qualitative Analysis with Expert
    Insights.** We systematically analyze quantitative metrics and
    integrate qualitative insights gathered from security experts. Our
    multi-faceted approach, combining automated data with human expert
    analysis, enhances the depth and validity of our findings. The
    validation of the prototype's activities against established
    cybersecurity frameworks like MITRE ATT&CK links observed behaviors
    to recognized industry standards and grounds our research in
    practical, real-world software security engineering.

-   **Investigating the Impact of Reasoning LLMs.** To the best of our
    knowledge this is the first paper that applies cutting-edge
    Reasoning LLMs to the problem of performing automated
    penetration-testing.

While we have chosen a scenario from the security domain for our
evaluation, the used LLM architecture and techniques are domain-agnostic
and can be used for improving the autonomous usage of LLMs in
non-related domains.

# Artifacts

The artifacts are released on Github[^1]. At the high level, they
consist of the following components (also see
Table [\[table:papers\]](#table:papers){reference-type="ref"
reference="table:papers"}):

-   **Prototype Code** for Evidence Generation.

-   **Generated Evidence** in the form of JSON log files

-   **Analysis Scripts** for analysis of evidence

::: table*
::: center
  Artifact              Available At                                                                 Used License
  --------------------- ---------------------------------------------------------------------------- --------------
  Evidence generation   <https://github.com/andreashappe/cochise/tree/main/src>                      MIT
  Generated Evidence    <https://github.com/andreashappe/cochise/tree/main/examples/initial-paper>   MIT
  Analysis Scripts      <https://github.com/andreashappe/cochise/tree/main/src/analysis>             MIT
:::

[]{#table:papers label="table:papers"}
:::

# Prerequisites and Requirements

The testbed of our prototype depends on a virtualized third-party
testbed, *A Game of Active Directory*[^2]. Our requirements are thus the
requirements for the testbed, the requirements for the standard *Kali*
virtual machine used to execute commands, and the requirements for
operating our prototype including providing access to a LLM.

## Hardware

We ran all tests on a *x86-64* desktop computer (AMD Ryzen 9 9950x with
12 cores, 192 GB RAM, 1 TB system NVM SSD). All virtual machines were
run using Broadcom/VMWare Workstation Pro 25H2.

The testbed consists of 5 virtual windows machines, each of which has a
60GB harddrive configured yielding a maximum storage requirement of
300GB. Due to dynamic disk allocation, the disk usage during our
benchmark runs was 103GB for all testbed machines. In sum, 20 GB of
system memory (RAM) were used by testbed itself. We used a standard
*Kali Linux* virtual machine image provided by Kali[^3] Linux using 16
GB of RAM. After multiple benchmark runs, the Linux image used
approximately 80gb or hard drive.

The prototype, *cochise*, is python based. When using *venv* for
dependencies, it needs roughly 2 gigabyte of filesystem storage.

Overall, this yields a minimum amount of 48GB RAM and roughly 190GB of
hard-drive space.

## Virtualization Infrastructure

GOAD supports multiple virtualization backends including Oracle
Virtualbox, VMWare Workstation Pro, or Proxmox. While we initially used
Oracle Virtualbox, stability issues motivated us to switch to VMWware
Enterprise Pro which can be downloaded from
<https://support.broadcom.com/> after a free user registration.

GOAD utilizes *vagrant* and *ansible* for automatization, both of which
were provided by our used Linux Distribution (Fedora Linux 42). To
prevent version-related problems, we installed *vagrant* and
*vagrant-vmware-utility* from
<https://developer.hashicorp.com/vagrant/docs/providers/vmware/vagrant-vmware-utility>.

After the *vagrant-vmware-utility* was installed, it must be activated
as a *systemd*-service. While this has not been documented by HashiCorp
themselves, it can be easily achieved by:

``` shell
$ sudo /opt/vagrant-vmware-desktop/bin/vagrant-vmware-utility service install
$ sudo systemctl start vagrant-vmware-utility
```

After VMWware, ansible and vagrant have been installed, *vagrant* can be
used to add missing plugins:

``` shell
$ vagrant plugin install vagrant-vmware-desktop
```

## GOAD Setup

We are using GOADv3[^4] with the specific commit of
*88ef39d8b6b7cfd08e0ae7e92be59bc9fecf3280*. GOAD uses evaluation
licenses for the installed Microsoft Windows products, e.g. Microsoft
Windows Server, and thus no pre-built images can be provided (as
evaluation licenses have a limited life-time of 180 days). Please refer
to GOAD's detailed installation instructions[^5] for advanced
information.

During our evaluation time-frame, the Microsoft SQL Explorer was not
available from Microsoft anymore. We removed it from the installation
instructions by applying the following diff:

``` diff
 diff --git a/ad/GOAD/data/inventory b/ad/GOAD/data/inventory
index bed60f9..d449f0e 100644
--- a/ad/GOAD/data/inventory
+++ b/ad/GOAD/data/inventory
@@ -112,8 +112,8 @@ srv03
 
 ; install mssql gui
 ; usage : servers.yml
-[mssql_ssms]
-srv02
+;[mssql_ssms]
+;srv02
 
 ; install webdav 
 [webdav]
```

We initially installed GOAD and verified the correctness of our setup:

``` shell
 $ git clone --revision 88ef39d8b6b7cfd08e0ae7e92be59bc9fecf3280 https://github.com/Orange-Cyberdefense/GOAD.git
 $ cd GOAD
 $ ./goad.sh -p vmware -t check
 [+] vagrant found in PATH 
[+] ansible-playbook found in PATH 
[+] Ansible galaxy collection ansible.windows is installed 
[+] Ansible galaxy collection community.general is installed 
[+] Ansible galaxy collection community.windows is installed 
[+] vagrant plugin vagrant-reload is installed 
[+] vmrun found in PATH 
[+] vmware utility is installed 
[+] vagrant plugin vagrant-vmware-desktop is installed 
```

If all checks were successful, the GOAD setup can be started by running:

``` shell
 $ ./goad.sh -p vmware -t install
```

The installation can last around 2--3 hours. After this step, 5 VMWare
virtual machines running in the `192.168.56.0/24` network should be
running.

## Kali Linux Virtual Machine Setup

We are using the pre-made Kali Linux VMWare virtual machine (VM) from
<https://www.kali.org/get-kali/#kali-virtual-machines>. We are also
providing a pre-configured virtual machine as part of our zenodo
artifact package (*10.5281/zenodo.17456062*).

To manually create the virtual machine, download the base VMWare image
from the Kali Linux Distribution's website:

``` shell
# download the archive
$ https://cdimage.kali.org/kali-2025.3/kali-linux-2025.3-vmware-amd64.7z

# unpack the archive (you might need to install 7z first)
$ 7z x kali-linux-2025.3-vmware-amd64.7z 
```

This image can now be added to VMWare Enterprise Pro. Please increase
the used system memory to 16gb. Make sure that the VM's network adapter
is set to be using the network segment of the created GOAD network (by
default 192.168.56.0/24). Add a second network card, configured to use
NAT to allow the Kali virtual machine to access the internet for
retrieving updates. This second network card can be disabled to prevent
LLM-provided commands to interact with systems outside of the lab
network.

Log into the started Kali virtual machine (user: *kali*, password:
*kali*). Go to the *Advanced Network Configuration* and configure both
network cards to *automatic (DHCP) address only*. We prefer to set the
IP address of the first network card (the card interacting with the test
network) to a fixed IP-address, i.e., 192.168.56.100. We will use this
IP address for the Kali VM throughout the rest of the setup
instructions. Set the DNS server to *192.168.56.10* (which is the
primary domain controller (DC) of the lab network).

Now setup the password *kali* for the *root* user:

``` shell
# set the root password to 'kali'
$ sudo passwd                
[sudo] password for kali: 
New password: 
Retype new password: 
passwd: password updated successfully
```

Allow to login as *root* over SSH by changing the option
`PermitRootLogin` to `yes` in the configuration file in
`/etc/ssh/sshd_config` and start openssh through
`sudo systemctl enable --now ssh.service`.

Now you should be able to login to the Kali virtual machine (with your
configured fix IP-address, e.g., 192.168.56.100) from your host as
"root" using the password "kali". From the virtual machine, you should
be able to ping the DC at `192.168.56.10`. With that, our basic GOAD
infrastructure has been setup.

## LLM Infrastructure

For running our python-based prototype with different cloud-provided
LLMs, respective API-keys are needed. If LLMs should be run locally, we
recommend using the OpenAI-compatible REST-interface of *ollama*.

We aligned our LLM selection process and the final selection with
best-practices for evaluating LLMs in offensive security
settings [@happe2025benchmarkingpracticesllmdrivenoffensive]. We have
selected five different LLM configurations for our analysis:

-   *OpenAI's GPT-4o* (gpt-4o-2024-08-06, temperature set to 0) and
    *DeepSeek's [DeepSeek-V3]{.smallcaps}* (temperature set to 0) will
    be used as baseline non-reasoning LLMs. This allows us to compare
    the performance of a closed-weight (GPT-4o) with an open-weight LLM
    ([DeepSeek-V3]{.smallcaps}).

-   *Google's [Gemini-2.5-Flash]{.smallcaps} (Preview)* (temperature set
    to 0) was used as an example of an integrated reasoning LLM. In
    addition, we will test the combination of *OpenAI's o1*
    (o1-preview-2024-12-17) for the high-level
    [Planner]{.smallcaps} with *OpenAI's GPT-4o* (temperature set to 0)
    for the low-level [Executor]{.smallcaps}.

-   Finally, we will investigate *Alibaba's [Qwen3]{.smallcaps}* as an
    example of an open-weight Small World Model (SLM) with reasoning
    capabilities that should be suitable for deployment on local
    edge-devices.

All models were hosted on their respective maker's cloud offerings. We
utilized LambdaLabs[^6] for running [Qwen3]{.smallcaps} by renting a
virtual machine providing sufficient hardware (VM with a single nVidia
PCIe-A100 with 40GB VRAM, 30 vCPUs, 200GB RAM) and software (Ubuntu
22.03.5LTS, nvidida 570.124.06-0Lambda0.22.04.2, Ollama v0.9.0) stack.

# Setup the Cochise Prototype

We include instructions on how to configure the *cochise* prototype,
connect it to a LLM provider, and use SSH to connect to the attacker
virtual machine within the test network. We are using *pip* and *venv*
to manage our prototype's dependencies. To install the prototype,
perform the following:

``` shell
# clone the repository
$ git clone --revision 3084bcdd99f85e5ce324f25d0d49f80439fd5382 git@github.com:andreashappe/cochise.git
$ cd cochise

# setup venv and install dependencies
$ python -m venv venv
$ source venv/bin/activate
$ pip install -e .
```

Now prepare a `.env` file within the *cochise* directory:

``` shell
# if you want to use openai
OPENAI_API_KEY='sk-...'
# if you want to use gemini
GOOGLE_API_KEY='...'
# if you want to use deepseek
DEEPSEEK_API_KEY='sk-...'

# enter the credentials from the configured kali virtual machine
TARGET_HOST=192.168.56.100
TARGET_USERNAME='root'
TARGET_PASSWORD='kali'
```

# Steps to Reproduce

After we configured the GOAD testbed, prepared a Kali-Linux attacker
virtual machine, and configured *chochise*, we can finally use *cochise*
to autonomously penetration-test the target GOAD network. During each
test-run a time-stamped JSON log file containing all interactions of
*cochise* with both LLM and environment will be stored within the
`logs/` directory.

## Data Generation

After the setup, the prototype can be started through:

``` shell
$ python src/cochise.py
```

It runs until it is stopped through triggering ctrl-c. We used a runtime
of two hours within the paper. During runs, all information needed for
analysis will be stored in *logs/* as JSON files. For each run, a new
JSON file with the start timestamp in its filename will be created.

## Data Analysis {#data_analysis}

![Using *analyze-json-logs.py* to create an overview of different runs
performed by OpenAI's O1/GPT-4o.](index.png){#fig:index
width="\\textwidth"}

![Using *analyze-json-logs.py* do detail the token-usage per used prompt
of a single test-run. O1 reports reasoning-tokens as part of the
completion tokens.](show.png){#fig:show width="\\textwidth"}

Please also see our *Methodology* Section $3.5$ in the original
paper [@happe2025llmshackenterprisenetworks]. We recommend to download
the latest version of cochise (as this version includes all log files as
well improved analysis scripts that were added after the experiments
were executed):

``` shell
# clone the repository
$ git clone git@github.com:andreashappe/cochise.git
$ cd cochise

# setup venv and install dependencies
$ python -m venv venv
$ source venv/bin/activate
$ pip install -e .
```

Copies of the JSON logs used for our analysis within the published paper
are included in *examples/initial-paper/*. We provide the following
analysis scripts for quantitative analysis and graph generation:

-   *src/analyze-json-logs.py* to create an overview of gathered log
    files, e.g., *python src/analyze-json-logs.py
    index-rounds-and-tokens examples/initial-paper/o1-gpt-4o/\*.json* to
    create an overview table of all *o1-gpt-4o* runs (shown in
    Figure [1](#fig:index){reference-type="ref" reference="fig:index"}).

-   With *python src/analyze-json-logs.py show-tokens
    examples/initial-paper/o1-gpt-4o/\*.json* the token use per included
    prompt can be analyzed. The Screenshot in
    Figure [2](#fig:show){reference-type="ref" reference="fig:show"}
    uses a single JSON log file instead of multiple log-files to show
    the token counts for the specified log-file.

-   *src/cochise-replay.py* allows to display existing JSON log-files
    similar to the original tool output (during a live run).

-   *src/analyze-json-graphs.py* generated the different graphs used
    within the paper. *src/analysis/\*.py* further analysis scripts used
    during generation of the report.

![Using *cochise-replay.py* to perform the replay of a log-file.
High-Level plans (create by the [Planner]{.smallcaps} are highlighted in
green, tasks selected by the [Planner]{.smallcaps} and forwarded to the
[Executor]{.smallcaps} are highlighted in yellow, low-level
[Executor]{.smallcaps} tool-calls (executed commands) are not
highlighted.](replay.png){#fig:replay width="\\textwidth"}

[^1]: <https://github.com/andreashappe/cochise>

[^2]: <https://github.com/Orange-Cyberdefense/GOAD>

[^3]: <https://www.kali.org/get-kali/#kali-virtual-machines>

[^4]: <https://orange-cyberdefense.github.io/GOAD/labs/GOAD/>

[^5]: <https://orange-cyberdefense.github.io/GOAD/installation/linux/#__tabbed_1_1>

[^6]: <https://lambda.ai/>
