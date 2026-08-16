"""Parse an OpenAPI / Swagger spec (JSON or YAML) into a grouped API surface.

Deterministic, no LLM. Groups operations by their first `tag` (falling back to the
first static path segment), so we can draw an "API surface" diagram: a root node
plus one box per group listing its `METHOD /path` endpoints.

Limitations (on purpose): no `$ref` resolution, no request/response schema graphs.
"""
from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


class Endpoint(BaseModel):
    method: str
    path: str
    summary: str = ""


class ApiGroup(BaseModel):
    name: str
    endpoints: list[Endpoint] = Field(default_factory=list)


class ParsedAPI(BaseModel):
    title: str = "API"
    groups: list[ApiGroup] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.groups

    @property
    def endpoint_count(self) -> int:
        return sum(len(g.endpoints) for g in self.groups)


def looks_like_openapi(text: str) -> bool:
    """Cheap detector the Router uses to route input to this parser."""
    t = text or ""
    return bool(re.search(r"""["']?(openapi|swagger)["']?\s*:""", t, re.I)) and "paths" in t


def _load(text: str):
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    try:
        import yaml

        return yaml.safe_load(text)
    except Exception:
        return None


def _group_name(op: dict, path: str) -> str:
    tags = op.get("tags")
    if isinstance(tags, list) and tags:
        return str(tags[0])
    # fallback: first static path segment, e.g. /users/{id} -> "users"
    for seg in path.split("/"):
        if seg and not seg.startswith("{"):
            return seg
    return "default"


def parse_openapi(text: str) -> ParsedAPI:
    doc = _load(text)
    if not isinstance(doc, dict):
        return ParsedAPI()

    info = doc.get("info") if isinstance(doc.get("info"), dict) else {}
    title = str(info.get("title") or "API")

    paths = doc.get("paths")
    if not isinstance(paths, dict):
        return ParsedAPI(title=title)

    groups: dict[str, ApiGroup] = {}
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method.lower() not in _HTTP_METHODS:
                continue
            op = op if isinstance(op, dict) else {}
            name = _group_name(op, str(path))
            group = groups.setdefault(name, ApiGroup(name=name))
            group.endpoints.append(
                Endpoint(
                    method=method.upper(),
                    path=str(path),
                    summary=str(op.get("summary") or op.get("operationId") or ""),
                )
            )

    return ParsedAPI(title=title, groups=list(groups.values()))
