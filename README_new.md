# Cochise: Autonomous LLM-Driven Penetration Testing in ~576 Lines of Python

> Full Active Directory domain compromise. Under $2. Less than 2 hours. No human in the loop. How?

Cochise is a minimal, readable prototype that uses Large Language Models to autonomously penetration-test enterprise networks. Point it at an Active Directory testbed, pick an LLM, and watch it plan attack chains, execute commands, harvest credentials, and escalate to domain admin -- all on its own.

**Why does this exist?** There are many autonomous hacking agent prototypes out there, but no good *baseline*. Cochise is deliberately minimal so you can:

- **Build on it** -- fork it and add your ideas without fighting framework complexity
- **Benchmark LLMs** -- swap models via a single env var and compare cybersecurity capabilities
- **Reproduce results** -- included log files, analysis scripts, and LaTeX export for academic work
- **Understand it** -- the entire agent core fits in ~576 lines of readable Python

The *understand it* approach makes it well-suited as a base for vibe-coding sessions.. LLMs can easily understand it too.

## Key Results

Through test-runs during development and debugging, I had the following results when running against [GOAD](https://github.com/Orange-Cyberdefense/GOAD) (Game of Active Directory) -- a realistic, multi-domain AD testbed with 5 Windows servers across 3 domains:

- `claude-4.6-opus` was able to fully-compromise (as in `domain dominance`) all three domains within 90 minutes.
- `gemini-3-flash-preview` is typically able to compromise 1-2 domains per run at much lower costs (typically ~$2 per run)
- `gpt-5.4` creates very long convoluted answers, need to fix context management within the *Executor* component for this. Was able to compromise 1-2 domains before my prototype crashed.
- `deepseek-v3.2` was the best open-weight model that I tested and was able to sometimes compromise a single domain but with very neglectable costs.

I also tested some of the newer Chineese models (`glm-5-turbo`, `mimi-v2-pro`, `minimax-m2.7`). While they were worse than `deepseek-v3.2` their quality was very similar to the frontier models that I've tested in early/mid 2025, their progress is impressive.

## Architecture

```
                    +------------------+
                    |     Planner      |  Strategic brain: creates attack plan,
                    |   (persistent)   |  selects tasks, aggregates knowledge
                    +--------+---------+
                             |
                    delegates tasks via LLM tool-calling
                             |
                    +--------v---------+
                    |     Executor     |  Tactical: fresh instance per task,
                    |   (ephemeral)    |  runs commands, reports findings
                    +--------+---------+
                             |
                      SSH execute_command via LLM tool-calling
                             |
                    +--------v---------+
                    |  Kali Linux VM   |  Attacker machine inside the
                    |  (target network)|  target network
                    +------------------+
```

The **Planner** maintains a persistent conversation with the LLM, building and updating a hierarchical attack plan. It delegates individual tasks to short-lived **Executor** instances that run shell commands over SSH and report back. A shared **Knowledge Base** tracks compromised accounts, discovered services, and attack leads across rounds.

Context window management is built-in: when the planner's history grows too large, it's automatically compacted so runs can continue for hours.

## Quick Start

### Prerequisites

- Python 3.12+
- SSH access to a Linux attacker VM (e.g., Kali) inside your target network
- An LLM API key ([OpenRouter](https://openrouter.ai/) recommended for easy model switching)
- A target environment (we recommend [GOAD](https://github.com/Orange-Cyberdefense/GOAD))

### Install

```bash
git clone https://github.com/andreashappe/cochise.git
cd cochise
```

### Configure

Create a `.env` file:

```bash
# LLM configuration (using OpenRouter for easy model switching)
LITELLM_MODEL='openrouter/google/gemini-3-flash-preview'
LITELLM_API_KEY='sk-or-...'

# SSH connection to your attacker VM
TARGET_HOST='192.168.56.100'
TARGET_USERNAME='root'
TARGET_PASSWORD='kali'

# Optional: runtime limits
MAX_RUN_TIME=7200                  # stop after N seconds (0 = unlimited), this is best effort not a hard limit
PLANNER_MAX_CONTEXT_SIZE=250000    # compact history at N tokens
PLANNER_MAX_INTERACTIONS=0         # max planner rounds (0 = unlimited) before history compaction
```

LiteLLM supports [100+ LLM providers](https://docs.litellm.ai/docs/providers) out of the box. To use a provider directly instead of OpenRouter:

```bash
# OpenAI
LITELLM_MODEL='gpt-4o'
LITELLM_API_KEY='sk-...'

# Google Gemini
LITELLM_MODEL='gemini/gemini-2.5-flash'
LITELLM_API_KEY='...'

# Anthropic Claude
LITELLM_MODEL='claude-opus-4-6'
LITELLM_API_KEY='sk-ant-...'

# Local models via Ollama
LITELLM_MODEL='ollama/llama3'
LITELLM_API_KEY='unused'
```

### Run

```bash
# start the autonomous pentest
uv run cochise

# or without uv
python -m cochise.cli.cochise
```

Cochise will create a timestamped JSON log in `logs/` capturing every LLM call, command execution, and discovered credential.

## Analysis Tools

Cochise ships with tools to replay, analyze, and visualize test runs:

```bash
# replay a run in your terminal (same rich output as live)
uv run cochise-replay logs/run-20260402-095548.json

# tabular overview: rounds, tokens, costs, compromised accounts
uv run cochise-analyze-logs index-rounds-and-tokens logs/*.json

# generate graphs: context growth, token usage over time
uv run cochise-analyze-graphs logs/run-20260402-095548.json
```

The analysis tools support LaTeX table export for academic papers.

## Adapting Cochise

### Use a different scenario

Cochise is not locked to Active Directory. The attack scenario is a Markdown template at `src/cochise/templates/scenario.md`. Change it to make Cochise perform any task that involves executing commands on a Linux machine -- CTF challenges, infrastructure auditing, compliance checks, or automated system administration.

### Use it as a baseline for your own agent

The codebase is structured for readability, not abstraction. The core files (I am using `tokei` for counting python lines-of-code and are not counting doc-strings within source files):

| File | Lines Python Code | Purpose |
|---|---|---|
| `planner.py` | 131 | Strategic planning loop |
| `executor.py` | 129 | Tactical command execution |
| `knowledge.py` | 73 | Credential & entity tracking |
| `common.py` | 89 | LLM interface (litellm wrapper) |
| `logger.py` | 80 | Structured JSON + Rich console logging |
| `ssh_connection.py` | 37 | Async SSH with timeout and reconnect |

See [walkthrough.md](walkthrough.md) for a detailed code walkthrough.

## Publication

This work is published in ACM Transactions on Software Engineering and Methodology (TOSEM):

> Andreas Happe, Aaron Kaplan, Juergen Cito. **"LLMs Hack Enterprise Networks: Investigating Autonomous Penetration Testing with Reasoning LLMs."** ACM TOSEM, 2025. [DOI: 10.1145/3766895](https://doi.org/10.1145/3766895) | [arXiv: 2502.04227](https://arxiv.org/abs/2502.04227)

If you use Cochise in your research, please cite:

```bibtex
@article{happe2025llmshackenterprisenetworks,
  title={LLMs Hack Enterprise Networks: Investigating Autonomous Penetration Testing with Reasoning LLMs},
  author={Happe, Andreas and Kaplan, Aaron and Cito, Juergen},
  journal={ACM Transactions on Software Engineering and Methodology},
  year={2025},
  publisher={ACM},
  doi={10.1145/3766895}
}
```

## Disclaimer

This tool is intended for authorized security testing, academic research, and educational purposes only. Only use Cochise against systems you own or have explicit written permission to test. Unauthorized access to computer systems is illegal. The authors assume no liability for misuse.

## License

MIT License. See [LICENSE](LICENSE) for details.
