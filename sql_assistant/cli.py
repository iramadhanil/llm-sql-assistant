"""Ask a question from the command line.

    python -m sql_assistant "Which customer state has the most orders?"
    python -m sql_assistant --show-prompt "配達済みの注文は何件ですか？"
"""

import argparse

from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from .assistant import Assistant
from .config import Settings
from .prompts import MODES, build_messages


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the e-commerce database a question in plain language.")
    parser.add_argument("question", nargs="+", help="the question, in English or Japanese")
    parser.add_argument("--mode", choices=MODES, default="with_context")
    parser.add_argument("--show-prompt", action="store_true", help="print the prompt sent to the model")
    args = parser.parse_args()
    question = " ".join(args.question)

    console = Console()
    assistant = Assistant(Settings.from_env(), mode=args.mode)
    if args.show_prompt:
        for message in build_messages(question, args.mode, assistant.knowledge, assistant.ddl):
            console.rule(message["role"])
            console.print(message["content"], markup=False)
        console.rule()

    with console.status("Thinking..."):
        answer = assistant.ask(question)

    console.print(Syntax(answer.sql or "-- no query", "sql", theme="ansi_dark", word_wrap=True))
    if answer.status != "ok":
        console.print(f"[red]{answer.status}[/red]: {answer.error}")
        return

    result = answer.result
    table = Table(*result.columns, header_style="bold")
    for row in result.rows[:20]:
        table.add_row(*("NULL" if v is None else f"{v:,.2f}" if isinstance(v, float) else str(v) for v in row))
    console.print(table)
    shown = min(len(result.rows), 20)
    more = " (truncated)" if result.truncated else ""
    console.print(
        f"[dim]{shown} of {len(result.rows)} rows{more} · {answer.attempts} attempt(s) · {answer.seconds:.1f} s[/dim]"
    )


if __name__ == "__main__":
    main()
