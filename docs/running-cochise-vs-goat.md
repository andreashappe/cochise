# How to Run Cochise Against GOAD (Game of Active Directory)

> This is a markdown conversion of my [RCR report submitted to TOSEM](https://dl.acm.org/doi/abs/10.1145/3800584).

## Prerequisites and Requirements

The testbed of our prototype depends on a virtualized third-party
testbed, *A Game of Active Directory*[^2]. Our requirements are thus the
requirements for the testbed, the requirements for the standard *Kali*
virtual machine used to execute commands, and the requirements for
operating our prototype including providing access to a LLM.

### Hardware

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

### Virtualization Infrastructure

GOAD supports multiple virtualization backends including Oracle
Virtualbox, VMWare Workstation Pro, or Proxmox. While we initially used
Oracle Virtualbox for the TOSEM paper, stability issues motivated us to
switch to VMWware Enterprise Pro (using a free license) for the
RCR report.

Luckily I found later out that you can also run GOAD through libvirt
which is the native linux virtualization solution.

### KVM/libvirt

This is my preferred way of running GOAD if you're using Linux as host.
While it is not "officially" supported yet, you can use [this pull request](https://github.com/Orange-Cyberdefense/GOAD/pull/475). Runs perfectly for me.

### VMWare

GOAD utilizes *vagrant* and *ansible* for automatization, both of which
were provided by our used Linux Distribution (Fedora Linux 42). To
prevent version-related problems, we installed *vagrant* and
[vagrant-vmware-utility](https://developer.hashicorp.com/vagrant/docs/providers/vmware/vagrant-vmware-utility).

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
