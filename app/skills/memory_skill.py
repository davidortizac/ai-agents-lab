"""
skills/memory_skill.py — Long-term memory skill.

Persists facts and notes across sessions in memory/facts.json.
Session-level conversation history is handled separately by the
MemorySaver checkpointer in agent.py.

Tools:
  - remember       : save a fact or note
  - recall         : search facts by keyword
  - list_memories  : list all saved facts
  - forget         : delete a fact by ID

Enabled via: SKILL_MEMORY=true (default: true)
"""

import os
import json
import uuid
from datetime import datetime
from langchain.tools import tool

MEMORY_FILE = os.path.join(
    os.getenv("MEMORY_PATH", os.path.join(os.path.dirname(__file__), "../../memory")),
    "facts.json",
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load() -> list[dict]:
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(facts: list[dict]) -> None:
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(facts, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def remember(fact: str) -> str:
    """
    Saves a fact, note, or piece of information to long-term memory.
    Use this when the user asks you to remember something, or when you
    learn something important that should persist across sessions.
    Input: the fact or note to remember as a plain string.
    Example: 'The FortiGate at 192.168.1.1 belongs to the main office.'
    """
    facts = _load()
    entry = {
        "id":        str(uuid.uuid4())[:8],
        "fact":      fact.strip(),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    facts.append(entry)
    _save(facts)
    return f"Remembered (id={entry['id']}): {entry['fact']}"


@tool
def recall(keyword: str) -> str:
    """
    Searches long-term memory for facts containing the given keyword.
    Use this when the user asks what you remember, or when you need
    context from previous sessions.
    Input: keyword or phrase to search for (case-insensitive).
    """
    facts = _load()
    if not facts:
        return "Memory is empty — nothing has been remembered yet."

    keyword_lower = keyword.strip().lower()
    matches = [f for f in facts if keyword_lower in f["fact"].lower()]

    if not matches:
        return f"No memories found matching '{keyword}'."

    lines = [f"[{m['id']}] ({m['timestamp']}) {m['fact']}" for m in matches]
    return f"Found {len(matches)} memory(ies):\n" + "\n".join(lines)


@tool
def list_memories(dummy: str = "") -> str:
    """
    Lists all facts stored in long-term memory.
    Use this when the user asks to see everything you remember.
    Input: leave empty or pass any string.
    """
    facts = _load()
    if not facts:
        return "Memory is empty — nothing has been remembered yet."

    lines = [f"[{m['id']}] ({m['timestamp']}) {m['fact']}" for m in facts]
    return f"All memories ({len(facts)}):\n" + "\n".join(lines)


@tool
def forget(fact_id: str) -> str:
    """
    Deletes a specific memory by its ID.
    Use this when the user asks to forget or remove a specific fact.
    Input: the memory ID (e.g. 'a3f2b1c0') shown in list_memories or recall.
    """
    facts = _load()
    original_count = len(facts)
    facts = [f for f in facts if f["id"] != fact_id.strip()]

    if len(facts) == original_count:
        return f"No memory found with id='{fact_id}'."

    _save(facts)
    return f"Memory '{fact_id}' deleted."


# ---------------------------------------------------------------------------
# Skill metadata
# ---------------------------------------------------------------------------

SKILL = {
    "name": "Memory",
    "description": "Persist and retrieve facts across sessions using a local JSON store.",
    "env_key": "SKILL_MEMORY",
    "get_tools": lambda: [remember, recall, list_memories, forget],
}
