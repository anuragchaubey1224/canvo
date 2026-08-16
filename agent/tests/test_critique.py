"""Geometry Critic — deterministic layout checks (no network/LLM)."""

from __future__ import annotations

from app.graph.critique import analyze_geometry
from app.schema import AgentAction, Shape


def _box(box_id: str, x: float, y: float, w: float = 200, h: float = 80) -> AgentAction:
    return AgentAction(type="create", shape=Shape(id=box_id, type="geo", x=x, y=y, w=w, h=h))


def _arrow(arrow_id: str, frm: str, to: str) -> AgentAction:
    return AgentAction(
        type="create", shape=Shape(id=arrow_id, type="arrow", x=0, y=0, from_id=frm, to_id=to)
    )


def test_detects_overlap():
    report = analyze_geometry([_box("a", 0, 0), _box("b", 20, 20)])  # clearly overlapping
    assert report.has_overlap
    assert any(i.kind == "overlap" for i in report.issues)


def test_clean_when_well_spaced():
    report = analyze_geometry([_box("a", 0, 0), _box("b", 600, 0)])  # far apart
    assert not report.has_overlap
    assert not report.issues


def test_detects_dangling_arrow():
    # 'ghost' is referenced by the arrow but never created as a box.
    report = analyze_geometry([_box("a", 0, 0), _box("b", 600, 0), _arrow("e", "a", "ghost")])
    assert any(i.kind == "dangling_arrow" for i in report.issues)
    assert not report.has_overlap  # the boxes themselves are fine


def test_bound_arrow_is_not_dangling():
    report = analyze_geometry([_box("a", 0, 0), _box("b", 600, 0), _arrow("e", "a", "b")])
    assert not report.issues


def _container(cid: str, x: float, y: float, w: float, h: float) -> AgentAction:
    return AgentAction(type="create", shape=Shape(id=cid, type="container", x=x, y=y, w=w, h=h))


def _member(box_id: str, parent: str, x: float, y: float, w: float = 200) -> AgentAction:
    return AgentAction(
        type="create", shape=Shape(id=box_id, type="geo", x=x, y=y, w=w, h=80, parent_id=parent)
    )


def test_member_on_its_container_is_not_an_overlap():
    report = analyze_geometry([_container("g", 0, 0, 600, 400), _member("a", "g", 48, 56)])
    assert not report.issues


def test_siblings_inside_a_container_can_still_overlap():
    report = analyze_geometry(
        [_container("g", 0, 0, 600, 400), _member("a", "g", 48, 56), _member("b", "g", 60, 60)]
    )
    assert report.has_overlap


def test_container_overflow_detected():
    # member sticks out past the container's right edge
    report = analyze_geometry([_container("g", 0, 0, 300, 200), _member("a", "g", 200, 56)])
    assert any(i.kind == "container_overflow" for i in report.issues)


def test_box_bleeding_into_foreign_container_is_overlap():
    report = analyze_geometry(
        [
            _container("g1", 0, 0, 400, 300),
            _container("g2", 600, 0, 400, 300),
            _member("a", "g1", 350, 50),  # inside g1's scope but poking into… nothing yet
        ]
    )
    # 'a' overflows g1 AND stays clear of g2 → overflow yes, foreign overlap no
    assert any(i.kind == "container_overflow" for i in report.issues)

    report2 = analyze_geometry(
        [
            _container("g1", 0, 0, 400, 300),
            _container("g2", 450, 0, 400, 300),
            _member("a", "g1", 350, 50),  # pokes into g2's panel
        ]
    )
    assert report2.has_overlap


def test_containers_colliding_is_overlap():
    report = analyze_geometry(
        [_container("g1", 0, 0, 400, 300), _container("g2", 380, 0, 400, 300)]
    )
    assert report.has_overlap


def test_arrow_bound_to_container_is_valid():
    report = analyze_geometry(
        [_container("g", 0, 0, 400, 300), _box("a", 600, 0), _arrow("e", "a", "g")]
    )
    assert not report.issues


def test_arrow_routing_through_foreign_box_is_flagged():
    # a → c passes straight through b (all on one row); elbow route cuts b's rect
    report = analyze_geometry(
        [_box("a", 0, 0), _box("b", 400, 0), _box("c", 800, 0), _arrow("e", "a", "c")]
    )
    assert any(i.kind == "arrow_crossing" for i in report.issues)
    assert all(i.severity == "warning" for i in report.issues if i.kind == "arrow_crossing")


def test_clear_arrow_route_is_not_flagged():
    report = analyze_geometry([_box("a", 0, 0), _box("c", 800, 0), _arrow("e", "a", "c")])
    assert not any(i.kind == "arrow_crossing" for i in report.issues)


def test_colliding_edge_labels_are_flagged():
    # two labeled arrows sharing the same corridor midpoint
    actions = [
        _box("a", 0, 0),
        _box("b", 800, 0),
        _box("c", 0, 300),
        _box("d", 800, 300),
        AgentAction(
            type="create",
            shape=Shape(id="e1", type="arrow", x=0, y=0, from_id="a", to_id="d", text="yes"),
        ),
        AgentAction(
            type="create",
            shape=Shape(id="e2", type="arrow", x=0, y=0, from_id="c", to_id="b", text="no"),
        ),
    ]
    assert any(i.kind == "label_collision" for i in analyze_geometry(actions).issues)
