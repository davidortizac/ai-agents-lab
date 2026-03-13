"""
skills/filesystem.py — File system skill.

Tools:
  - list_files  : list directory contents
  - read_file   : read a text file
  - write_file  : write/overwrite a text file

Enabled via: SKILL_FILESYSTEM=true (default: true)
"""

import os
from langchain.tools import tool


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def list_files(path: str) -> str:
    """
    Lists all files and folders inside the given directory path.
    Returns a newline-separated list sorted alphabetically.
    Use this when the user asks what files exist in a directory.
    """
    try:
        entries = os.listdir(path)
        if not entries:
            return f"(empty directory: {path})"
        return "\n".join(sorted(entries))
    except FileNotFoundError:
        return f"ERROR: Directory not found — {path}"
    except PermissionError:
        return f"ERROR: Permission denied — {path}"
    except Exception as e:
        return f"ERROR: {e}"


@tool
def read_file(path: str) -> str:
    """
    Reads and returns the full text content of a file.
    Use this when the user wants to inspect, analyze, or summarize a file.
    Only works with plain-text files (txt, py, md, json, yaml, log, conf, etc.).
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return content if content.strip() else f"(empty file: {path})"
    except FileNotFoundError:
        return f"ERROR: File not found — {path}"
    except PermissionError:
        return f"ERROR: Permission denied — {path}"
    except UnicodeDecodeError:
        return f"ERROR: Cannot read binary file — {path}"
    except Exception as e:
        return f"ERROR: {e}"


@tool
def write_file(input: str) -> str:
    """
    Writes text content to a file, creating or overwriting it.
    Input format: 'path::content'  (path and content separated by '::')
    Example: 'workspace/report.txt::This is the report content.'
    Use this when the user asks to save, create, or write a file.
    """
    try:
        if "::" not in input:
            return "ERROR: Input must be in format 'path::content'"
        path, content = input.split("::", 1)
        path = path.strip()
        os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"File written successfully: {path}"
    except PermissionError:
        return f"ERROR: Permission denied — {path}"
    except Exception as e:
        return f"ERROR: {e}"


# ---------------------------------------------------------------------------
# Skill metadata
# ---------------------------------------------------------------------------

SKILL = {
    "name": "Filesystem",
    "description": "Read, write, and list local files and directories.",
    "env_key": "SKILL_FILESYSTEM",
    "get_tools": lambda: [list_files, read_file, write_file],
}
