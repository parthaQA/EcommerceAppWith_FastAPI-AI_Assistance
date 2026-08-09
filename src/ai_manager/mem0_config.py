from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
CHROMA_PATH = BASE_DIR / "data" / "mem0-chroma_db"

config = {
    "vector_store": {
        "provider": "chroma",
        "config": {
            "path": str(CHROMA_PATH)
        }
    },

    "llm": {
        "provider": "ollama",
        "config": {
            "model": "llama3.1:8b",
            "ollama_base_url": "http://localhost:11434",
            "temperature": 0
        }
    },

    "embedder": {
        "provider": "huggingface",
        "config": {
            "model": "all-MiniLM-L6-v2"
        }
    }
}