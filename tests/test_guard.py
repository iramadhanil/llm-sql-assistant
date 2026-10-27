import sqlite3

import pytest

from sql_assistant.guard import GuardError, check_sql, run_query

TABLES = {"orders", "order_items", "customers"}


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT COUNT(*) FROM orders",
        "select order_id from orders where order_status = 'delivered' limit 5",
        "WITH t AS (SELECT customer_id FROM orders) SELECT COUNT(*) FROM t",
        "SELECT order_id FROM orders UNION SELECT order_id FROM order_items",
        "SELECT customer_id, RANK() OVER (ORDER BY customer_id) FROM customers",
        "SELECT o.order_id FROM orders AS o JOIN order_items AS i ON i.order_id = o.order_id",
    ],
)
def test_allows_read_only_queries(sql):
    check_sql(sql, TABLES)


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE orders",
        "DELETE FROM orders",
        "UPDATE orders SET order_status = 'x'",
        "INSERT INTO orders (order_id) VALUES ('a')",
        "CREATE TABLE x AS SELECT * FROM orders",
        "ALTER TABLE orders ADD COLUMN x TEXT",
        "PRAGMA table_info(orders)",
        "ATTACH DATABASE 'other.db' AS other",
        "SELECT 1; DROP TABLE orders",
        "SELECT * FROM orders; SELECT * FROM customers",
        "SELECT * FROM sqlite_master",
        "SELECT * FROM secret_table",
        "",
    ],
)
def test_blocks_unsafe_or_unknown_queries(sql):
    with pytest.raises(GuardError):
        check_sql(sql, TABLES)


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.sqlite"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE orders (order_id TEXT, order_status TEXT)")
    con.executemany("INSERT INTO orders VALUES (?, ?)", [(f"o{i}", "delivered") for i in range(50)])
    con.commit()
    con.close()
    return path


def test_connection_is_read_only_even_without_the_static_check(db):
    with pytest.raises(sqlite3.OperationalError):
        run_query(db, "DELETE FROM orders")
    assert run_query(db, "SELECT COUNT(*) FROM orders").rows == [(50,)]


def test_row_limit(db):
    result = run_query(db, "SELECT order_id FROM orders", max_rows=10)
    assert len(result.rows) == 10
    assert result.truncated


def test_time_limit_stops_long_queries(db):
    endless = "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) SELECT COUNT(*) FROM n"
    with pytest.raises(sqlite3.OperationalError, match="longer than"):
        run_query(db, endless, timeout_s=0.5)
