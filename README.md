# Local AI Agent Lab

A production-ready local AI agent built with **LangChain** and **Ollama**, running inside Docker.
This is the foundation for a personal AI assistant that can interact with local files and tools.

---

## Architecture

```
ai-agents-lab/
├── app/
│   ├── agent.py      # Agent entry point — LLM + ReAct loop + Rich UI
│   ├── tools.py      # LangChain @tool definitions
│   └── config.py     # Environment variable loader
├── workspace/        # Files the agent can read/write (Docker volume)
├── memory/           # Persistent memory / logs (Docker volume)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env
```

### Components

| Component | Role |
|-----------|------|
| **ChatOllama** | Local LLM via Ollama HTTP API |
| **ReAct Agent** | `ZERO_SHOT_REACT_DESCRIPTION` — reasons about tool use step-by-step |
| **Tools** | `list_files`, `read_file`, `run_python` |
| **Rich** | Colored terminal UI |
| **Docker** | Isolated, reproducible environment |

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed
- [Ollama](https://ollama.com) running on your host machine with `llama3` pulled:

```bash
ollama pull llama3
ollama serve          # runs on localhost:11434 by default
```

---

## How to run

### Option A — Docker (recommended)

```bash
cd ai-agents-lab

# Build and start the agent interactively
docker compose run --rm ai-agent
```

### Option B — Local Python (development)

```bash
cd ai-agents-lab
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run from the app/ directory so imports resolve
cd app
python agent.py
```

---

## How to test the agent

Once the agent starts, try these prompts:

### List files
```
List files in /app/workspace
```

### Read a file
```
Read the file /app/workspace/test.txt
```

### Execute Python
```
Execute this Python code: print(2 + 2)
```

### Combined reasoning
```
Read the file /app/workspace/test.txt and tell me what it contains.
```

---

## Example session

```
You: List files in /app/workspace

> Entering new AgentExecutor chain...
Thought: I need to list files in the /app/workspace directory.
Action: list_files
Action Input: /app/workspace
Observation: example.txt
               test.txt
Thought: I now have the list of files.
Final Answer: The workspace contains: example.txt, test.txt

╭─ Agent ───────────────────────────────────────╮
│ The workspace contains: example.txt, test.txt │
╰───────────────────────────────────────────────╯
```

---

## Configuration

Edit `.env` to change the model or Ollama URL:

```env
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3        # change to llama3.2, mistral, etc.
```

---

## Future Extensions

This architecture is designed to grow. Here is how each extension maps to the existing structure:

### MCP Servers (Model Context Protocol)
Add new modules under `app/skills/` that wrap MCP client calls.
Each skill registers as a LangChain `@tool`, so the agent can discover and
invoke it without any changes to `agent.py`.

### Cybersecurity Tools
Add tools in `tools.py` (or a dedicated `app/tools_security.py`) that:
- parse CVE databases
- scan open ports with `nmap` via `subprocess`
- analyze PCAP files with `pyshark`

### Fortigate Automation
Create `app/tools_fortigate.py` with tools that:
- connect to FortiGate REST API via `httpx`
- read/write firewall policies
- parse FortiGate log files from `workspace/`

The agent can then answer: *"Show me all DENY policies on the outside interface."*

### Log Analysis
Add a `parse_log` tool that:
- reads log files from `workspace/`
- applies regex or structured parsing (CEF, syslog, JSON)
- summarizes anomalies

Combine with the LLM for natural-language incident reports.

---

## License

MIT
