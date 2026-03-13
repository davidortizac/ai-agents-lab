"""
skills/code_runner.py — Python code execution skill.

Tools:
  - run_python : execute a Python snippet and return stdout

Enabled via: SKILL_CODE_RUNNER=true (default: true)
"""

import sys
import subprocess
import textwrap
from langchain.tools import tool


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def run_python(code: str) -> str:
    """
    Executes a Python code snippet and returns its stdout output.
    Use this when the user asks to run, compute, or test Python code.
    Do NOT use for destructive operations (file deletion, network scans, etc.).
    Input must be valid Python source code as a plain string.
    Execution is limited to 10 seconds.
    """
    clean_code = textwrap.dedent(code).strip()

    try:
        result = subprocess.run(
            [sys.executable, "-c", clean_code],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return f"EXECUTION ERROR:\n{result.stderr.strip()}"
        output = result.stdout.strip()
        return output if output else "(no output)"

    except subprocess.TimeoutExpired:
        return "ERROR: Code execution timed out (10s limit)."
    except Exception as e:
        return f"ERROR: {e}"


# ---------------------------------------------------------------------------
# Skill metadata
# ---------------------------------------------------------------------------

SKILL = {
    "name": "Code Runner",
    "description": "Execute Python code snippets safely.",
    "env_key": "SKILL_CODE_RUNNER",
    "get_tools": lambda: [run_python],
}
