"""Rasterise the SVG app icons into the PNGs that phones actually accept.

Why this exists rather than just pointing the manifest at the SVGs:

  * iOS ignores an SVG `apple-touch-icon` completely. Without a PNG it puts a
    screenshot of the page on the home screen, which is the single most common
    reason an "app" looks uninstalled.
  * Chrome only surfaces the install UI in some builds when a real 192px PNG
    is present. The SVG entry satisfies the letter of the criteria and is then
    ignored in practice.

The SVGs stay the source of truth and this file *reads* them -- it does not
carry a copy of the path. An earlier version kept a `GLYPH_D` string literal
plus a check that the two matched. The check did fire, and comparing the two
strings by hand afterwards did not turn up a differing character, which is the
real argument: a hand-maintained duplicate of a data file is a liability whose
failure mode is "the build stops and nobody can see why". There is now only
one copy, so the question cannot arise.

No third-party dependency on purpose. Cairo and Pillow both want native wheels
that behave differently across the versions of Windows this has to build on, and
a build step that can fail to install is worse than one that cannot.

    python -m scripts.make_icons
"""

from __future__ import annotations

import math
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
ASSETS = REPO_ROOT / "assets"

# source SVG -> the "any" and "maskable" manifests both read these
SOURCE_ICONS = ("icon.svg", "icon-maskable.svg")

# Manifest icon sizes. Chrome wants a 192 and a 512; 180 is iOS's, handled
# separately below since it is the same artwork under a different name.
SIZES = (192, 512)
APPLE_SIZE = 180

# Rendering quality. Curves are flattened to SEGMENTS line segments, then the
# shape is sampled on an SS x SS grid and box-filtered down, which is what
# antialiases the edges.
SEGMENTS = 16
SS = 4


# --- SVG parsing ---------------------------------------------------------


def _local(tag: str) -> str:
    """Strip the {http://www.w3.org/2000/svg} namespace from a tag name."""
    return tag.rsplit("}", 1)[-1]


def _colour(value: str | None, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    """#RGB or #RRGGBB -> (r, g, b)."""
    if not value or not value.startswith("#"):
        return fallback
    digits = value[1:]
    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)
    if len(digits) != 6:
        return fallback
    return tuple(int(digits[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


# An affine transform as (a, b, c, d, e, f):
#     x' = a*x + c*y + e
#     y' = b*x + d*y + f
IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _multiply(outer: tuple, inner: tuple) -> tuple:
    """Return outer ∘ inner -- apply `inner` to a point, then `outer`."""
    a1, b1, c1, d1, e1, f1 = outer
    a2, b2, c2, d2, e2, f2 = inner
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


_TRANSFORM_RE = re.compile(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)")


def _transform_matrix(text: str | None, source: str = "svg") -> tuple:
    """Parse an SVG `transform` attribute into a single matrix.

    The icon SVGs use `translate(256 256) scale(11) translate(-12 -12)`, but
    supporting the rest of the grammar means an edit to the SVG that swaps in
    `matrix(...)` or `rotate(...)` still renders instead of being silently
    ignored.
    """
    matrix = IDENTITY
    if not text:
        return matrix
    for name, raw in _TRANSFORM_RE.findall(text):
        context = f"{source} transform: {name}({raw})"
        if name == "translate":
            args = _numbers(raw, 1, context)
            step = (1.0, 0.0, 0.0, 1.0, args[0], args[1] if len(args) > 1 else 0.0)
        elif name == "scale":
            args = _numbers(raw, 1, context)
            sx = args[0]
            sy = args[1] if len(args) > 1 else sx
            step = (sx, 0.0, 0.0, sy, 0.0, 0.0)
        elif name == "matrix":
            step = tuple(_numbers(raw, 6, context)[:6])
        elif name == "rotate":
            args = _numbers(raw, 1, context)
            angle = math.radians(args[0])
            cos, sin = math.cos(angle), math.sin(angle)
            step = (cos, sin, -sin, cos, 0.0, 0.0)
            if len(args) == 3:
                cx, cy = args[1], args[2]
                step = _multiply(
                    (1.0, 0.0, 0.0, 1.0, cx, cy),
                    _multiply(step, (1.0, 0.0, 0.0, 1.0, -cx, -cy)),
                )
        else:  # skewX / skewY -- not used by these icons, but trivial.
            args = _numbers(raw, 1, context)
            radians = math.radians(args[0])
            step = (
                (1.0, 0.0, math.tan(radians), 1.0, 0.0, 0.0) if name == "skewX"
                else (1.0, math.tan(radians), 0.0, 1.0, 0.0, 0.0)
            )
        matrix = _multiply(matrix, step)
    return matrix


def _apply(matrix: tuple, point: tuple[float, float]) -> tuple[float, float]:
    a, b, c, d, e, f = matrix
    return (a * point[0] + c * point[1] + e, b * point[0] + d * point[1] + f)


@dataclass
class IconSpec:
    """Everything needed to render one icon, read straight out of the SVG."""

    width: float
    height: float
    background: tuple[int, int, int]
    radius: float
    foreground: tuple[int, int, int]
    subpaths: list[list[tuple[float, float]]] = field(default_factory=list)


def _find(parent, tag: str, svg_path: Path, what: str):
    """First descendant with this tag, or a clear failure.

    A bare `next(...)` raises StopIteration, whose traceback says nothing about
    which file was at fault -- unhelpful when this runs inside a Docker build.
    """
    for element in parent.iter():
        if _local(element.tag) == tag:
            return element
    raise SystemExit(f"{svg_path.name}: no <{what}> found")


def _numbers(text: str, count: int, context: str) -> list[float]:
    """Parse `count` numbers out of a transform argument list, or fail."""
    values = [float(v) for v in re.split(r"[\s,]+", text.strip()) if v]
    if len(values) < count:
        raise SystemExit(f"{context}: expected {count} numbers, got {text.strip()!r}")
    return values


def read_icon(svg_path: Path) -> IconSpec:
    """Parse an icon SVG into user-space geometry."""
    root = ET.fromstring(svg_path.read_text(encoding="utf-8"))

    view_box = root.get("viewBox")
    if view_box:
        parts = _numbers(view_box, 4, f"{svg_path.name} viewBox")
        width, height = parts[2], parts[3]
    else:
        width = height = float(root.get("width") or 512)

    rect = _find(root, "rect", svg_path, "rect (the background)")
    group = _find(root, "g", svg_path, "g (the glyph group)")
    path = _find(group, "path", svg_path, "path (the glyph)")

    rect_width = float(rect.get("width") or width)
    rect_height = float(rect.get("height") or height)
    # No rx on the maskable icon, which is the point of it: Android crops to
    # whatever shape it likes, so the background has to bleed to the edges.
    radius = float(rect.get("rx") or rect.get("ry") or 0.0)
    if radius:
        radius = min(radius, rect_width / 2, rect_height / 2)

    spec = IconSpec(
        width=rect_width,
        height=rect_height,
        background=_colour(rect.get("fill"), (0xFF, 0xC2, 0x2E)),
        radius=radius,
        foreground=_colour(group.get("fill"), (0x16, 0x13, 0x0F)),
    )
    # The <g> carries the placement; without its transform the glyph would be
    # sitting at the origin instead of centred.
    matrix = _transform_matrix(group.get("transform"), svg_path.name)
    spec.subpaths = [
        [_apply(matrix, point) for point in sub]
        for sub in parse_path(path.get("d", ""))
    ]
    if not spec.subpaths:
        raise SystemExit(f"{svg_path.name}: no drawable path found")
    return spec


# --- SVG path ------------------------------------------------------------
#
# A small subset of the path grammar. The current glyph only uses M/C/S/L/H/V
# and Z, but arcs and quadratics are handled too: a parser that silently drops
# an `a` would render the next icon somebody draws as garbage rather than
# failing, and that is much harder to notice.

_COMMAND_ARITY = {
    "M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0,
}
_TOKEN_RE = re.compile(r"([MmLlHhVvCcSsQqTtAaZz])|(-?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?)")


def _tokenise(d: str):
    """Yield ('cmd', letter) and ('num', float) in document order."""
    for match in _TOKEN_RE.finditer(d):
        if match.group(1):
            yield ("cmd", match.group(1))
        else:
            yield ("num", float(match.group(2)))


def _arc_to_centre(x0, y0, rx, ry, angle, large_arc, sweep, x1, y1, out):
    """SVG arc -> centre parameterisation -> polyline points appended to `out`.

    Straight from the SVG 1.1 implementation notes (F.6.5), including the
    out-of-range radii correction the spec requires but few implementations
    bother with.
    """
    if x0 == x1 and y0 == y1:
        return
    rx, ry = abs(rx), abs(ry)
    if rx == 0 or ry == 0:
        out.append((x1, y1))
        return
    phi = math.radians(angle)
    cos_p, sin_p = math.cos(phi), math.sin(phi)

    # Step 1: into the unit-circle space.
    dx2, dy2 = (x0 - x1) / 2.0, (y0 - y1) / 2.0
    x1p = cos_p * dx2 + sin_p * dy2
    y1p = -sin_p * dx2 + cos_p * dy2

    # Step 2: grow radii that are too small to span the endpoints.
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:
        grow = math.sqrt(lam)
        rx, ry = rx * grow, ry * grow

    # Step 3: the centre, in unit-circle space.
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    factor = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large_arc == sweep:
        factor = -factor
    cxp = factor * rx * y1p / ry
    cyp = -factor * ry * x1p / rx

    # Step 4: back to user space.
    cx = cos_p * cxp - sin_p * cyp + (x0 + x1) / 2.0
    cy = sin_p * cxp + cos_p * cyp + (y0 + y1) / 2.0

    theta1 = math.atan2((y1p - cyp) / ry, (x1p - cxp) / rx)
    theta2 = math.atan2((-y1p - cyp) / ry, (-x1p - cxp) / rx)
    delta = theta2 - theta1
    if sweep == 0 and delta > 0:
        delta -= 2 * math.pi
    elif sweep == 1 and delta < 0:
        delta += 2 * math.pi

    steps = max(2, int(abs(delta) / (math.pi / SEGMENTS)) + 1)
    for i in range(1, steps + 1):
        theta = theta1 + delta * i / steps
        out.append((
            cx + rx * math.cos(theta) * cos_p - ry * math.sin(theta) * sin_p,
            cy + rx * math.cos(theta) * sin_p + ry * math.sin(theta) * cos_p,
        ))


def _cubic(p0, p1, p2, p3, out):
    for i in range(1, SEGMENTS + 1):
        t = i / SEGMENTS
        u = 1 - t
        out.append((
            u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
            u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1],
        ))


def parse_path(d: str) -> list[list[tuple[float, float]]]:
    """Flatten a path into a list of point lists, one per subpath.

    Arcs and curves become line segments, which is what the scanline filler
    needs. Each subpath is explicitly closed.
    """
    subpaths: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    cursor = (0.0, 0.0)
    start = (0.0, 0.0)
    last_cubic_control = None
    last_quad_control = None
    command = None
    pending: list[float] = []

    def flush_close():
        # Filling an open subpath implicitly closes it, so do the same here.
        if current:
            current.append(start)
            subpaths.append(current)

    for kind, value in _tokenise(d):
        if kind == "cmd":
            # A 'z' is handled here, one token late, because `command` still
            # holds the previous letter at the point the z is read.
            if command in ("Z", "z"):
                flush_close()
                current = []
            command = value
            pending = []
            continue

        pending.append(value)
        if command is None:
            continue
        arity = _COMMAND_ARITY[command.upper()]
        if len(pending) < arity:
            continue
        args = pending[:arity]
        pending = pending[arity:]
        upper = command.upper()
        relative = command.islower()
        ox, oy = cursor

        if upper == "M":
            point = (ox + args[0], oy + args[1]) if relative else (args[0], args[1])
            flush_close()
            current = [point]
            cursor = start = point
            # Subsequent pairs after a moveto are implicit linetos.
            command = "l" if relative else "L"
            last_cubic_control = last_quad_control = None
            continue
        if upper == "L":
            point = (ox + args[0], oy + args[1]) if relative else (args[0], args[1])
            current.append(point)
            cursor = point
        elif upper == "H":
            point = (ox + args[0], oy) if relative else (args[0], oy)
            current.append(point)
            cursor = point
        elif upper == "V":
            point = (ox, oy + args[0]) if relative else (ox, args[0])
            current.append(point)
            cursor = point
        elif upper == "C":
            if relative:
                c1, c2 = (ox + args[0], oy + args[1]), (ox + args[2], oy + args[3])
                end = (ox + args[4], oy + args[5])
            else:
                c1, c2 = (args[0], args[1]), (args[2], args[3])
                end = (args[4], args[5])
            _cubic(cursor, c1, c2, end, current)
            cursor, last_cubic_control = end, c2
        elif upper == "S":
            if relative:
                c2, end = (ox + args[0], oy + args[1]), (ox + args[2], oy + args[3])
            else:
                c2, end = (args[0], args[1]), (args[2], args[3])
            # Reflect the previous control point about the cursor; with no
            # predecessor the control point is the cursor itself.
            c1 = cursor if last_cubic_control is None else (
                2 * cursor[0] - last_cubic_control[0],
                2 * cursor[1] - last_cubic_control[1],
            )
            _cubic(cursor, c1, c2, end, current)
            cursor, last_cubic_control = end, c2
        elif upper == "Q":
            if relative:
                c1, end = (ox + args[0], oy + args[1]), (ox + args[2], oy + args[3])
            else:
                c1, end = (args[0], args[1]), (args[2], args[3])
            _cubic(cursor, c1, c1, end, current)
            cursor, last_quad_control = end, c1
        elif upper == "T":
            end = (ox + args[0], oy + args[1]) if relative else (args[0], args[1])
            c1 = cursor if last_quad_control is None else (
                2 * cursor[0] - last_quad_control[0],
                2 * cursor[1] - last_quad_control[1],
            )
            _cubic(cursor, c1, c1, end, current)
            cursor, last_quad_control = end, c1
        elif upper == "A":
            end = (ox + args[5], oy + args[6]) if relative else (args[5], args[6])
            _arc_to_centre(cursor[0], cursor[1], args[0], args[1], args[2],
                           int(args[3]), int(args[4]), end[0], end[1], current)
            cursor = end

        # An S reflects the previous *cubic* control point; anything else ends
        # that chain. A Q/T pair likewise forms its own reflection chain.
        last_cubic_control = last_cubic_control if upper in ("C", "S") else None
        if upper not in ("Q", "T"):
            last_quad_control = None

    flush_close()
    return [sub for sub in subpaths if len(sub) >= 3]


def rounded_rect(width: float, height: float, radius: float) -> list[list[tuple[float, float]]]:
    """A rounded rectangle as a polygon, corners approximated with cubics."""
    if radius <= 0:
        return [[(0.0, 0.0), (width, 0.0), (width, height), (0.0, height), (0.0, 0.0)]]

    k = 0.5522847498307936  # circle -> cubic Bezier constant
    r = min(radius, width / 2, height / 2)
    out: list[tuple[float, float]] = []
    for cx, cy, start_deg in (
        (width - r, r, -90.0),
        (width - r, height - r, 0.0),
        (r, height - r, 90.0),
        (r, r, 180.0),
    ):
        rad = math.radians(start_deg)
        quarter = math.pi / 2
        p0 = (cx + r * math.cos(rad), cy + r * math.sin(rad))
        # Always emit p0, including for corners after the first. _cubic starts
        # at t=1/SEGMENTS, so without this the straight run between two
        # corners would be a chord that slightly under-fills the shape.
        out.append(p0)
        p3 = (cx + r * math.cos(rad + quarter), cy + r * math.sin(rad + quarter))
        c1 = (p0[0] + k * r * math.cos(rad + quarter), p0[1] + k * r * math.sin(rad + quarter))
        c2 = (p3[0] - k * r * math.cos(rad), p3[1] - k * r * math.sin(rad))
        _cubic(p0, c1, c2, p3, out)
    out.append(out[0])
    return [out]


# --- scanline fill -------------------------------------------------------


def rasterise(subpaths: list[list[tuple[float, float]]], big: int) -> bytearray:
    """Fill already-pixel-space subpaths into a big x big 0/1 coverage mask."""
    coverage = bytearray(big * big)

    edges = []
    for sub in subpaths:
        for (x0, y0), (x1, y1) in zip(sub, sub[1:]):
            if y0 == y1:
                continue
            direction = 1
            if y0 > y1:  # normalise so y0 < y1, remembering the winding
                x0, y0, x1, y1 = x1, y1, x0, y0
                direction = -1
            edges.append((y0, y1, x0, (x1 - x0) / (y1 - y0), direction))
    if not edges:
        return coverage

    # Sort by top edge and keep a running active set, so each scanline only
    # tests edges that can actually cross it.
    edges.sort(key=lambda e: e[0])
    active: list[tuple] = []
    next_edge = 0

    for row in range(big):
        y = row + 0.5
        while next_edge < len(edges) and edges[next_edge][0] <= y:
            active.append(edges[next_edge])
            next_edge += 1
        if active:
            active = [e for e in active if e[1] > y]
        if not active:
            continue

        crossings = [
            (x_at_ymin + (y - ymin) * slope, direction)
            for ymin, ymax, x_at_ymin, slope, direction in active
            if ymin <= y < ymax
        ]
        if not crossings:
            continue
        crossings.sort()

        # Nonzero winding, which is the SVG default fill-rule.
        winding = 0
        span_start = 0.0
        base = row * big
        for x, direction in crossings:
            previous = winding
            winding += direction
            if previous == 0 and winding != 0:
                span_start = x
            elif previous != 0 and winding == 0:
                lo = max(0, int(math.floor(span_start)))
                hi = min(big, int(math.ceil(x)))
                if hi > lo:
                    coverage[base + lo:base + hi] = b"\x01" * (hi - lo)

    return coverage


def downsample(coverage: bytearray, size: int, supersample: int = SS) -> bytearray:
    """Box-filter a supersampled mask down to `size` x `size`, values 0..255."""
    out = bytearray(size * size)
    area = supersample * supersample
    big = size * supersample
    for y in range(size):
        for x in range(size):
            total = 0
            for sy in range(supersample):
                start = (y * supersample + sy) * big + x * supersample
                total += sum(coverage[start:start + supersample])
            out[y * size + x] = round(255 * total / area)
    return out


# --- PNG output ----------------------------------------------------------


def _chunk(tag: bytes, payload: bytes) -> bytes:
    return (struct.pack(">I", len(payload)) + tag + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))


def write_png(path: Path, size: int, pixels: bytes) -> None:
    """Write 8-bit RGBA. `pixels` is size*size*4 bytes."""
    stride = size * 4
    raw = bytearray()
    for y in range(size):
        # Filter 0 (None). Every row gets its own bytes but they share one
        # zlib stream, so the file still compresses well.
        raw.append(0)
        raw.extend(pixels[y * stride:(y + 1) * stride])

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )


def render(spec: IconSpec, size: int) -> bytes:
    """Composite background + glyph for one output size, as RGBA bytes."""
    big = size * SS
    # User units -> supersampled pixels, taken from the SVG's own viewBox
    # rather than a hardcoded 512. One factor for both axes, which is correct
    # because these icons are square; a non-square one would need the aspect
    # ratio handled separately.
    to_px = big / spec.width

    def pixels(sub: list[tuple[float, float]]) -> list[tuple[float, float]]:
        return [(x * to_px, y * to_px) for x, y in sub]

    glyph_cov = downsample(
        rasterise([pixels(sub) for sub in spec.subpaths], big), size
    )
    if spec.radius > 0:
        bg_cov = downsample(
            rasterise([pixels(sub) for sub in rounded_rect(spec.width, spec.height, spec.radius)], big),
            size,
        )
    else:
        # Full-bleed, as the maskable icon wants: Android crops this to
        # whatever shape it likes, so there must be no transparent corners.
        bg_cov = bytearray(b"\xff" * (size * size))

    red, green, blue = spec.foreground
    out = bytearray(size * size * 4)
    for i in range(size * size):
        alpha = bg_cov[i]
        if alpha == 0:
            continue  # transparent: leave RGB at 0 so edges cannot fringe
        g = glyph_cov[i] / 255.0
        out[i * 4 + 0] = round(spec.background[0] * (1 - g) + red * g)
        out[i * 4 + 1] = round(spec.background[1] * (1 - g) + green * g)
        out[i * 4 + 2] = round(spec.background[2] * (1 - g) + blue * g)
        out[i * 4 + 3] = alpha
    return bytes(out)


def _glyph_coverage(spec: IconSpec, size: int) -> float:
    """Fraction of the icon the glyph actually inks, for the self-check."""
    big = size * SS
    to_px = big / spec.width
    mask = rasterise(
        [[(x * to_px, y * to_px) for x, y in sub] for sub in spec.subpaths], big
    )
    return sum(mask) / (big * big)


def main() -> int:
    specs = {}
    for name in SOURCE_ICONS:
        path = ASSETS / name
        if not path.is_file():
            raise SystemExit(f"missing source icon: {path}")
        specs[name] = read_icon(path)

    for name, spec in specs.items():
        # A path parser bug would otherwise ship a blank yellow square, which
        # looks plausible enough to go unnoticed until someone installs it.
        coverage = _glyph_coverage(spec, 128)
        if not 0.01 < coverage < 0.9:
            raise SystemExit(
                f"{name}: the glyph inks {coverage:.1%} of the icon. That means "
                f"the path parser is wrong, not that the artwork is."
            )

        # icon.svg -> icon-192.png; icon-maskable.svg -> icon-maskable-192.png
        stem = name[:-4]
        print(f"  {name}: {len(spec.subpaths)} subpaths, glyph covers {coverage:.1%}")
        for size in SIZES:
            target = ASSETS / f"{stem}-{size}.png"
            write_png(target, size, render(spec, size))
            print(f"  {target.relative_to(REPO_ROOT)}  ({target.stat().st_size // 1024} KB)")

    # iOS reads apple-touch-icon and will not accept SVG. Same artwork as the
    # "any" icon, at the size iOS asks for.
    apple = ASSETS / "apple-touch-icon.png"
    write_png(apple, APPLE_SIZE, render(specs["icon.svg"], APPLE_SIZE))
    print(f"  {apple.relative_to(REPO_ROOT)}  ({apple.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
