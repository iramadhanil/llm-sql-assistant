"""Prompt building. Two modes are compared in the evaluation:

schema_only   the model sees the CREATE TABLE statements and the question.
with_context  the model also sees column descriptions, the business rules that
              match the question, and two worked examples.
"""

from .knowledge import Knowledge

MODES = ("schema_only", "with_context")

SYSTEM_PROMPT = """You write SQLite queries for the analytics database of a Brazilian e-commerce marketplace.
The question may be in English or Japanese.

Rules:
- Write exactly one read-only query: SELECT, or WITH ... SELECT.
- Use only the tables and columns listed below.
- Answer what the question asks and nothing more.
- If the data cannot answer the question, return: SELECT 'not answerable' AS note

Reply with the SQL only, inside a ```sql code block."""


def build_messages(question: str, mode: str, knowledge: Knowledge, ddl: str) -> list:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")

    if mode == "schema_only":
        context = f"### Schema\n{ddl}"
    else:
        rules = knowledge.relevant_rules(question)
        examples = knowledge.relevant_examples(question)
        parts = [f"### Schema\n{knowledge.describe_schema()}"]
        parts.append("### Business rules\n" + "\n".join(f"- {r.text}" for r in rules))
        if examples:
            shown = "\n\n".join(f"Question: {e.question}\n```sql\n{e.sql.strip()}\n```" for e in examples)
            parts.append(f"### Examples\n{shown}")
        context = "\n\n".join(parts)

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{context}\n\n### Question\n{question}"},
    ]


def repair_message(error: str) -> dict:
    """Sent back to the model once when its query is rejected or fails."""
    return {
        "role": "user",
        "content": (
            f"That query did not work: {error}\n"
            "Write a corrected query. Reply with the SQL only, inside a ```sql code block."
        ),
    }
