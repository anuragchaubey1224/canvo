"""Parse SQL DDL (`CREATE TABLE ...`) into a structured schema for ERD generation.

This is a pragmatic, dependency-free parser — not a full SQL grammar. It handles the
common shapes of Postgres / MySQL / SQLite DDL:

- column definitions with types (incl. parametrized types like `VARCHAR(255)`, `NUMERIC(10,2)`)
- inline `PRIMARY KEY` and `REFERENCES other(col)`
- table-level `PRIMARY KEY (...)` and `FOREIGN KEY (...) REFERENCES ...`
- named `CONSTRAINT ... FOREIGN KEY ...` / `CONSTRAINT ... PRIMARY KEY ...`
- quoted identifiers (`` ` ``, `"`, `[ ]`) and `schema.table` names
- line (`--`) and block (`/* */`) comments

Limitations (documented on purpose): no ALTER TABLE, no cross-statement constraint
resolution beyond what's inline, composite FKs collapse to their first column pair.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

# ---- models -----------------------------------------------------------------


class Column(BaseModel):
    name: str
    type: str = ""
    is_primary_key: bool = False
    is_foreign_key: bool = False


class Relation(BaseModel):
    from_table: str
    from_column: str
    to_table: str
    to_column: str


class Table(BaseModel):
    name: str
    columns: list[Column] = Field(default_factory=list)


class ParsedSchema(BaseModel):
    tables: list[Table] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.tables


# ---- helpers ----------------------------------------------------------------

_REF = r"[`\"\[\]\w.]+"  # a (possibly quoted / schema-qualified) identifier
_TYPE_STOP_WORDS = {
    "primary",
    "key",
    "not",
    "null",
    "default",
    "unique",
    "references",
    "check",
    "constraint",
    "auto_increment",
    "autoincrement",
    "generated",
    "collate",
    "comment",
    "on",
    "unsigned",
    "zerofill",
}


def looks_like_sql(text: str) -> bool:
    """Cheap detector the Router uses to route input to this parser."""
    return bool(re.search(r"\bcreate\s+table\b", text or "", re.I))


def _clean_ident(token: str) -> str:
    return token.strip().strip('`"[]').split(".")[-1].strip('`"[]').strip()


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql


def _split_top_level(body: str) -> list[str]:
    """Split a table body on depth-0 commas (so `NUMERIC(10,2)` stays intact)."""
    parts: list[str] = []
    depth = 0
    cur: list[str] = []
    for ch in body:
        if ch == "(":
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def _find_create_tables(sql: str) -> list[tuple[str, str]]:
    """Return (table_name, body) for each `CREATE TABLE name ( body )`."""
    out: list[tuple[str, str]] = []
    for m in re.finditer(r"create\s+table\s+(?:if\s+not\s+exists\s+)?(.+?)\s*\(", sql, re.I | re.S):
        name = _clean_ident(m.group(1))
        # scan from just after the '(' for the matching close paren
        depth = 1
        i = m.end()
        while i < len(sql) and depth > 0:
            if sql[i] == "(":
                depth += 1
            elif sql[i] == ")":
                depth -= 1
            i += 1
        out.append((name, sql[m.end() : i - 1]))
    return out


def _cols_in_parens(item: str) -> list[str]:
    m = re.search(r"\(([^)]*)\)", item)
    if not m:
        return []
    return [_clean_ident(c) for c in m.group(1).split(",") if c.strip()]


def _parse_fk(item: str, table: str) -> Relation | None:
    m = re.search(
        r"foreign\s+key\s*\(\s*([^)]*)\)\s*references\s+(" + _REF + r")\s*(?:\(\s*([^)]*)\))?",
        item,
        re.I,
    )
    if not m:
        return None
    from_cols = [_clean_ident(c) for c in m.group(1).split(",") if c.strip()]
    to_cols = [_clean_ident(c) for c in (m.group(3) or "").split(",") if c.strip()]
    return Relation(
        from_table=table,
        from_column=from_cols[0] if from_cols else "",
        to_table=_clean_ident(m.group(2)),
        to_column=to_cols[0] if to_cols else "id",
    )


# ---- main -------------------------------------------------------------------


def parse_sql(ddl: str) -> ParsedSchema:
    sql = _strip_comments(ddl or "")
    schema = ParsedSchema()
    pk_constraints: dict[str, set[str]] = {}

    for table_name, body in _find_create_tables(sql):
        table = Table(name=table_name)
        for item in _split_top_level(body):
            tokens = item.split()
            if not tokens:
                continue
            head = _clean_ident(tokens[0]).lower()

            # --- table-level constraints ---
            if head == "primary" and len(tokens) > 1 and tokens[1].lower() == "key":
                pk_constraints.setdefault(table_name, set()).update(_cols_in_parens(item))
                continue
            if head == "foreign" and len(tokens) > 1 and tokens[1].lower() == "key":
                if rel := _parse_fk(item, table_name):
                    schema.relations.append(rel)
                continue
            if head == "constraint":
                if re.search(r"\bforeign\s+key\b", item, re.I) and (
                    rel := _parse_fk(item, table_name)
                ):
                    schema.relations.append(rel)
                elif re.search(r"\bprimary\s+key\b", item, re.I):
                    pk_constraints.setdefault(table_name, set()).update(_cols_in_parens(item))
                continue
            if head in {"unique", "key", "index", "check", "fulltext", "spatial"}:
                continue

            # --- column definition ---
            col_name = _clean_ident(tokens[0])
            type_tokens: list[str] = []
            for tok in tokens[1:]:
                if tok.split("(")[0].lower() in _TYPE_STOP_WORDS:
                    break
                type_tokens.append(tok)
            col = Column(
                name=col_name,
                type=" ".join(type_tokens).rstrip(","),
                is_primary_key=bool(re.search(r"\bprimary\s+key\b", item, re.I)),
            )
            ref = re.search(
                r"references\s+(" + _REF + r")\s*(?:\(\s*(" + _REF + r")\s*\))?", item, re.I
            )
            if ref:
                col.is_foreign_key = True
                schema.relations.append(
                    Relation(
                        from_table=table_name,
                        from_column=col_name,
                        to_table=_clean_ident(ref.group(1)),
                        to_column=_clean_ident(ref.group(2)) if ref.group(2) else "id",
                    )
                )
            table.columns.append(col)
        schema.tables.append(table)

    # apply table-level primary keys
    for table in schema.tables:
        pks = pk_constraints.get(table.name, set())
        for col in table.columns:
            if col.name in pks:
                col.is_primary_key = True

    # mark FK columns discovered via table-level constraints
    fk_cols = {(r.from_table, r.from_column) for r in schema.relations}
    for table in schema.tables:
        for col in table.columns:
            if (table.name, col.name) in fk_cols:
                col.is_foreign_key = True

    return schema
