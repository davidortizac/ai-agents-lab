"""
agent.py — Main AI agent entry point. (Fase 2)

Two layers of memory:
  1. Session memory  — MemorySaver checkpointer keeps full conversation
                       history within a session (thread_id = session UUID).
                       Restarting the agent starts a fresh session.

  2. Long-term memory — memory_skill tools (remember / recall / forget)
                        persist facts to memory/facts.json across sessions.
"""

import sys
import uuid
from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from config import OLLAMA_BASE_URL, OLLAMA_MODEL
from skills import load_enabled_skills

console = Console()


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def print_banner(tools, session_id: str) -> None:
    banner = Text()
    banner.append("  Local AI Agent  —  Fase 2\n", style="bold cyan")
    banner.append(f"  Model   : {OLLAMA_MODEL}\n", style="dim")
    banner.append(f"  Server  : {OLLAMA_BASE_URL}\n", style="dim")
    banner.append(f"  Session : {session_id}\n", style="dim")
    banner.append(f"  Tools   : {len(tools)} loaded\n", style="dim")
    banner.append("  Type 'exit' to quit | 'tools' to list skills\n", style="dim")
    console.print(Panel(banner, border_style="cyan", expand=False))


# ---------------------------------------------------------------------------
# Agent builder
# ---------------------------------------------------------------------------

def build_agent():
    """
    Builds the agent with:
    - All enabled skills loaded from the registry
    - MemorySaver checkpointer for in-session conversation history
    - A unique session thread_id so each run starts fresh
    """
    console.print("\n[bold]Loading skills...[/bold]")
    tools = load_enabled_skills()

    if not tools:
        console.print("[bold red]ERROR:[/bold red] No skills loaded. Check .env skill toggles.")
        sys.exit(1)

    llm = ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0,
    )

    # MemorySaver keeps the full message history in memory for this session.
    # Each invocation appends to the thread, so the agent remembers earlier
    # messages in the same session.
    checkpointer = MemorySaver()
    agent = create_agent(llm, tools, checkpointer=checkpointer, debug=False)

    # Unique thread ID per session — isolates conversation history
    session_id = str(uuid.uuid4())[:8]

    return agent, tools, session_id


# ---------------------------------------------------------------------------
# Response extractor
# ---------------------------------------------------------------------------

def extract_response(result: dict) -> str:
    """Pull the last assistant message from the agent graph output."""
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.content and not getattr(msg, "tool_calls", None):
            return msg.content
    return "(no response)"


# ---------------------------------------------------------------------------
# Interactive loop
# ---------------------------------------------------------------------------

def run_interactive_loop(agent, tools, session_id: str) -> None:
    print_banner(tools, session_id)

    # LangGraph config — thread_id ties all messages to this session
    config = {"configurable": {"thread_id": session_id}}

    while True:
        try:
            user_input = console.input("\n[bold green]You:[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Goodbye![/yellow]")
            sys.exit(0)

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit", "q"}:
            console.print("[yellow]Goodbye![/yellow]")
            sys.exit(0)

        # Built-in command: list loaded tools
        if user_input.lower() == "tools":
            tool_list = "\n".join(f"  - {t.name}: {t.description[:80]}" for t in tools)
            console.print(Panel(tool_list, title="[bold cyan]Loaded Tools[/bold cyan]", border_style="dim"))
            continue

        try:
            result = agent.invoke(
                {"messages": [{"role": "user", "content": user_input}]},
                config=config,
            )
            response = extract_response(result)
            console.print(Panel(
                f"[white]{response}[/white]",
                title="[bold cyan]Agent[/bold cyan]",
                border_style="cyan",
            ))
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    agent, tools, session_id = build_agent()
    run_interactive_loop(agent, tools, session_id)
