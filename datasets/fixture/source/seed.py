"""Create the deterministic DuckDB fixture for Grounded's metric resolver."""

from __future__ import annotations

from pathlib import Path

import duckdb


def seed_database(db_path: str = "grounded.duckdb") -> None:
    """Recreate the Slice 001 fixture and its DuckDB mart view."""
    database_path = Path(db_path)
    connection = duckdb.connect(str(database_path))
    try:
        connection.execute("DROP VIEW IF EXISTS customer_directory")
        connection.execute("DROP VIEW IF EXISTS mart_revenue")
        for table in ("order_items", "orders", "products", "customers"):
            connection.execute(f"DROP TABLE IF EXISTS {table}")

        connection.execute(
            """
            CREATE TABLE customers (
                customer_id INTEGER,
                name VARCHAR,
                email VARCHAR,
                country VARCHAR,
                created_at DATE
            )
            """
        )
        connection.executemany(
            "INSERT INTO customers VALUES (?, ?, ?, ?, ?)",
            [
                (1, "Alice", "alice@example.com", "DE", "2026-01-05"),
                (2, "Bob", "bob@example.com", "US", "2026-02-10"),
                (3, "Cara", "cara@example.com", "FR", "2026-03-01"),
                (4, "Dan", "dan@example.com", "NL", "2026-04-15"),
                (5, "Eve", "eve@example.com", "GB", "2026-05-20"),
            ],
        )

        connection.execute(
            """
            CREATE TABLE products (
                product_id INTEGER,
                name VARCHAR,
                category VARCHAR,
                price DECIMAL(10, 2)
            )
            """
        )
        connection.executemany(
            "INSERT INTO products VALUES (?, ?, ?, ?)",
            [
                (1, "Widget", "Electronics", "100.00"),
                (2, "Gadget", "Electronics", "50.00"),
                (3, "Novel", "Books", "20.00"),
                (4, "Textbook", "Books", "40.00"),
                (5, "Lamp", "Home", "30.00"),
                (6, "Chair", "Home", "75.00"),
            ],
        )

        connection.execute(
            """
            CREATE TABLE orders (
                order_id INTEGER,
                customer_id INTEGER,
                order_ts TIMESTAMP,
                status VARCHAR
            )
            """
        )
        connection.executemany(
            "INSERT INTO orders VALUES (?, ?, ?, ?)",
            [
                (101, 1, "2026-07-03 10:00:00", "completed"),
                (102, 2, "2026-07-08 12:00:00", "completed"),
                (103, 3, "2026-07-15 09:30:00", "completed"),
                (104, 4, "2026-07-20 16:45:00", "completed"),
                (105, 5, "2026-07-28 11:15:00", "completed"),
                (106, 1, "2026-07-25 14:00:00", "cancelled"),
                (107, 2, "2026-06-30 23:59:00", "completed"),
                (108, 3, "2026-08-01 00:30:00", "completed"),
            ],
        )

        connection.execute(
            """
            CREATE TABLE order_items (
                order_id INTEGER,
                product_id INTEGER,
                quantity INTEGER,
                unit_price DECIMAL(10, 2)
            )
            """
        )
        connection.executemany(
            "INSERT INTO order_items VALUES (?, ?, ?, ?)",
            [
                (101, 1, 2, "100.00"), (101, 3, 3, "20.00"),
                (102, 2, 4, "50.00"), (102, 5, 1, "30.00"),
                (103, 4, 2, "40.00"), (103, 6, 2, "75.00"),
                (104, 1, 1, "100.00"), (104, 4, 1, "40.00"),
                (105, 6, 3, "75.00"), (105, 3, 5, "20.00"),
                (106, 1, 9, "100.00"),
                (107, 2, 9, "50.00"),
                (108, 1, 9, "100.00"),
            ],
        )

        connection.execute(
            """
            CREATE VIEW mart_revenue AS
            SELECT
                order_items.order_id,
                order_items.product_id,
                order_items.quantity,
                order_items.unit_price,
                order_items.quantity * order_items.unit_price AS line_revenue,
                date_trunc('month', orders.order_ts) AS order_month,
                products.category,
                orders.status,
                customers.country
            FROM order_items
            JOIN orders ON order_items.order_id = orders.order_id
            JOIN products ON order_items.product_id = products.product_id
            JOIN customers ON orders.customer_id = customers.customer_id
            """
        )
        connection.execute(
            """
            CREATE VIEW customer_directory AS
            SELECT name, country, email
            FROM customers
            """
        )
    finally:
        connection.close()


if __name__ == "__main__":
    from packlib import active_pack

    seed_database(str(active_pack().destination.path))
