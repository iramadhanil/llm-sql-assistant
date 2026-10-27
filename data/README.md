# Data

The database is built from the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce):
about 99,000 real orders from 2016 to 2018 with items, payments, reviews, customers, sellers and products.
The data is not stored in this repository.

1. Download the dataset from Kaggle and unzip the CSV files into a folder, for example `data/csv/`.
2. Build the SQLite database:

```bash
python scripts/build_db.py --csv-dir data/csv
```

This creates `data/olist.sqlite` with eight tables: `orders`, `order_items`, `payments`, `reviews`,
`customers`, `sellers`, `products` and `category_translation`. Column descriptions are in
[`docs/data_dictionary.yaml`](../docs/data_dictionary.yaml).

Expected row counts: orders 99,441 · order_items 112,650 · payments 103,886 · reviews 99,224 ·
customers 99,441 · sellers 3,095 · products 32,951 · category_translation 71.

The Olist dataset is published under the [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) license.
