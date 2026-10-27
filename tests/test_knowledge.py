import pytest

from sql_assistant.knowledge import Knowledge, keyword_score
from sql_assistant.llm import extract_sql
from sql_assistant.prompts import build_messages


@pytest.fixture(scope="module")
def knowledge():
    return Knowledge.load()


def rule_names(knowledge, question):
    return {r.name for r in knowledge.relevant_rules(question)}


def test_always_on_rules(knowledge):
    assert "dates" in rule_names(knowledge, "How many orders are there?")


def test_percentage_rule_only_when_asked(knowledge):
    assert "percentages" not in rule_names(knowledge, "What is the average number of installments?")
    assert "percentages" in rule_names(knowledge, "What percentage of orders arrived late?")
    assert "percentages" in rule_names(knowledge, "レビュー評価が1のレビューは全体の何％ですか？")


def test_rules_match_english_questions(knowledge):
    names = rule_names(knowledge, "What was the total revenue from delivered orders?")
    assert {"revenue", "delivered orders"} <= names
    assert "median" in rule_names(knowledge, "What is the median freight value?")


def test_rules_match_japanese_questions(knowledge):
    names = rule_names(knowledge, "配達済みの注文について、注文ごとの送料合計の平均はいくらですか？")
    assert {"delivered orders", "freight"} <= names


def test_examples_are_ranked_by_overlap(knowledge):
    examples = knowledge.relevant_examples("What was the monthly revenue in 2017?")
    assert examples and "revenue" in examples[0].question


def test_keyword_score_is_case_insensitive():
    assert keyword_score("Revenue by STATE", ["revenue", "state"]) == 2


def test_prompt_modes(knowledge):
    plain = build_messages("How many orders?", "schema_only", knowledge, "CREATE TABLE orders (order_id TEXT);")
    rich = build_messages("How many orders?", "with_context", knowledge, "")
    assert "CREATE TABLE orders" in plain[1]["content"]
    assert "Business rules" not in plain[1]["content"]
    assert "Business rules" in rich[1]["content"]
    with pytest.raises(ValueError):
        build_messages("x", "unknown", knowledge, "")


@pytest.mark.parametrize(
    "reply, expected",
    [
        ("```sql\nSELECT 1;\n```", "SELECT 1"),
        ("Here you go:\n```SQL\nSELECT 2\n```\nThis counts rows.", "SELECT 2"),
        ("```\nSELECT 3\n```", "SELECT 3"),
        ("SELECT 4;", "SELECT 4"),
    ],
)
def test_extract_sql(reply, expected):
    assert extract_sql(reply) == expected
