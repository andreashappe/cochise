# Can LLMs Hack Enterprise Networks?

***Autonomous Assumed Breach Penetration-Testing Active Directory Networks***

The title is quite a handful, I know..

I have been working on [hackingBuddyGPT](https://github.com/ipa-lab/hackingBuddyGPT), making it easier for ethical hackers to use LLMs. My main focus are single-host linux systems and privilege-escalation attacks within them.

When OpenAI opened up API access to its o1 model on January, 24th 2025 and I saw the massive quality improvement over GPT-4o, one of my initial thoughts was "could this be used for more-complex pen-testing tasks.. for example, performing Assumed Breach simulations again Active Directory networks?"

To evaluate the LLM's capabilities I set up the great [GOADv3](https://github.com/Orange-Cyberdefense/GOAD) testbed and wrote the simple prototype that you're currenlty looking at. This work is only intended to be used against security testbeds, never against real system (you know, as long as we do not understand how AI decision-making happens, you wouldn't want to use an LLM for taking potentially destructive decisions).

A [paper detailing our architecture, implementation and results is available on arxive](https://arxiv.org/pdf/2502.04227), if you want to cite it within your own work, please use

```bibtex
@misc{happe2025llmshackenterprisenetworks,
      title={Can LLMs Hack Enterprise Networks? Autonomous Assumed Breach Penetration-Testing Active Directory Networks}, 
      author={Andreas Happe and Jürgen Cito},
      year={2025},
      eprint={2502.04227},
      archivePrefix={arXiv},
      primaryClass={cs.CR},
      url={https://arxiv.org/abs/2502.04227}, 
}
```

**I expect this work (especially the prototype, not the collected logs and screenshots) to end up within [hackingBuddyGPT](https://github.com/ipa-lab/hackingBuddyGPT) eventually.**

## Example

![Cochise using AS-REP roasting together with password-cracking to compromise missandei](examples/screenshots/asrep_hash.png)

Cochise using AS-REP roasting together with password-cracking to compromise missandei's password.

## How to use this?

### Step 1: Install GOAD

I was using [GOADs install instructions](https://orange-cyberdefense.github.io/GOAD/installation/) to install GOAD v3 using VirtualBox as backend (side-note: I'd love to have a KVM-based backend).

I had problems starting VirtualBox due to my host's Linux Kernel 6.12 auto-loading KVM (and VirtualBox only loads when KVM hasn't been loaded yet). Seem Linux KVM auto-load behavior changed in 6.12 and you have to pass `kvm.enable_virt_at_load=0` as Kernel boot option.

We are using the standard [GOAD setup](https://orange-cyberdefense.github.io/GOAD/labs/GOAD/) but the other ones should also be good. The default setup uses `192.168.56.0/24` for the testbed.

### Step 2: Setup the Kali Linux VM

Create a new kali linux virtual machine and place it into the virtual network (which is used by GOAD). I did the following changes to the otherwise vanilla Kali VM:

- enabled root access via SSH and increased parallel SSH connectes to 100 (both in `/etc/ssh/sshd_config`)
- removed wayland/X11. Mostly because our tooling does not work with graphcial user interfaces and I prefer my attacker VMs to have as little processes as possible -- this makes it easier to spot anomalous processes and saves resources, etc.

I also added the target hostnames to `/etc/hosts` and configured the virtual AD DNS through `/etc/resolve.conf` (also see https://mayfly277.github.io/posts/GOADv2-pwning_part1/) but did not setup Kerberos.

### Step 3: Fix VMs

When I started with evaluating my prototype, I ran into ***weird*** timing problems. "The internet" told me to try the following fixes:

- limiting the core count per VM to 2
- enabling HPET timers for all virtual machines (`VBoxManage modifyvm <server> --hpet on`).

Did I already mention that I would have loved to use KVM instead of VirtualBox?

### Step 4: Setup cochise and its dependencies

.. will follow soon.

# Disclaimers

Please note and accept all of them.

### Disclaimer 1

This project is an experimental application and is provided "as-is" without any warranty, express or implied. By using this software, you agree to assume all risks associated with its use, including but not limited to data loss, system failure, or any other issues that may arise.

The developers and contributors of this project do not accept any responsibility or liability for any losses, damages, or other consequences that may occur as a result of using this software. You are solely responsible for any decisions and actions taken based on the information provided by this project. 

**Please note that the use of any OpenAI language model can be expensive due to its token usage.** By utilizing this project, you acknowledge that you are responsible for monitoring and managing your own token usage and the associated costs. It is highly recommended to check your OpenAI API usage regularly and set up any necessary limits or alerts to prevent unexpected charges.

As an autonomous experiment, hackingBuddyGPT may generate content or take actions that are not in line with real-world best-practices or legal requirements. It is your responsibility to ensure that any actions or decisions made based on the output of this software comply with all applicable laws, regulations, and ethical standards. The developers and contributors of this project shall not be held responsible for any consequences arising from the use of this software.

By using hackingBuddyGPT, you agree to indemnify, defend, and hold harmless the developers, contributors, and any affiliated parties from and against any and all claims, damages, losses, liabilities, costs, and expenses (including reasonable attorneys' fees) arising from your use of this software or your violation of these terms.

### Disclaimer 2

The use of hackingBuddyGPT for attacking targets without prior mutual consent is illegal. It's the end user's responsibility to obey all applicable local, state, and federal laws. The developers of hackingBuddyGPT assume no liability and are not responsible for any misuse or damage caused by this program. Only use it for educational purposes.
