"""Unit tests for the OpenAPI parser (no LLM, deterministic)."""
from __future__ import annotations

import json

from app.tools.parse_openapi import looks_like_openapi, parse_openapi

SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Shop API", "version": "1.0"},
    "paths": {
        "/users": {
            "get": {"tags": ["users"], "summary": "List users"},
            "post": {"tags": ["users"], "operationId": "createUser"},
        },
        "/users/{id}": {"get": {"tags": ["users"]}},
        "/orders": {"get": {"tags": ["orders"]}, "post": {"tags": ["orders"]}},
        "/health": {"get": {}},  # no tag → falls back to path segment "health"
    },
}

SPEC_JSON = json.dumps(SPEC)

SPEC_YAML = """
openapi: 3.0.0
info:
  title: Shop API
paths:
  /users:
    get:
      tags: [users]
  /orders:
    post:
      tags: [orders]
"""


def _group(api, name):
    return next(g for g in api.groups if g.name == name)


def test_detects_openapi():
    assert looks_like_openapi(SPEC_JSON)
    assert looks_like_openapi(SPEC_YAML)
    assert not looks_like_openapi("CREATE TABLE users (id INT);")


def test_title_and_counts():
    api = parse_openapi(SPEC_JSON)
    assert api.title == "Shop API"
    assert api.endpoint_count == 6
    assert {g.name for g in api.groups} == {"users", "orders", "health"}


def test_grouping_by_tag():
    api = parse_openapi(SPEC_JSON)
    users = _group(api, "users")
    signatures = {(e.method, e.path) for e in users.endpoints}
    assert ("GET", "/users") in signatures
    assert ("POST", "/users") in signatures
    assert ("GET", "/users/{id}") in signatures


def test_fallback_to_path_segment_when_no_tag():
    api = parse_openapi(SPEC_JSON)
    health = _group(api, "health")
    assert [(e.method, e.path) for e in health.endpoints] == [("GET", "/health")]


def test_yaml_spec():
    api = parse_openapi(SPEC_YAML)
    assert api.title == "Shop API"
    assert {g.name for g in api.groups} == {"users", "orders"}


def test_empty_or_non_openapi():
    assert parse_openapi("").is_empty
    assert parse_openapi("just prose, not a spec").is_empty
