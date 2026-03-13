"""
skills/__init__.py — Central skill registry.

Each skill module must expose:
  SKILL = {
      "name": str,
      "description": str,
      "env_key": str,          # e.g. "SKILL_FILESYSTEM"
      "get_tools": callable,   # returns List[BaseTool]
  }

Usage:
  from skills import load_enabled_skills
  tools = load_enabled_skills()
"""

import importlib
import os
from typing import List
from langchain.tools import BaseTool

# ── Registered skill modules ──────────────────────────────────────────────────
# Add new skill module names here as they are created.
SKILL_MODULES = [
    "skills.filesystem",
    "skills.code_runner",
    "skills.fortigate",
    "skills.memory_skill",
    "skills.log_analysis",
]


def load_enabled_skills() -> List[BaseTool]:
    """
    Iterates over all registered skill modules, checks if each is enabled
    via its env_key, and collects all tools from enabled skills.

    A skill is enabled when its env_key is set to "true" (case-insensitive)
    in the environment. Missing key defaults to "true" so skills are ON by default
    unless explicitly disabled.

    Returns a flat list of LangChain BaseTool instances.
    """
    tools: List[BaseTool] = []

    for module_path in SKILL_MODULES:
        module = importlib.import_module(module_path)
        skill_meta = module.SKILL

        env_key = skill_meta.get("env_key", "")
        enabled = os.getenv(env_key, "true").lower() == "true"

        if enabled:
            skill_tools = skill_meta["get_tools"]()
            tools.extend(skill_tools)
            print(f"  [skill] ON  {skill_meta['name']} ({len(skill_tools)} tools)")
        else:
            print(f"  [skill] OFF {skill_meta['name']} (disabled via {env_key})")

    return tools
