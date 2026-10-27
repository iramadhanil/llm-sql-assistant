"""Question in, checked SQL and result out."""

import sqlite3
import time
from dataclasses import dataclass, field

from .config import Settings
from .guard import GuardError, QueryResult, check_sql, run_query
from .knowledge import Knowledge, schema_ddl
from .llm import ChatModel, extract_sql
from .prompts import build_messages, repair_message


@dataclass
class Answer:
    question: str
    status: str  # ok, blocked, error
    sql: str = ""
    result: QueryResult | None = None
    error: str = ""
    attempts: int = 0
    seconds: float = 0.0
    replies: list = field(default_factory=list)


class Assistant:
    def __init__(self, settings: Settings, mode: str = "with_context", model=None, knowledge=None):
        self.settings = settings
        self.mode = mode
        self.model = model or ChatModel(settings)
        self.knowledge = knowledge or Knowledge.load()
        self.ddl = schema_ddl(settings.db_path)

    def ask(self, question: str, max_attempts: int = 2) -> Answer:
        """Generate a query, check it, run it. If the query is rejected or fails,
        the error goes back to the model once so it can correct itself."""
        start = time.perf_counter()
        messages = build_messages(question, self.mode, self.knowledge, self.ddl)
        answer = Answer(question=question, status="error")

        for attempt in range(1, max_attempts + 1):
            reply = self.model.complete(messages)
            answer.replies.append(reply)
            answer.attempts = attempt
            answer.sql = extract_sql(reply)
            try:
                check_sql(answer.sql, self.knowledge.table_names())
                answer.result = run_query(
                    self.settings.db_path, answer.sql, self.settings.max_rows, self.settings.timeout_s
                )
                answer.status, answer.error = "ok", ""
                break
            except GuardError as e:
                answer.status, answer.error = "blocked", str(e)
            except sqlite3.Error as e:
                answer.status, answer.error = "error", str(e)
            messages = messages + [{"role": "assistant", "content": reply}, repair_message(answer.error)]

        answer.seconds = time.perf_counter() - start
        return answer
