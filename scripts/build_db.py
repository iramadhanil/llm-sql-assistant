"""Build data/olist.sqlite from the Olist CSV files.

Usage:
    python scripts/build_db.py --csv-dir path/to/olist_csvs

The CSVs are the Brazilian E-Commerce Public Dataset by Olist (Kaggle).
Table and column names are cleaned up a little so they read naturally in a
prompt (for example olist_order_items_dataset.csv becomes order_items, and the
dataset's "lenght" typo is fixed). The geolocation file is not used.
"""

import argparse
import csv
import sqlite3
from pathlib import Path

# table name -> (source file, [(column, sqlite type, source column)])
TABLES = {
    "customers": ("olist_customers_dataset.csv", [
        ("customer_id", "TEXT", "customer_id"),
        ("customer_unique_id", "TEXT", "customer_unique_id"),
        ("customer_zip_code_prefix", "TEXT", "customer_zip_code_prefix"),
        ("customer_city", "TEXT", "customer_city"),
        ("customer_state", "TEXT", "customer_state"),
    ]),
    "orders": ("olist_orders_dataset.csv", [
        ("order_id", "TEXT", "order_id"),
        ("customer_id", "TEXT", "customer_id"),
        ("order_status", "TEXT", "order_status"),
        ("order_purchase_timestamp", "TEXT", "order_purchase_timestamp"),
        ("order_approved_at", "TEXT", "order_approved_at"),
        ("order_delivered_carrier_date", "TEXT", "order_delivered_carrier_date"),
        ("order_delivered_customer_date", "TEXT", "order_delivered_customer_date"),
        ("order_estimated_delivery_date", "TEXT", "order_estimated_delivery_date"),
    ]),
    "order_items": ("olist_order_items_dataset.csv", [
        ("order_id", "TEXT", "order_id"),
        ("order_item_id", "INTEGER", "order_item_id"),
        ("product_id", "TEXT", "product_id"),
        ("seller_id", "TEXT", "seller_id"),
        ("shipping_limit_date", "TEXT", "shipping_limit_date"),
        ("price", "REAL", "price"),
        ("freight_value", "REAL", "freight_value"),
    ]),
    "payments": ("olist_order_payments_dataset.csv", [
        ("order_id", "TEXT", "order_id"),
        ("payment_sequential", "INTEGER", "payment_sequential"),
        ("payment_type", "TEXT", "payment_type"),
        ("payment_installments", "INTEGER", "payment_installments"),
        ("payment_value", "REAL", "payment_value"),
    ]),
    "reviews": ("olist_order_reviews_dataset.csv", [
        ("review_id", "TEXT", "review_id"),
        ("order_id", "TEXT", "order_id"),
        ("review_score", "INTEGER", "review_score"),
        ("review_comment_title", "TEXT", "review_comment_title"),
        ("review_comment_message", "TEXT", "review_comment_message"),
        ("review_creation_date", "TEXT", "review_creation_date"),
        ("review_answer_timestamp", "TEXT", "review_answer_timestamp"),
    ]),
    "products": ("olist_products_dataset.csv", [
        ("product_id", "TEXT", "product_id"),
        ("product_category_name", "TEXT", "product_category_name"),
        ("product_name_length", "INTEGER", "product_name_lenght"),
        ("product_description_length", "INTEGER", "product_description_lenght"),
        ("product_photos_qty", "INTEGER", "product_photos_qty"),
        ("product_weight_g", "REAL", "product_weight_g"),
        ("product_length_cm", "REAL", "product_length_cm"),
        ("product_height_cm", "REAL", "product_height_cm"),
        ("product_width_cm", "REAL", "product_width_cm"),
    ]),
    "sellers": ("olist_sellers_dataset.csv", [
        ("seller_id", "TEXT", "seller_id"),
        ("seller_zip_code_prefix", "TEXT", "seller_zip_code_prefix"),
        ("seller_city", "TEXT", "seller_city"),
        ("seller_state", "TEXT", "seller_state"),
    ]),
    "category_translation": ("product_category_name_translation.csv", [
        ("product_category_name", "TEXT", "product_category_name"),
        ("product_category_name_english", "TEXT", "product_category_name_english"),
    ]),
}

INDEXES = [
    "CREATE INDEX idx_orders_customer ON orders(customer_id)",
    "CREATE INDEX idx_orders_id ON orders(order_id)",
    "CREATE INDEX idx_items_order ON order_items(order_id)",
    "CREATE INDEX idx_items_product ON order_items(product_id)",
    "CREATE INDEX idx_items_seller ON order_items(seller_id)",
    "CREATE INDEX idx_payments_order ON payments(order_id)",
    "CREATE INDEX idx_reviews_order ON reviews(order_id)",
    "CREATE INDEX idx_customers_id ON customers(customer_id)",
    "CREATE INDEX idx_products_id ON products(product_id)",
    "CREATE INDEX idx_sellers_id ON sellers(seller_id)",
]


def convert(value, sqlite_type):
    """Empty strings become NULL; numeric columns become numbers."""
    if value is None or value.strip() == "":
        return None
    if sqlite_type == "INTEGER":
        return int(float(value))
    if sqlite_type == "REAL":
        return float(value)
    return value


def build(csv_dir: Path, db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    for table, (filename, columns) in TABLES.items():
        source = csv_dir / filename
        if not source.exists():
            raise SystemExit(f"Missing {source}. Download the Olist CSVs first (see data/README.md).")
        col_defs = ", ".join(f"{name} {sqlite_type}" for name, sqlite_type, _ in columns)
        con.execute(f"CREATE TABLE {table} ({col_defs})")
        placeholders = ", ".join("?" for _ in columns)
        with source.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = (
                tuple(convert(row[src], sqlite_type) for _, sqlite_type, src in columns)
                for row in reader
            )
            con.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
        count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table:22s} {count:>8,} rows")
    for statement in INDEXES:
        con.execute(statement)
    con.commit()
    con.execute("VACUUM")
    con.close()
    print(f"done -> {db_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv-dir", type=Path, required=True, help="folder with the Olist CSV files")
    parser.add_argument("--db", type=Path, default=Path("data/olist.sqlite"), help="output SQLite file")
    args = parser.parse_args()
    build(args.csv_dir, args.db)
