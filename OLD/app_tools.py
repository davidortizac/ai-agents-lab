"""
tools.py — LangChain tool definitions for the local AI agent.

Tools available:
  - list_files   : list files in a directory
  - read_file    : read the content of a file
  - run_python   : execute a small Python snippet and return its output

All tools use the @tool decorator from LangChain.
Designed to be imported by agent.py.
"""

import os
import subprocess
import sys
import textwrap
from langchain.tools import tool


# ---------------------------------------------------------------------------
# Tool 1 — list_files
# ---------------------------------------------------------------------------

@tool
def list_files(path: str) -> str:
    """
    Lists all files and folders inside the given directory path.
    Returns a newline-separated list of names.
    Use this when the user asks to see what files exist in a directory.
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
        return f"ERROR: {str(e)}"


# ---------------------------------------------------------------------------
# Tool 2 — read_file
# ---------------------------------------------------------------------------

@tool
def read_file(path: str) -> str:
    """
    Reads and returns the full text content of a file.
    Use this when the user wants to inspect, analyze, or summarize a file.
    Only reads plain-text files (txt, py, md, json, yaml, log, etc.).
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if not content.strip():
            return f"(file is empty: {path})"
        return content
    except FileNotFoundError:
        return f"ERROR: File not found — {path}"
    except PermissionError:
        return f"ERROR: Permission denied — {path}"
    except UnicodeDecodeError:
        return f"ERROR: Cannot read binary file — {path}"
    except Exception as e:
        return f"ERROR: {str(e)}"


# ---------------------------------------------------------------------------
# Tool 3 — run_python
# ---------------------------------------------------------------------------

@tool
def run_python(code: str) -> str:
    """
    Executes a small Python code snippet and returns its stdout output.
    Use this when the user asks to run, compute, or test a piece of Python code.
    Do NOT use for destructive operations (file deletion, network calls, etc.).
    Input must be valid Python source code as a plain string.
    """
    # Dedent in case the model passes indented code blocks
    clean_code = textwrap.dedent(code).strip()

    try:
        result = subprocess.run(
            [sys.executable, "-c", clean_code],
            capture_output=True,
            text=True,
            timeout=10,          # hard limit — prevent infinite loops
        )

        output = result.stdout.strip()
        error = result.stderr.strip()

        if result.returncode != 0:
            return f"EXECUTION ERROR:\n{error}"

        return output if output else "(no output)"

    except subprocess.TimeoutExpired:
        return "ERROR: Code execution timed out (10s limit)."
    except Exception as e:
        return f"ERROR: {str(e)}"
