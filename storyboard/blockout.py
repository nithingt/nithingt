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

def figure(sk, x, ground, height, pose="stand", hair="short", flip=False):
    """Blocked-in human. (x, ground) is the feet; height is head-to-toe px."""
    s = -1 if flip else 1
    hr_x, hr_y = height * 0.046, height * 0.058
    head_y = ground - height * 0.942
    sh_y = ground - height * 0.838
    hip_y = ground - height * 0.516
    sh_w, hip_w = height * 0.105, height * 0.072

    # head, neck, torso
    sk.ellipse(x, head_y, hr_x, hr_y, sw=1.9, amp=1.6)
    sk.line(x - hr_x * 0.45, head_y + hr_y * 0.85, x - sh_w * 0.28, sh_y, sw=1.7, amp=1.2)
    sk.line(x + hr_x * 0.45, head_y + hr_y * 0.85, x + sh_w * 0.28, sh_y, sw=1.7, amp=1.2)
    sk.poly([(x - sh_w, sh_y), (x + sh_w, sh_y),
             (x + hip_w, hip_y), (x - hip_w, hip_y)], close=True, sw=2.0, amp=2.0)

    if hair == "short":
        sk.fill([(x - hr_x * 1.15, head_y - hr_y * 0.15), (x - hr_x * 0.9, head_y - hr_y * 1.05),
                 (x + hr_x * 0.9, head_y - hr_y * 1.05), (x + hr_x * 1.15, head_y - hr_y * 0.2),
                 (x + hr_x * 0.6, head_y - hr_y * 0.55), (x - hr_x * 0.6, head_y - hr_y * 0.55)],
                op=0.9, jitter=2.0)
    elif hair == "tied":
        sk.fill([(x - hr_x * 1.1, head_y - hr_y * 0.2), (x, head_y - hr_y * 1.15),
                 (x + hr_x * 1.1, head_y - hr_y * 0.2), (x + hr_x * 1.5, head_y + hr_y * 0.5),
                 (x + hr_x * 0.8, head_y - hr_y * 0.1)], op=0.9, jitter=2.0)

    # arms
    el_y, hd_y = (sh_y + hip_y) / 2, hip_y + height * 0.055
    if pose == "arms_up":
        for side in (-1, 1):
            sk.poly([(x + side * sh_w, sh_y),
                     (x + side * sh_w * 1.5, sh_y - height * 0.13),
                     (x + side * sh_w * 1.35, sh_y - height * 0.30)], sw=2.2, amp=2.2)
    elif pose == "reach":
        sk.poly([(x - sh_w, sh_y), (x - sh_w * 1.6, el_y), (x - sh_w * 0.9, hd_y)], sw=2.0, amp=2.0)
        sk.poly([(x + sh_w, sh_y), (x + s * sh_w * 2.1, sh_y + height * 0.03),
                 (x + s * sh_w * 3.2, sh_y - height * 0.02)], sw=2.0, amp=2.0)
    else:
        for side in (-1, 1):
            sk.poly([(x + side * sh_w, sh_y),
                     (x + side * sh_w * 1.35, el_y),
                     (x + side * sh_w * 1.05, hd_y)], sw=2.0, amp=2.0)

    # legs
    for side in (-1, 1):
        sk.poly([(x + side * hip_w * 0.8, hip_y),
                 (x + side * hip_w * 1.05, (hip_y + ground) / 2),
                 (x + side * hip_w * 0.85, ground)], sw=2.1, amp=2.0)


def face_closeup(sk, cx, cy, r, mouth_open=0.5, turn=-0.12):
    """Head filling frame — the reaction-shot workhorse."""
    sk.ellipse(cx, cy, r * 0.80, r, sw=2.3, amp=2.2, steps=18)
    sk.line(cx - r * 0.62, cy + r * 0.30, cx - r * 0.16, cy + r * 0.92, sw=2.0, amp=2.0)
    sk.line(cx + r * 0.62, cy + r * 0.30, cx + r * 0.16, cy + r * 0.92, sw=2.0, amp=2.0)

    ex, ey = r * 0.34, cy - r * 0.06
    off = turn * r
    for side in (-1, 1):
        x = cx + side * ex + off
        sk.poly([(x - r * 0.19, ey), (x - r * 0.05, ey - r * 0.09),
                 (x + r * 0.13, ey - r * 0.03), (x + r * 0.19, ey)], sw=1.7, amp=1.1)
        sk.poly([(x - r * 0.19, ey), (x - r * 0.02, ey + r * 0.12), (x + r * 0.19, ey)],
                sw=1.7, amp=1.1)
        sk.ellipse(x + r * 0.01, ey + r * 0.02, r * 0.075, r * 0.085, steps=10, sw=1.5, amp=0.9)
        sk.fill([(x - r * 0.05, ey - r * 0.03), (x + r * 0.05, ey - r * 0.03),
                 (x + r * 0.05, ey + r * 0.07), (x - r * 0.05, ey + r * 0.07)], op=0.85, jitter=1.2)
        sk.line(x - r * 0.24, ey - r * 0.22, x + r * 0.22, ey - r * 0.28, sw=2.6, amp=1.6)

    sk.poly([(cx + off, cy - r * 0.02), (cx + off - r * 0.09, cy + r * 0.30),
             (cx + off + r * 0.03, cy + r * 0.35)], sw=1.7, amp=1.4)

    my = cy + r * 0.56
    sk.ellipse(cx + off, my, r * 0.16, r * 0.055 + r * 0.10 * mouth_open, steps=12, sw=1.9, amp=1.2)

    sk.fill([(cx - r * 0.92, cy - r * 0.30), (cx - r * 0.70, cy - r * 1.02),
             (cx + off, cy - r * 1.20), (cx + r * 0.74, cy - r * 0.96),
             (cx + r * 0.92, cy - r * 0.22), (cx + r * 0.58, cy - r * 0.52),
             (cx + off, cy - r * 0.66), (cx - r * 0.56, cy - r * 0.48)], op=0.92, jitter=3.0)


# --- panels ------------------------------------------------------------------

def shot_09():
    """OTS past Sable, deep to Roon in the doorway. Camera at bench height."""
    sk = Sketch(9)
    sk.wash([(0, 0), (W, 0), (W, 320), (0, 300)], op=0.10)
    for y in (58, 96, 134):                                     # roof beams
        sk.line(120, y, W, y - 16, sw=1.6, amp=3.0, op=0.55)
    sk.poly([(150, 30), (150, 300)], sw=1.5, amp=2.5, op=0.4)
    sk.poly([(0, 250), (W, 214)], sw=1.7, amp=3.0, op=0.5)      # far wall / floor line

    doorway = [(556, 96), (742, 92), (742, 352), (556, 356)]     # light source, deep
    sk.wash(doorway, op=0.06)
    sk.poly(doorway, close=True, sw=2.4, amp=2.2)
    figure(sk, 648, 344, 244, pose="stand", hair="tied")
    sk.hatch(556, 250, 186, 106, angle=-62, gap=13, op=0.28)

    sk.poly([(60, 470), (470, 372), (W, 430)], sw=2.6, amp=3.0)  # bench edge
    sk.line(470, 372, 470, 540, sw=2.0, amp=2.4, op=0.6)
    sk.hatch(470, 372, 490, 168, angle=-55, gap=14, op=0.22)

    # foreground head + shoulder, held as a dark mass
    sk.fill([(96, 540), (86, 400), (150, 316), (268, 306), (344, 372),
             (352, 470), (392, 540)], op=0.93, jitter=4.5)
    sk.poly([(30, 540), (74, 452), (150, 420)], sw=3.0, amp=3.5, op=0.7)
    return sk


def shot_10():
    """CU Roon. Reaction. Eyeline just off lens."""
    sk = Sketch(10)
    for y in (120, 176, 402, 452):
        sk.line(40, y, W - 40, y - 10, sw=1.5, amp=3.5, op=0.28)
    sk.line(806, 60, 846, 490, sw=1.6, amp=3.0, op=0.3)
    face_closeup(sk, 470, 268, 168, mouth_open=0.62, turn=-0.10)
    sk.poly([(300, 540), (338, 440), (470, 412), (610, 442), (648, 540)], sw=2.4, amp=3.0)
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

    figure(sk, 484, 540, 470, pose="arms_up", hair="short")
    for i, x in enumerate((196, 250, 706, 764)):                # strain lines
        sk.line(x, 250 + i * 8, x + (-58 if x < 480 else 58), 200 + i * 8, sw=2.0, amp=1.6, op=0.6)
    return sk


def shot_12():
    """Wide two-shot. Neither of them moves. Hold."""
    sk = Sketch(12)
    sk.wash([(0, 0), (W, 0), (W, 300), (0, 286)], op=0.09)
    sk.poly([(0, 300), (W, 286)], sw=2.0, amp=3.0)
    for x in (120, 300, 520, 760):
        sk.line(x, 300, x - 60 + (x - 480) * 0.22, 540, sw=1.4, amp=3.0, op=0.28)
    mass = [(700, 300), (700, 120), (920, 96), (940, 300)]      # machine bulk, frame right
    sk.wash(mass, op=0.18)
    sk.poly(mass, close=True, sw=2.6, amp=2.6)
    sk.hatch(700, 190, 240, 112, angle=-60, gap=13, op=0.3)
    figure(sk, 268, 470, 232, pose="stand", hair="short")
    figure(sk, 566, 452, 214, pose="stand", hair="tied", flip=True)
    sk.line(300, 470, 540, 452, sw=1.3, amp=2.0, op=0.25)       # eyeline
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
