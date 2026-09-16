"""Check explicitly annotated SVG geometry, without guessing browser text bounds.

The HTML remains the only geometry source. Unmarked SVG is outside this check;
rectangular nodes/label masks and line/polyline edges use SVG user coordinates.
"""
from __future__ import annotations

from html.parser import HTMLParser
import math
import re


NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
MARKS = ("data-node", "data-edge", "data-label-for")


def numbers(value: str) -> list[float]:
    if not isinstance(value, str):
        raise ValueError("geometry attribute requires a numeric value")
    if re.sub(NUMBER, "", value).strip(" ,\t\r\n"):
        raise ValueError("geometry must use numeric SVG user coordinates")
    result = [float(n) for n in NUMBER.findall(value)]
    if not result or not all(math.isfinite(n) for n in result):
        raise ValueError("geometry must contain finite numbers")
    return result


def scalar(attrs: dict, key: str) -> float:
    value = numbers(attrs.get(key, "0"))
    if len(value) != 1:
        raise ValueError(f"{key} must be one number")
    return value[0]


def overlaps(a, b):
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def crosses(start, end, box):
    """Open-rectangle clipping: grazing a boundary is not crossing its content."""
    low, high = 0.0, 1.0
    for axis in (0, 1):
        delta = end[axis] - start[axis]
        if delta == 0:
            if not box[axis] < start[axis] < box[axis + 2]:
                return False
            continue
        a = (box[axis] - start[axis]) / delta
        b = (box[axis + 2] - start[axis]) / delta
        low, high = max(low, min(a, b)), min(high, max(a, b))
    return low < high


def endpoint_ok(point, other, box):
    x, y = point
    left, top, right, bottom = box
    # Up to 8 user units allows the board's intentional 4px standoff.
    sides = [(abs(x-left), top <= y <= bottom and x <= left, (-1, 0)),
             (abs(x-right), top <= y <= bottom and x >= right, (1, 0)),
             (abs(y-top), left <= x <= right and y <= top, (0, -1)),
             (abs(y-bottom), left <= x <= right and y >= bottom, (0, 1))]
    dx, dy = other[0]-x, other[1]-y
    # At the target, the preceding point must also lie outward from its edge.
    return any(distance <= 8 and within and dx*nx + dy*ny > 0
               for distance, within, (nx, ny) in sides)


class DiagramParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.scopes = []
        self.active = []
        self.issues = []

    def issue(self, line, message):
        self.issues.append((line, message))

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "svg":
            scope = {"nodes": {}, "edges": {}, "labels": {}, "unmarked_edges": []}
            self.scopes.append(scope)
            self.active.append(scope)
        if not self.active:
            return
        inherited = self.stack[-1][1] if self.stack else False
        unsupported = inherited or "transform" in attrs or "style" in attrs
        self.stack.append((tag, unsupported))
        marked = [key for key in MARKS if key in attrs]
        if not marked:
            if "data-from" in attrs or "data-to" in attrs:
                self.active[-1]["unmarked_edges"].append(self.getpos()[0])
            return
        line = self.getpos()[0]
        try:
            if len(marked) != 1 or not attrs[marked[0]]:
                raise ValueError("use one nonempty semantic marker per element")
            if unsupported:
                raise ValueError("marked geometry needs direct coordinates, without ancestor transform/style")
            kind = marked[0]
            name = attrs[kind]
            collection = {"data-node": "nodes", "data-edge": "edges", "data-label-for": "labels"}[kind]
            target = self.active[-1][collection]
            if name in target:
                raise ValueError(f"duplicate {kind} {name!r}")
            if kind == "data-edge":
                if tag == "line":
                    points = [(scalar(attrs, "x1"), scalar(attrs, "y1")),
                              (scalar(attrs, "x2"), scalar(attrs, "y2"))]
                elif tag == "polyline":
                    coords = numbers(attrs.get("points", ""))
                    if len(coords) < 4 or len(coords) % 2:
                        raise ValueError("polyline needs at least two complete points")
                    points = list(zip(coords[::2], coords[1::2]))
                else:
                    raise ValueError("mark the line/polyline shaft, not its arrowhead or a path")
                if any(a == b for a, b in zip(points, points[1:])):
                    raise ValueError("edge has a zero-length segment")
                target[name] = (line, points, attrs.get("data-from"), attrs.get("data-to"))
            else:
                if tag != "rect":
                    raise ValueError("nodes and label masks must be rect elements")
                x, y, w, h = (scalar(attrs, k) for k in ("x", "y", "width", "height"))
                if w <= 0 or h <= 0 or not all(math.isfinite(v) for v in (x+w, y+h)):
                    raise ValueError("rectangle width and height must be positive")
                target[name] = (line, (x, y, x+w, y+h))
        except ValueError as error:
            self.issue(line, str(error))

    def handle_endtag(self, tag):
        if not self.active:
            return
        # HTML void elements outside SVG never enter this stack.
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()
        if tag == "svg":
            self.active.pop()

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def validate(self):
        for scope in self.scopes:
            nodes, edges, labels = (scope[k] for k in ("nodes", "edges", "labels"))
            if nodes or edges or labels:
                for line in scope["unmarked_edges"]:
                    self.issue(line, "relationship endpoints require data-edge")
            for group, kind in ((nodes, "nodes"), (labels, "label masks")):
                entries = list(group.items())
                for i, (name, (line, box)) in enumerate(entries):
                    for other, (_, other_box) in entries[i+1:]:
                        if overlaps(box, other_box):
                            self.issue(line, f"{kind} {name!r} and {other!r} overlap")
            for name, (line, box) in labels.items():
                if name not in edges:
                    self.issue(line, f"label mask {name!r} has no matching edge")
                for node, (_, node_box) in nodes.items():
                    if overlaps(box, node_box):
                        self.issue(line, f"label mask {name!r} overlaps node {node!r}")
            for name, (line, points, source, target) in edges.items():
                if source not in nodes or target not in nodes:
                    self.issue(line, f"edge {name!r} references missing node: {source!r} -> {target!r}")
                    continue
                for node, point, other in ((source, points[0], points[1]),
                                           (target, points[-1], points[-2])):
                    if not endpoint_ok(point, other, nodes[node][1]):
                        self.issue(line, f"edge {name!r} does not attach outward to node {node!r}; move endpoint/route")
                for node, (_, box) in nodes.items():
                    if any(crosses(a, b, box) for a, b in zip(points, points[1:])):
                        self.issue(line, f"edge {name!r} crosses node {node!r}; move route or node")
                for label, (_, box) in labels.items():
                    if label != name and any(crosses(a, b, box) for a, b in zip(points, points[1:])):
                        self.issue(line, f"edge {name!r} crosses label mask {label!r}; move route or mask")
        return self.issues


def scan_geometry(html: str) -> list[tuple[int, str]]:
    parser = DiagramParser()
    parser.feed(html)
    parser.close()
    return parser.validate()
