"""Settings, read from environment variables so no keys live in the code."""

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    db_path: Path
    base_url: str
    model: str
    api_key: str
    max_rows: int = 1000
    timeout_s: float = 20.0

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            db_path=Path(os.getenv("SQL_ASSISTANT_DB", ROOT / "data" / "olist.sqlite")),
            # Any OpenAI-compatible endpoint works: a local llama.cpp or Ollama
            # server, or a hosted API.
            base_url=os.getenv("SQL_ASSISTANT_BASE_URL", "http://localhost:8000/v1"),
            model=os.getenv("SQL_ASSISTANT_MODEL", "local-model"),
            api_key=os.getenv("SQL_ASSISTANT_API_KEY", "not-needed"),
        )
