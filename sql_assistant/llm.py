"""A thin wrapper around any OpenAI-compatible chat endpoint."""

import re

from .config import Settings

SQL_BLOCK = re.compile(r"```(?:sql|sqlite)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


class ChatModel:
    def __init__(self, settings: Settings):
        from openai import OpenAI  # imported here so tests can run without a server

        self.client = OpenAI(base_url=settings.base_url, api_key=settings.api_key)
        self.model = settings.model

    def complete(self, messages: list) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0,
            max_tokens=800,
        )
        return response.choices[0].message.content or ""


def extract_sql(text: str) -> str:
    """Pull the query out of a model reply: the first ```sql block if there is
    one, otherwise the whole reply. Trailing semicolons are removed."""
    match = SQL_BLOCK.search(text)
    sql = match.group(1) if match else text
    return sql.strip().rstrip(";").strip()
