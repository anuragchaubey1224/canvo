"""Unit tests for the SQL DDL parser (no LLM, fully deterministic)."""

from __future__ import annotations

from app.tools.parse_sql import looks_like_sql, parse_sql

ECOMMERCE = """
-- a small e-commerce schema
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    total NUMERIC(10,2) NOT NULL,
    status VARCHAR(32)
);
"""


def _table(schema, name):
    return next(t for t in schema.tables if t.name == name)


def _col(table, name):
    return next(c for c in table.columns if c.name == name)


def test_detects_sql():
    assert looks_like_sql(ECOMMERCE)
    assert not looks_like_sql("draw a login flow for an app")


def test_tables_and_columns():
    schema = parse_sql(ECOMMERCE)
    assert {t.name for t in schema.tables} == {"users", "orders"}
    orders = _table(schema, "orders")
    # the comma inside NUMERIC(10,2) must NOT split the column list
    assert {c.name for c in orders.columns} == {"id", "user_id", "total", "status"}
    assert _col(orders, "total").type == "NUMERIC(10,2)"


def test_primary_key_inline():
    schema = parse_sql(ECOMMERCE)
    assert _col(_table(schema, "users"), "id").is_primary_key is True
    assert _col(_table(schema, "users"), "email").is_primary_key is False


def test_inline_foreign_key_relation():
    schema = parse_sql(ECOMMERCE)
    rels = [(r.from_table, r.from_column, r.to_table, r.to_column) for r in schema.relations]
    assert ("orders", "user_id", "users", "id") in rels
    assert _col(_table(schema, "orders"), "user_id").is_foreign_key is True


def test_table_level_constraints():
    ddl = """
    CREATE TABLE posts (
        id INT PRIMARY KEY,
        author_id INT,
        CONSTRAINT fk_author FOREIGN KEY (author_id) REFERENCES users (id)
    );
    """
    schema = parse_sql(ddl)
    posts = _table(schema, "posts")
    assert _col(posts, "author_id").is_foreign_key is True
    rels = [(r.from_table, r.from_column, r.to_table, r.to_column) for r in schema.relations]
    assert ("posts", "author_id", "users", "id") in rels


def test_composite_primary_key():
    ddl = """
    CREATE TABLE memberships (
        user_id INT,
        group_id INT,
        PRIMARY KEY (user_id, group_id)
    );
    """
    schema = parse_sql(ddl)
    m = _table(schema, "memberships")
    assert _col(m, "user_id").is_primary_key is True
    assert _col(m, "group_id").is_primary_key is True


def test_quoted_and_schema_qualified_names():
    ddl = 'CREATE TABLE IF NOT EXISTS public."Account" ( "Id" INT PRIMARY KEY, name TEXT );'
    schema = parse_sql(ddl)
    assert _table(schema, "Account")
    assert _col(_table(schema, "Account"), "Id").is_primary_key is True


def test_empty_or_non_sql():
    assert parse_sql("").is_empty
    assert parse_sql("just some text, no ddl here").is_empty
