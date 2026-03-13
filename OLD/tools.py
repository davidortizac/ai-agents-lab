
import os
from langchain.tools import tool

@tool
def list_files(path: str) -> str:
    """Lista archivos en un directorio."""
    try:
        files = os.listdir(path)
        return "\n".join(files)
    except Exception as e:
        return str(e)


@tool
def read_file(path: str) -> str:
    """Lee el contenido de un archivo."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return str(e)