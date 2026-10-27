"""Run the evaluation set, or re-score a recorded run without calling a model.

    python -m sql_assistant.evaluate --mode with_context --name qwen3-4b
    python -m sql_assistant.evaluate --questions eval/holdout.yaml --name holdout
    python -m sql_assistant.evaluate --replay runs/qwen3-4b-v2__with_context.jsonl

Each run writes runs/<name>__<mode>.jsonl (one line per question, with the SQL
the model wrote) and results/<name>__<mode>.md (summary and per-question table).
"""

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

import yaml

from .config import ROOT, Settings
from .compare import results_match
from .guard import GuardError, check_sql, run_query
from .knowledge import Knowledge
from .prompts import MODES

QUESTIONS_PATH = ROOT / "eval" / "questions.yaml"
RUNS_DIR = ROOT / "runs"
RESULTS_DIR = ROOT / "results"


def load_questions(path: Path = QUESTIONS_PATH) -> list:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def gold_results(settings: Settings, questions: list) -> dict:
    return {q["id"]: run_query(settings.db_path, q["gold_sql"]).rows for q in questions}


def score_sql(settings: Settings, sql: str, gold_rows: list, tables: set) -> tuple:
    """Check, run and compare one query. Returns (status, correct, rows, error)."""
    try:
        check_sql(sql, tables)
        rows = run_query(settings.db_path, sql, settings.max_rows, settings.timeout_s).rows
    except GuardError as e:
        return "blocked", False, [], str(e)
    except sqlite3.Error as e:
        return "error", False, [], str(e)
    return "ok", results_match(gold_rows, rows), rows, ""


def summarize(records: list) -> dict:
    total = len(records)
    correct = sum(r["correct"] for r in records)
    by = defaultdict(lambda: [0, 0])
    for r in records:
        for key in (f"difficulty:{r['difficulty']}", f"lang:{r['lang']}"):
            by[key][0] += r["correct"]
            by[key][1] += 1
    return {
        "correct": correct,
        "total": total,
        "accuracy": round(100.0 * correct / total, 1) if total else 0.0,
        "groups": {k: f"{v[0]}/{v[1]}" for k, v in sorted(by.items())},
        "fixed_on_retry": sum(1 for r in records if r["correct"] and r.get("attempts", 1) > 1),
        "blocked": sum(1 for r in records if r["status"] == "blocked"),
        "errors": sum(1 for r in records if r["status"] == "error"),
        "avg_seconds": round(sum(r.get("seconds", 0) for r in records) / total, 1) if total else 0.0,
    }


def write_report(records: list, name: str, mode: str, model: str) -> Path:
    s = summarize(records)
    lines = [
        f"# {name} · {mode}",
        "",
        f"Model: `{model}`",
        "",
        f"**{s['correct']} of {s['total']} correct ({s['accuracy']}%).** "
        f"Fixed on the retry: {s['fixed_on_retry']}. Blocked by the guard: {s['blocked']}. "
        f"Failed to run: {s['errors']}. Average time per question: {s['avg_seconds']} s.",
        "",
        "| Group | Correct |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v} |" for k, v in s["groups"].items()]
    lines += ["", "| ID | Lang | Level | Result | Tries | Question |", "|---|---|---|---|---|---|"]
    for r in records:
        result = "correct" if r["correct"] else ("wrong" if r["status"] == "ok" else r["status"])
        question = r["question"].replace("|", "\\|")
        lines.append(
            f"| {r['id']} | {r['lang']} | {r['difficulty']} | {result} | {r.get('attempts', 1)} | {question} |"
        )
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{name}__{mode}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run(name: str, mode: str, limit: int | None = None, questions_path: Path = QUESTIONS_PATH) -> list:
    from .assistant import Assistant

    settings = Settings.from_env()
    questions = load_questions(questions_path)
    questions = questions[:limit] if limit else questions
    gold = gold_results(settings, questions)
    assistant = Assistant(settings, mode=mode)
    tables = assistant.knowledge.table_names()
    records = []
    for q in questions:
        answer = assistant.ask(q["question"])
        if answer.status == "ok":
            correct = results_match(gold[q["id"]], answer.result.rows)
            rows = answer.result.rows
        else:
            correct, rows = False, []
        record = {
            "id": q["id"], "lang": q["lang"], "difficulty": q["difficulty"], "question": q["question"],
            "mode": mode, "model": settings.model, "sql": answer.sql, "status": answer.status,
            "error": answer.error, "attempts": answer.attempts, "seconds": round(answer.seconds, 1),
            "correct": correct, "rows": [list(r) for r in rows[:20]], "gold": [list(r) for r in gold[q["id"]][:20]],
        }
        records.append(record)
        mark = "correct" if correct else ("wrong" if answer.status == "ok" else answer.status)
        print(f"{q['id']} {mark:8s} tries={answer.attempts} {answer.seconds:5.1f}s  {q['question'][:70]}", flush=True)

    RUNS_DIR.mkdir(exist_ok=True)
    run_path = RUNS_DIR / f"{name}__{mode}.jsonl"
    with run_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    report = write_report(records, name, mode, settings.model)
    s = summarize(records)
    print(f"\n{s['correct']}/{s['total']} correct ({s['accuracy']}%) -> {run_path} and {report}")
    return records


def replay(path: Path, write: bool = False) -> list:
    """Re-run the recorded SQL against the database and re-score it. No model needed.
    With write=True the run file and its report are updated with the new scores."""
    settings = Settings.from_env()
    questions = {q["id"]: q for f in sorted((ROOT / "eval").glob("*.yaml")) for q in load_questions(f)}
    records = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    gold = gold_results(settings, [questions[r["id"]] for r in records])
    tables = Knowledge.load().table_names()
    changed = 0
    for r in records:
        if r["status"] != "ok":
            continue
        status, correct, rows, _ = score_sql(settings, r["sql"], gold[r["id"]], tables)
        if status != "ok" or correct != r["correct"]:
            changed += 1
            print(f"{r['id']}: recorded correct={r['correct']}, now {status} correct={correct}")
        if write:
            r.update(correct=correct, rows=[list(x) for x in rows[:20]], gold=[list(x) for x in gold[r["id"]][:20]])
    if write:
        Path(path).write_text("".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in records), encoding="utf-8")
        name, mode = Path(path).stem.rsplit("__", 1)
        write_report(records, name, mode, records[0].get("model", "") if records else "")
    s = summarize(records)
    print(f"{path}: {s['correct']}/{s['total']} correct; {changed} question(s) scored differently from the recording.")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the SQL assistant on eval/questions.yaml")
    parser.add_argument("--mode", choices=MODES, default="with_context")
    parser.add_argument("--name", default="run", help="label for the output files, e.g. the model name")
    parser.add_argument("--limit", type=int, help="only run the first N questions")
    parser.add_argument("--questions", type=Path, default=QUESTIONS_PATH, help="question file (default eval/questions.yaml)")
    parser.add_argument("--replay", type=Path, help="re-score a recorded runs/*.jsonl file instead")
    parser.add_argument("--write", action="store_true", help="with --replay, save the new scores")
    args = parser.parse_args()
    if args.replay:
        replay(args.replay, write=args.write)
    else:
        run(args.name, args.mode, args.limit, args.questions)


if __name__ == "__main__":
    main()
