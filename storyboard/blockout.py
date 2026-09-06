"""Procedural storyboard blockouts.

Blockouts are the composition layer: camera height, shot size, where bodies sit
in frame. They are the input to the generation step (img2img / ControlNet
scribble), and they stand in as readable placeholders until panels are rendered.

    python3 blockout.py            # writes blockouts/shot_XX.svg
"""

import json
import math
import os
import random

W, H = 960, 540
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "blockouts")

INK = "#14161a"
GREY = "#6b7280"


class Sketch:
    """Accumulates rough, hand-drawn-looking SVG geometry."""

    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self.parts = []

    def _j(self, amp):
        return self.rng.uniform(-amp, amp)

    def line(self, x1, y1, x2, y2, sw=2.0, amp=2.5, passes=2, op=1.0, color=INK):
        """A single stroke, drawn a couple of times with slight wobble."""
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        for _ in range(passes):
            bow = self.rng.uniform(-amp, amp)
            cx = (x1 + x2) / 2 + nx * bow
            cy = (y1 + y2) / 2 + ny * bow
            sx, sy = x1 + self._j(amp * 0.4), y1 + self._j(amp * 0.4)
            ex, ey = x2 + self._j(amp * 0.4), y2 + self._j(amp * 0.4)
            self.parts.append(
                f'<path d="M{sx:.1f},{sy:.1f} Q{cx:.1f},{cy:.1f} {ex:.1f},{ey:.1f}" '
                f'fill="none" stroke="{color}" stroke-width="{sw * self.rng.uniform(0.8, 1.2):.2f}" '
                f'stroke-linecap="round" opacity="{op * self.rng.uniform(0.72, 1.0):.2f}"/>'
            )

    def poly(self, pts, close=False, **kw):
        seq = list(pts) + ([pts[0]] if close else [])
        for (x1, y1), (x2, y2) in zip(seq, seq[1:]):
            self.line(x1, y1, x2, y2, **kw)

    def ellipse(self, cx, cy, rx, ry, steps=14, rot=0.0, **kw):
        pts = []
        for i in range(steps):
            a = 2 * math.pi * i / steps
            x, y = rx * math.cos(a), ry * math.sin(a)
            pts.append((cx + x * math.cos(rot) - y * math.sin(rot),
                        cy + x * math.sin(rot) + y * math.cos(rot)))
        self.poly(pts, close=True, **kw)

    def fill(self, pts, color=INK, op=1.0, jitter=3.0):
        """A filled mass with a ragged edge — hair, silhouettes, shadow."""
        d = " ".join(
            f"{'M' if i == 0 else 'L'}{x + self._j(jitter):.1f},{y + self._j(jitter):.1f}"
            for i, (x, y) in enumerate(pts)
        )
        self.parts.append(f'<path d="{d} Z" fill="{color}" opacity="{op:.2f}"/>')

    def wash(self, pts, op=0.14):
        self.fill(pts, color=GREY, op=op, jitter=1.5)

    def hatch(self, x, y, w, h, angle=-58, gap=9, sw=1.1, op=0.5):
        """Diagonal shading confined to a box."""
        cid = f"c{len(self.parts)}"
        self.parts.append(
            f'<clipPath id="{cid}"><rect x="{x}" y="{y}" width="{w}" height="{h}"/></clipPath>'
        )
        self.parts.append(f'<g clip-path="url(#{cid})">')
        rad = math.radians(angle)
        dx, dy = math.cos(rad), math.sin(rad)
        span = int((w + h) / gap) + 2
        for i in range(-span, span):
            px, py = x + i * gap, y
            self.line(px - dx * 900, py - dy * 900, px + dx * 900, py + dy * 900,
                      sw=sw, amp=1.4, passes=1, op=op)
        self.parts.append("</g>")

    def svg(self):
        body = "\n    ".join(self.parts)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'width="{W}" height="{H}" role="img">\n'
            f'    <rect width="{W}" height="{H}" fill="#f4f2ee"/>\n    {body}\n</svg>'
        )


# --- figure primitives -------------------------------------------------------
#
# Figures are built on a jointed skeleton rather than drawn as outlines, so the
# things that make a body read as a person survive: contrapposto (weight on one
# leg tilts the hips one way and the shoulders the other), limbs that taper from
# joint to joint, and a skull that carries a jaw narrower than its cranium.


def arc(cx, cy, rx, ry, a0, a1, n=14):
    """Points along an ellipse arc. Angles in radians, -pi/2 is straight up."""
    return [(cx + rx * math.cos(a0 + (a1 - a0) * i / (n - 1)),
             cy + ry * math.sin(a0 + (a1 - a0) * i / (n - 1))) for i in range(n)]


def tube(sk, pts, radii, sw=1.8, amp=1.4, cap=True):
    """A limb segment with volume: two contours offset around a centre line."""
    left, right = [], []
    for i, ((px, py), r) in enumerate(zip(pts, radii)):
        if i == 0:
            dx, dy = pts[1][0] - px, pts[1][1] - py
        elif i == len(pts) - 1:
            dx, dy = px - pts[-2][0], py - pts[-2][1]
        else:
            dx, dy = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        left.append((px + nx * r, py + ny * r))
        right.append((px - nx * r, py - ny * r))
    sk.poly(left, sw=sw, amp=amp, passes=1)
    sk.poly(right, sw=sw, amp=amp, passes=1)
    if cap:
        sk.line(*left[-1], *right[-1], sw=sw * 0.8, amp=amp * 0.7, passes=1, op=0.7)


def hair_mass(sk, cx, cy, rx, ry, style="short", op=0.9):
    """A crescent following the skull, so hair sits on the head, not over it."""
    # Ends at the temples, above the brow — a mass that drops past eye level
    # stops reading as hair and starts reading as a hood.
    outer = arc(cx, cy, rx * 1.06, ry * 1.08, -math.pi * 0.95, -math.pi * 0.05)
    inner = arc(cx, cy + ry * 0.06, rx * 0.93, ry * 0.68, -math.pi * 0.05, -math.pi * 0.95)
    sk.fill(outer + inner, op=op, jitter=rx * 0.05)
    for side in (-1, 1):                                  # temple strands, not slabs
        sk.line(cx + side * rx * 0.94, cy - ry * 0.30,
                cx + side * rx * 1.02, cy + ry * 0.16,
                sw=1.3, amp=1.5, passes=1, op=0.45)
    if style == "tied":
        sk.ellipse(cx + rx * 1.10, cy - ry * 0.52, rx * 0.31, ry * 0.27,
                   steps=11, sw=1.5, amp=1.0)


def skull(sk, cx, cy, r, turn=0.0, hair="short"):
    """Cranium plus jaw. The jaw taper is what stops a head reading as an egg."""
    off = turn * r
    sk.ellipse(cx, cy, r * 0.88, r, steps=18, sw=1.9, amp=1.4)
    chin = (cx + off * 1.6, cy + r * 1.38)
    sk.poly([(cx - r * 0.80 + off * 0.3, cy + r * 0.16),
             (cx - r * 0.62 + off * 0.7, cy + r * 0.86),
             (cx - r * 0.24 + off * 1.3, cy + r * 1.28), chin,
             (cx + r * 0.24 + off * 1.3, cy + r * 1.28),
             (cx + r * 0.62 + off * 0.7, cy + r * 0.86),
             (cx + r * 0.80 + off * 0.3, cy + r * 0.16)], sw=1.8, amp=1.1, passes=1)
    hair_mass(sk, cx, cy, r * 0.88, r, style=hair)
    return chin


def mitt(sk, cx, cy, r, angle):
    """A hand as a small closed mass — a ring reads as a bracelet."""
    pts = arc(cx, cy, r * 0.80, r * 1.05, -math.pi, math.pi, n=11)
    rot = [(cx + (px - cx) * math.cos(angle) - (py - cy) * math.sin(angle),
            cy + (px - cx) * math.sin(angle) + (py - cy) * math.cos(angle))
           for px, py in pts]
    sk.fill(rot, color=GREY, op=0.30, jitter=r * 0.10)
    sk.poly(rot, close=True, sw=1.5, amp=0.9, passes=1)


def figure(sk, x, ground, h, pose="stand", hair="short", flip=False,
           weight=1, build="med", turn=-0.1):
    """Blocked-in human on a jointed skeleton. (x, ground) is the feet."""
    s = -1 if flip else 1
    weight *= s
    top = ground - h
    sw_half = h * (0.128 if build == "broad" else 0.113)
    waist_half, hip_half = h * 0.058, h * 0.078
    r_head = h * 0.052

    # Contrapposto: weight-bearing hip rides up, that shoulder drops.
    hip_tilt = -weight * h * 0.014
    sh_tilt = weight * h * 0.013
    sway = weight * h * 0.012

    head_cy = top + r_head * 1.22
    chin = skull(sk, x + turn * h * 0.008, head_cy, r_head, turn=turn, hair=hair)

    sh_y = top + h * 0.182
    sl = (x - sw_half, sh_y + sh_tilt)
    sr = (x + sw_half, sh_y - sh_tilt)
    waist_y, hip_y = top + h * 0.408, top + h * 0.487
    wl = (x - waist_half + sway * 0.5, waist_y)
    wr = (x + waist_half + sway * 0.5, waist_y)
    hl = (x - hip_half + sway, hip_y + hip_tilt)
    hr = (x + hip_half + sway, hip_y - hip_tilt)

    tube(sk, [(chin[0], chin[1] - r_head * 0.12), ((chin[0] + x) / 2, sh_y - h * 0.010)],
         [r_head * 0.40, r_head * 0.54], sw=1.6, amp=1.0, cap=False)
    sk.poly([sl, (x + turn * h * 0.005, sh_y - h * 0.030), sr], sw=2.0, amp=1.5)

    # torso: shoulders clearly wider than waist, pelvis flaring back out
    sk.poly([sl, (x - sw_half * 0.92, top + h * 0.30), wl, hl], sw=2.1, amp=1.7, passes=1)
    sk.poly([sr, (x + sw_half * 0.92, top + h * 0.30), wr, hr], sw=2.1, amp=1.7, passes=1)
    sk.line(hl[0], hl[1], hr[0], hr[1], sw=1.7, amp=1.3, passes=1, op=0.55)
    for fy in (top + h * 0.355, top + h * 0.445):
        sk.line(x - waist_half * 0.85 + sway, fy, x + waist_half * 0.75 + sway,
                fy - h * 0.006, sw=1.4, amp=1.5, passes=1, op=0.42)
    sk.hatch(x + (h * 0.030 if weight < 0 else -h * 0.098), sh_y,
             h * 0.068, h * 0.30, angle=-64, gap=7, sw=1.0, op=0.28)

    # arms
    el_y, wr_y = top + h * 0.398, top + h * 0.508
    for side, sh in ((-1, sl), (1, sr)):
        if pose == "arms_up":
            joints = [sh, (sh[0] + side * sw_half * 0.44, sh_y - h * 0.088),
                      (sh[0] + side * sw_half * 0.24, sh_y - h * 0.208)]
        elif pose == "reach" and side == s:
            joints = [sh, (sh[0] + side * sw_half * 0.74, sh_y + h * 0.045),
                      (sh[0] + side * sw_half * 1.48, sh_y + h * 0.012)]
        else:
            joints = [sh, (sh[0] + side * sw_half * 0.20, el_y),
                      (sh[0] + side * sw_half * 0.06, wr_y)]
        tube(sk, joints, [h * 0.030, h * 0.022, h * 0.016], sw=1.8, amp=1.3)
        hx, hy = joints[-1]
        dx, dy = hx - joints[-2][0], hy - joints[-2][1]
        d = math.hypot(dx, dy) or 1
        mitt(sk, hx + dx / d * h * 0.020, hy + dy / d * h * 0.020, h * 0.024,
             math.atan2(dy, dx) - math.pi / 2)

    # legs — the weight leg runs straight, the free leg bends and trails
    knee_y, ankle_y = top + h * 0.730, top + h * 0.960
    for side, hipj in ((-1, hl), (1, hr)):
        bearing = (side == weight)
        kx = hipj[0] + side * h * (0.004 if bearing else 0.020)
        ax = hipj[0] + side * h * (0.001 if bearing else 0.042)
        tube(sk, [hipj, (kx, knee_y + (0 if bearing else h * 0.010)), (ax, ankle_y)],
             [h * 0.050, h * 0.032, h * 0.021], sw=1.9, amp=1.4, cap=False)
        sk.poly([(ax - h * 0.020, ankle_y), (ax - h * 0.016, ground),
                 (ax + side * h * 0.048, ground), (ax + h * 0.016, ankle_y)],
                sw=1.7, amp=1.2, passes=1)
        if not bearing:
            sk.line(kx - h * 0.026, knee_y - h * 0.010, kx + h * 0.022,
                    knee_y - h * 0.016, sw=1.3, amp=1.3, passes=1, op=0.4)


def face_closeup(sk, cx, cy, r, mouth_open=0.5, turn=-0.12, hair="tied"):
    """Head filling frame. The reaction shot lives or dies on this one."""
    off = turn * r
    sk.ellipse(cx, cy, r * 0.82, r * 0.92, steps=20, sw=2.2, amp=1.8)
    chin_y = cy + r * 1.32
    jaw = [(cx - r * 0.75 + off * 0.3, cy + r * 0.14),
           (cx - r * 0.66 + off * 0.6, cy + r * 0.60),
           (cx - r * 0.46 + off * 1.0, cy + r * 1.02),
           (cx - r * 0.18 + off * 1.4, chin_y - r * 0.06),
           (cx + off * 1.7, chin_y),
           (cx + r * 0.19 + off * 1.4, chin_y - r * 0.06),
           (cx + r * 0.47 + off * 1.0, cy + r * 1.02),
           (cx + r * 0.67 + off * 0.6, cy + r * 0.60),
           (cx + r * 0.76 + off * 0.3, cy + r * 0.14)]
    sk.poly(jaw, sw=2.1, amp=1.4, passes=1)

    ey = cy + r * 0.10
    for side in (-1, 1):
        ex = cx + side * r * 0.31 + off * (1.25 if side * turn < 0 else 0.75)
        w, hgt = r * 0.235, r * 0.145
        sk.poly([(ex - w, ey + hgt * 0.10), (ex - w * 0.42, ey - hgt),
                 (ex + w * 0.42, ey - hgt * 0.86), (ex + w, ey - hgt * 0.05)],
                sw=2.0, amp=0.8, passes=1)
        sk.poly([(ex - w, ey + hgt * 0.10), (ex - w * 0.28, ey + hgt * 0.90),
                 (ex + w * 0.48, ey + hgt * 0.70), (ex + w, ey - hgt * 0.05)],
                sw=1.4, amp=0.7, passes=1)
        sk.ellipse(ex + off * 0.15, ey + hgt * 0.02, r * 0.098, r * 0.104,
                   steps=12, sw=1.4, amp=0.6)
        sk.fill(arc(ex + off * 0.15, ey + hgt * 0.02, r * 0.050, r * 0.052,
                    -math.pi, math.pi, n=11), op=0.88, jitter=r * 0.006)
        sk.poly([(ex - w * 1.10, ey - r * 0.34), (ex - w * 0.15, ey - r * 0.46),
                 (ex + w * 1.00, ey - r * 0.34)], sw=2.6, amp=1.1, passes=1)
        sk.hatch(ex - w * 1.05, ey - r * 0.30, w * 2.1, r * 0.15,
                 angle=-70, gap=6, sw=0.9, op=0.26)

    nx = cx + off * 1.5
    sk.line(cx + off * 0.5, cy + r * 0.02, nx - r * 0.07, cy + r * 0.46,
            sw=1.3, amp=0.9, passes=1, op=0.45)
    sk.poly(arc(nx - r * 0.01, cy + r * 0.52, r * 0.115, r * 0.085, -0.35, math.pi + 0.35, n=9),
            sw=1.7, amp=0.7, passes=1)
    for side in (-1, 1):
        sk.line(nx + side * r * 0.125, cy + r * 0.46,
                nx + side * r * 0.145, cy + r * 0.545, sw=1.5, amp=0.5, passes=1, op=0.65)
    sk.hatch(nx - r * 0.16, cy + r * 0.50, r * 0.30, r * 0.12,
             angle=-72, gap=6, sw=0.9, op=0.22)

    my = cy + r * 0.86
    gap = r * (0.05 + 0.14 * mouth_open)
    sk.poly([(nx - r * 0.23, my), (nx - r * 0.09, my - r * 0.050),
             (nx + off * 0.2, my - r * 0.018), (nx + r * 0.10, my - r * 0.054),
             (nx + r * 0.23, my)], sw=1.8, amp=0.7, passes=1)
    sk.poly([(nx - r * 0.23, my), (nx - r * 0.05, my + gap),
             (nx + r * 0.15, my + gap * 0.80), (nx + r * 0.23, my)],
            sw=1.6, amp=0.7, passes=1)
    if mouth_open > 0.35:
        sk.hatch(nx - r * 0.20, my + r * 0.006, r * 0.40, gap * 0.72,
                 angle=-80, gap=5, sw=0.9, op=0.42)
    sk.line(nx - r * 0.11, my + gap + r * 0.11, nx + r * 0.13, my + gap + r * 0.09,
            sw=1.2, amp=0.9, passes=1, op=0.30)

    ear_side = 1 if turn < 0 else -1
    sk.ellipse(cx + ear_side * r * 0.78 + off * 0.4, cy + r * 0.22,
               r * 0.10, r * 0.19, steps=10, sw=1.5, amp=0.9)

    # neck springs from the jaw corners, not from thin air
    sk.poly([(jaw[2][0] + r * 0.06, jaw[2][1] + r * 0.10),
             (cx - r * 0.34, chin_y + r * 0.66)], sw=1.9, amp=1.2, passes=1)
    sk.poly([(jaw[6][0] - r * 0.06, jaw[6][1] + r * 0.10),
             (cx + r * 0.38, chin_y + r * 0.64)], sw=1.9, amp=1.2, passes=1)
    sk.hatch(cx - r * 0.32, chin_y - r * 0.04, r * 0.70, r * 0.32,
             angle=-58, gap=7, sw=1.0, op=0.28)

    hair_mass(sk, cx, cy, r * 0.82, r * 0.92, style=hair, op=0.92)
    for i in range(5):
        sx = cx - r * 0.66 + i * r * 0.33
        sk.line(sx, cy - r * 0.64, sx + r * 0.09, cy - r * 0.26,
                sw=1.1, amp=1.4, passes=1, op=0.30)


# --- panels ------------------------------------------------------------------

def shot_09():
    """OTS past Sable, deep to Roon in the doorway. Camera at bench height."""
    sk = Sketch(9)
    sk.wash([(0, 0), (W, 0), (W, 320), (0, 300)], op=0.10)
    for y in (58, 96, 134):                                     # roof beams
        sk.line(120, y, W, y - 16, sw=1.6, amp=3.0, op=0.55)
    sk.poly([(150, 30), (150, 300)], sw=1.5, amp=2.5, op=0.4)
    sk.poly([(0, 250), (520, 232)], sw=1.7, amp=3.0, op=0.5)    # far wall / floor line
    sk.poly([(756, 208), (W, 200)], sw=1.7, amp=3.0, op=0.5)

    doorway = [(556, 96), (742, 92), (742, 352), (556, 356)]     # light source, deep
    sk.wash(doorway, op=0.06)
    sk.poly(doorway, close=True, sw=2.4, amp=2.2)
    figure(sk, 648, 344, 246, pose="stand", hair="tied", weight=-1, turn=-0.22)
    sk.hatch(556, 250, 186, 106, angle=-62, gap=13, op=0.28)

    sk.poly([(60, 470), (470, 372), (W, 430)], sw=2.6, amp=3.0)  # bench edge
    sk.line(470, 372, 470, 540, sw=2.0, amp=2.4, op=0.6)
    sk.hatch(470, 372, 490, 168, angle=-55, gap=14, op=0.22)

    # foreground head + shoulder, held as a dark mass
    skull_pts = arc(214, 392, 118, 128, -math.pi, 0, n=16)
    sk.fill(skull_pts + [(340, 452), (392, 540), (40, 540), (92, 448)],
            op=0.93, jitter=4.0)
    sk.poly([(30, 540), (74, 452), (150, 420)], sw=3.0, amp=3.5, op=0.7)
    return sk


def shot_10():
    """CU Roon. Reaction. Eyeline just off lens."""
    sk = Sketch(10)
    for y in (120, 176, 402, 452):
        sk.line(40, y, W - 40, y - 10, sw=1.5, amp=3.5, op=0.28)
    sk.line(806, 60, 846, 490, sw=1.6, amp=3.0, op=0.3)
    face_closeup(sk, 468, 246, 156, mouth_open=0.60, turn=-0.13, hair="tied")
    sk.poly([(214, 540), (286, 486), (400, 462)], sw=2.5, amp=3.0)
    sk.poly([(548, 458), (664, 484), (734, 540)], sw=2.5, amp=3.0)
    for x in (300, 640):                                        # breath / snap ticks
        sk.line(x, 210, x + 22, 196, sw=1.8, amp=1.5, op=0.55)
        sk.line(x - 6, 236, x + 16, 226, sw=1.8, amp=1.5, op=0.55)
    return sk


def shot_11():
    """Low angle on Sable, pinned under the rig. Camera on the floor."""
    sk = Sketch(11)
    for x in (60, 250, 700, 900):                               # converging verticals
        sk.line(x, 540, 480 + (x - 480) * 0.30, 40, sw=1.7, amp=3.0, op=0.4)
    sk.wash([(0, 0), (W, 0), (W, 150), (0, 132)], op=0.12)

    rig = [(24, 196), (W - 24, 150), (W - 24, 262), (24, 306)]  # gantry across frame
    sk.wash(rig, op=0.16)
    sk.poly(rig, close=True, sw=3.0, amp=2.6)
    for x in (150, 300, 660, 810):
        sk.line(x, 196 - (x / W) * 46 + 6, x, 306 - (x / W) * 44 - 6, sw=1.8, amp=2.0, op=0.6)
    sk.hatch(24, 236, 912, 70, angle=-50, gap=16, op=0.2)

    figure(sk, 484, 540, 462, pose="arms_up", hair="short", weight=1,
           build="broad", turn=0.06)
    for i, x in enumerate((196, 250, 706, 764)):                # strain lines
        sk.line(x, 250 + i * 8, x + (-58 if x < 480 else 58), 200 + i * 8, sw=2.0, amp=1.6, op=0.6)
    return sk


def shot_12():
    """Wide two-shot. Neither of them moves. Hold."""
    sk = Sketch(12)
    sk.wash([(0, 0), (W, 0), (W, 186), (0, 172)], op=0.09)
    sk.poly([(0, 172), (W, 186)], sw=2.0, amp=3.0)
    for x in (120, 300, 520, 760):
        sk.line(x, 180, x - 90 + (x - 480) * 0.30, 540, sw=1.4, amp=3.0, op=0.22)
    mass = [(716, 470), (716, 150), (928, 128), (948, 470)]     # machine bulk, frame right
    sk.wash(mass, op=0.18)
    sk.poly(mass, close=True, sw=2.6, amp=2.6)
    sk.hatch(716, 250, 232, 220, angle=-60, gap=13, op=0.26)
    figure(sk, 262, 472, 236, pose="stand", hair="short", weight=1,
           build="broad", turn=0.16)
    figure(sk, 572, 452, 212, pose="stand", hair="tied", flip=True,
           weight=-1, turn=-0.18)
    sk.line(300, 380, 546, 366, sw=1.3, amp=2.0, op=0.22)       # eyeline
    return sk


def shot_13():
    """Insert. Her hands, still on the coupling. She hasn't let go."""
    sk = Sketch(13)
    sk.wash([(0, 340), (W, 300), (W, 540), (0, 540)], op=0.13)
    sk.poly([(0, 340), (W, 300)], sw=2.2, amp=3.0)
    cyl = [(150, 250), (810, 214), (810, 344), (150, 380)]
    sk.wash(cyl, op=0.15)
    sk.poly(cyl, close=True, sw=2.8, amp=2.4)
    sk.ellipse(150, 315, 30, 66, steps=16, sw=2.4, amp=1.8)
    sk.ellipse(810, 279, 28, 65, steps=16, sw=2.4, amp=1.8)
    sk.hatch(150, 300, 660, 80, angle=-52, gap=15, op=0.24)
    for hx, hy in ((360, 300), (596, 286)):                     # two hands gripping
        sk.poly([(hx - 76, hy + 74), (hx - 62, hy - 12), (hx + 8, hy - 40),
                 (hx + 72, hy - 12), (hx + 78, hy + 70)], sw=2.4, amp=2.2)
        for i in range(4):
            fx = hx - 50 + i * 34
            sk.poly([(fx, hy - 26), (fx + 6, hy + 20), (fx - 4, hy + 52)], sw=1.9, amp=1.6)
    return sk


PANELS = {"09": shot_09, "10": shot_10, "11": shot_11, "12": shot_12, "13": shot_13}


def main():
    os.makedirs(OUT, exist_ok=True)
    for key, fn in PANELS.items():
        path = os.path.join(OUT, f"shot_{key}.svg")
        with open(path, "w") as fh:
            fh.write(fn().svg())
        print("wrote", os.path.relpath(path, HERE))


if __name__ == "__main__":
    main()
