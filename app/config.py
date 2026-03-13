"""
config.py — Centralized configuration loader.
Reads environment variables from .env file using python-dotenv.
"""

import os
from dotenv import load_dotenv

# Load .env from project root (one level up from app/)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# Ollama connection settings
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

# Workspace and memory paths (mounted as Docker volumes)
WORKSPACE_PATH: str = os.getenv("WORKSPACE_PATH", "/app/workspace")
MEMORY_PATH: str = os.getenv("MEMORY_PATH", "/app/memory")
