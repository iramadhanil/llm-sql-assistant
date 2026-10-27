"""Schema descriptions, business rules and worked examples, plus the simple
retrieval that decides which of them go into the prompt."""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .config import ROOT

DICTIONARY_PATH = ROOT / "docs" / "data_dictionary.yaml"
EXAMPLES_PATH = ROOT / "docs" / "examples.yaml"


@dataclass
class Rule:
    name: str
    text: str
    keywords: list = field(default_factory=list)
    always: bool = False


@dataclass
class Example:
    question: str
    sql: str
    keywords: list = field(default_factory=list)


@dataclass
class Knowledge:
    tables: dict
    rules: list
    examples: list

    @classmethod
    def load(cls, dictionary_path: Path = DICTIONARY_PATH, examples_path: Path = EXAMPLES_PATH) -> "Knowledge":
        data = yaml.safe_load(Path(dictionary_path).read_text(encoding="utf-8"))
        rules = [Rule(**r) for r in data["rules"]]
        examples = [Example(**e) for e in yaml.safe_load(Path(examples_path).read_text(encoding="utf-8"))]
        return cls(tables=data["tables"], rules=rules, examples=examples)

    def table_names(self) -> set:
        return set(self.tables)

    def describe_schema(self) -> str:
        """Tables and columns with their descriptions (used in the context mode)."""
        lines = []
        for table, info in self.tables.items():
            lines.append(f"Table {table}: {info['description']}")
            for column, description in info["columns"].items():
                lines.append(f"  - {column}: {description}")
        return "\n".join(lines)

    def relevant_rules(self, question: str) -> list:
        """Rules marked always, plus every rule with a keyword in the question."""
        return [r for r in self.rules if r.always or keyword_score(question, r.keywords) > 0]

    def relevant_examples(self, question: str, k: int = 2) -> list:
        """The k examples that share the most keywords with the question."""
        scored = [(keyword_score(question, e.keywords), i, e) for i, e in enumerate(self.examples)]
        scored = [s for s in scored if s[0] > 0]
        scored.sort(key=lambda s: (-s[0], s[1]))
        return [e for _, _, e in scored[:k]]


def keyword_score(text: str, keywords: list) -> int:
    """Count keywords that appear in the text. Plain substring matching keeps it
    predictable and works for Japanese, which has no spaces between words."""
    lowered = text.lower()
    return sum(1 for kw in keywords if kw.lower() in lowered)


def schema_ddl(db_path: Path) -> str:
    """CREATE TABLE statements straight from the database (used in the schema-only mode)."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
    finally:
        con.close()
    return "\n".join(r[0] + ";" for r in rows)
