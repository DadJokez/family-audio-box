#!/usr/bin/env python3
"""Generate the preliminary FamilyBox radio enclosure drawing set.

The dimensions and component envelopes are sourced from
docs/radio-enclosure-v1.md.  The sheets are intentionally marked PRELIMINARY:
prototype holes and clone-board mounting details must be checked against the
delivered hardware before release for production.
"""

from __future__ import annotations

import math
from pathlib import Path

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import TABLOID, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "pdf" / "familybox-radio-enclosure-v1-drawings.pdf"

PAGE_W, PAGE_H = landscape(TABLOID)
INK = HexColor("#15222A")
DIM = HexColor("#315C70")
ACCENT = HexColor("#9A4C2C")
SAGE = HexColor("#8C9270")
CREAM = HexColor("#F0E3C6")
LIGHT = HexColor("#E9EEF0")
MID = HexColor("#9AA8AF")
RED = HexColor("#B94132")
GREEN = HexColor("#4B7A58")
BLUE = HexColor("#3D6C91")
YELLOW = HexColor("#D8A62E")


def rr(c, x, y, w, h, r, fill=None, stroke=INK, lw=1):
    c.saveState()
    c.setLineWidth(lw)
    c.setStrokeColor(stroke)
    if fill is not None:
        c.setFillColor(fill)
    c.roundRect(x, y, w, h, r, stroke=1, fill=1 if fill is not None else 0)
    c.restoreState()


def line(c, x1, y1, x2, y2, color=INK, lw=1, dash=None):
    c.saveState()
    c.setStrokeColor(color)
    c.setLineWidth(lw)
    if dash:
        c.setDash(dash)
    c.line(x1, y1, x2, y2)
    c.restoreState()


def txt(c, x, y, s, size=8, color=INK, font="Helvetica", align="left"):
    c.saveState()
    c.setFillColor(color)
    c.setFont(font, size)
    if align == "center":
        c.drawCentredString(x, y, s)
    elif align == "right":
        c.drawRightString(x, y, s)
    else:
        c.drawString(x, y, s)
    c.restoreState()


def wrap(c, x, y, text, width, size=8, leading=10, color=INK, bullet=False):
    words = text.split()
    rows, row = [], ""
    for word in words:
        test = f"{row} {word}".strip()
        if row and stringWidth(test, "Helvetica", size) > width:
            rows.append(row)
            row = word
        else:
            row = test
    if row:
        rows.append(row)
    for i, row in enumerate(rows):
        prefix = "- " if bullet and i == 0 else "  " if bullet else ""
        txt(c, x, y - i * leading, prefix + row, size, color)
    return y - len(rows) * leading


def arrow(c, x, y, angle, color=DIM, size=5):
    a1 = angle + math.radians(150)
    a2 = angle - math.radians(150)
    path = c.beginPath()
    path.moveTo(x, y)
    path.lineTo(x + size * math.cos(a1), y + size * math.sin(a1))
    path.lineTo(x + size * math.cos(a2), y + size * math.sin(a2))
    path.close()
    c.saveState()
    c.setFillColor(color)
    c.drawPath(path, fill=1, stroke=0)
    c.restoreState()


def dim_h(c, x1, x2, y_obj, y_dim, label, color=DIM):
    line(c, x1, y_obj, x1, y_dim, color, 0.6)
    line(c, x2, y_obj, x2, y_dim, color, 0.6)
    line(c, x1, y_dim, x2, y_dim, color, 0.8)
    arrow(c, x1, y_dim, 0, color)
    arrow(c, x2, y_dim, math.pi, color)
    txt(c, (x1 + x2) / 2, y_dim + 3, label, 7, color, align="center")


def dim_v(c, y1, y2, x_obj, x_dim, label, color=DIM):
    line(c, x_obj, y1, x_dim, y1, color, 0.6)
    line(c, x_obj, y2, x_dim, y2, color, 0.6)
    line(c, x_dim, y1, x_dim, y2, color, 0.8)
    arrow(c, x_dim, y1, math.pi / 2, color)
    arrow(c, x_dim, y2, -math.pi / 2, color)
    c.saveState()
    c.translate(x_dim - 8, (y1 + y2) / 2)
    c.rotate(90)
    txt(c, 0, 0, label, 7, color, align="center")
    c.restoreState()


def leader(c, x1, y1, x2, y2, label, align="left"):
    line(c, x1, y1, x2, y2, DIM, 0.8)
    arrow(c, x1, y1, math.atan2(y1 - y2, x1 - x2), DIM, 4)
    offset = 3 if align == "left" else -3
    txt(c, x2 + offset, y2 + 2, label, 7, DIM, align=align)


class View:
    def __init__(self, c, x, y, scale):
        self.c, self.x, self.y, self.s = c, x, y, scale

    def p(self, x, y):
        return self.x + x * self.s, self.y + y * self.s

    def rect(self, x, y, w, h, r=0, fill=None, stroke=INK, lw=1, dash=None):
        X, Y = self.p(x, y)
        self.c.saveState()
        self.c.setStrokeColor(stroke)
        self.c.setLineWidth(lw)
        if dash:
            self.c.setDash(dash)
        if fill is not None:
            self.c.setFillColor(fill)
        if r:
            self.c.roundRect(
                X,
                Y,
                w * self.s,
                h * self.s,
                r * self.s,
                stroke=1,
                fill=1 if fill is not None else 0,
            )
        else:
            self.c.rect(X, Y, w * self.s, h * self.s, stroke=1, fill=1 if fill is not None else 0)
        self.c.restoreState()

    def circle(self, x, y, d, fill=None, stroke=INK, lw=1, dash=None):
        X, Y = self.p(x, y)
        self.c.saveState()
        self.c.setStrokeColor(stroke)
        self.c.setLineWidth(lw)
        if dash:
            self.c.setDash(dash)
        if fill is not None:
            self.c.setFillColor(fill)
        self.c.circle(X, Y, d * self.s / 2, stroke=1, fill=1 if fill is not None else 0)
        self.c.restoreState()

    def line(self, x1, y1, x2, y2, color=INK, lw=1, dash=None):
        X1, Y1 = self.p(x1, y1)
        X2, Y2 = self.p(x2, y2)
        line(self.c, X1, Y1, X2, Y2, color, lw, dash)

    def label(self, x, y, label, size=7, color=INK, align="left"):
        X, Y = self.p(x, y)
        rows = label.split("\n")
        for i, row in enumerate(rows):
            txt(self.c, X, Y - i * (size + 2), row, size, color, align=align)


def center_mark(v, x, y, r=4):
    v.line(x - r, y, x + r, y, DIM, 0.5)
    v.line(x, y - r, x, y + r, DIM, 0.5)


def sheet_frame(c, sheet, title, subtitle="FAMILYBOX RADIO ENCLOSURE V1"):
    c.setTitle("FamilyBox radio enclosure V1 technical drawings")
    c.setAuthor("OpenAI Codex for FamilyBox")
    c.setSubject("Preliminary enclosure design drawings")
    c.setStrokeColor(INK)
    c.setLineWidth(1.2)
    c.rect(18, 18, PAGE_W - 36, PAGE_H - 36, stroke=1, fill=0)
    c.setFillColor(HexColor("#F5F1E8"))
    c.rect(18, 18, PAGE_W - 36, 45, fill=1, stroke=1)
    line(c, 18, 63, PAGE_W - 18, 63, INK, 1)
    line(c, PAGE_W - 455, 18, PAGE_W - 455, 63, INK, 0.8)
    line(c, PAGE_W - 215, 18, PAGE_W - 215, 63, INK, 0.8)
    line(c, PAGE_W - 95, 18, PAGE_W - 95, 63, INK, 0.8)
    txt(c, 28, 44, title.upper(), 13, INK, "Helvetica-Bold")
    txt(c, 28, 28, subtitle, 8, INK)
    txt(c, PAGE_W - 445, 47, "STATUS", 6, DIM)
    txt(c, PAGE_W - 445, 29, "PRELIMINARY - VERIFY HARDWARE", 9, ACCENT, "Helvetica-Bold")
    txt(c, PAGE_W - 205, 47, "UNITS / SCALE", 6, DIM)
    txt(c, PAGE_W - 205, 29, "mm / NTS", 9, INK, "Helvetica-Bold")
    txt(c, PAGE_W - 85, 47, "SHEET", 6, DIM)
    txt(c, PAGE_W - 85, 29, f"{sheet} / 6", 10, INK, "Helvetica-Bold")
    txt(c, PAGE_W - 22, PAGE_H - 14, "REV A | 2026-08-29", 6, DIM, align="right")


def note_box(c, x, y, w, h, title, notes, warning=False):
    rr(c, x, y, w, h, 5, HexColor("#FAFBFB"), ACCENT if warning else DIM, 0.8)
    c.setFillColor(ACCENT if warning else DIM)
    c.rect(x, y + h - 22, w, 22, fill=1, stroke=0)
    txt(c, x + 8, y + h - 15, title, 8, white, "Helvetica-Bold")
    yy = y + h - 34
    for n in notes:
        yy = wrap(c, x + 9, yy, n, w - 18, 7.3, 9, INK, bullet=True) - 2


def draw_front(v, details=True):
    v.rect(0, 0, 210, 150, 18, SAGE, INK, 1.4)
    v.rect(4, 4, 202, 142, 14, CREAM, INK, 1.0)
    v.circle(58, 78, 96, None, DIM, 0.7, [4, 3])
    v.circle(58, 78, 79, HexColor("#22282B"), INK, 1.2)
    v.circle(58, 78, 51, HexColor("#384046"), black, 0.8)
    v.circle(58, 78, 18, black, black, 0.8)
    if details:
        for a in (45, 135, 225, 315):
            x = 58 + 43 * math.cos(math.radians(a))
            y = 78 + 43 * math.sin(math.radians(a))
            v.circle(x, y, 4.8, white, INK, 0.8)
        for x, col in zip((132, 159, 186), (BLUE, GREEN, RED), strict=True):
            v.circle(x, 44, 20, col, INK, 1)
            center_mark(v, x, 44, 2.5)
        v.circle(159, 100, 38, HexColor("#6C756F"), INK, 1)
        center_mark(v, 159, 100, 3)
        for x, z in ((14, 14), (105, 14), (196, 14), (14, 136), (105, 136), (196, 136)):
            v.circle(x, z, 4.5, white, MID, 0.7)
    center_mark(v, 58, 78, 4)


def sheet1(c):
    sheet_frame(c, 1, "General arrangement and principal dimensions")
    txt(c, 44, PAGE_H - 54, "ORTHOGRAPHIC VIEWS", 12, INK, "Helvetica-Bold")
    txt(c, 44, PAGE_H - 68, "Coordinate system: X left-right, Y front-rear, Z bottom-up", 7, DIM)

    vf = View(c, 55, 348, 2.05)
    draw_front(vf)
    vf.label(105, -10, "FRONT", 8, INK, "center")
    x0, y0 = vf.p(0, 0)
    x1, y1 = vf.p(210, 150)
    dim_h(c, x0, x1, y0, y0 - 27, "210 OVERALL")
    dim_v(c, y0, y1, x0, x0 - 27, "150 OVERALL")
    leader(c, *vf.p(58, 78), vf.p(95, 130)[0], vf.p(95, 130)[1], "3 in speaker / DIA 79 prototype")
    leader(c, *vf.p(159, 100), vf.p(189, 126)[0], vf.p(189, 126)[1], "DIA 38 volume knob")

    vt = View(c, 55, 91, 2.05)
    vt.rect(0, 0, 210, 115, 18, SAGE, INK, 1.2)
    vt.rect(4, 3, 108, 109, 10, None, DIM, 0.7, [4, 3])
    vt.line(112, 3, 112, 112, ACCENT, 1.1)
    vt.line(115, 3, 115, 112, ACCENT, 1.1)
    vt.circle(171, 67, 62, CREAM, INK, 1)
    center_mark(vt, 171, 67, 4)
    vt.label(105, -10, "TOP", 8, INK, "center")
    vt.label(55, 55, "SEALED CHAMBER", 7, DIM, "center")
    vt.label(162, 16, "ELECTRONICS BAY", 7, DIM, "center")
    x0, y0 = vt.p(0, 0)
    x1, y1 = vt.p(210, 115)
    dim_h(c, x0, x1, y0, y0 - 24, "210")
    dim_v(c, y0, y1, x1, x1 + 25, "115")
    leader(c, *vt.p(171, 67), vt.p(187, 101)[0], vt.p(187, 101)[1], "NFC PAD DIA 62")

    vs = View(c, 790, 348, 2.05)
    vs.rect(0, 0, 115, 150, 18, SAGE, INK, 1.2)
    vs.rect(8, 8, 99, 134, 10, None, DIM, 0.7, [4, 3])
    vs.label(57.5, -10, "RIGHT SIDE", 8, INK, "center")
    x0, y0 = vs.p(0, 0)
    x1, y1 = vs.p(115, 150)
    dim_h(c, x0, x1, y0, y0 - 27, "115 OVERALL")
    dim_v(c, y0, y1, x1, x1 + 25, "150")
    vs.label(57.5, 74, "REMOVABLE SERVICE PANEL\nZONE", 7, DIM, "center")

    note_box(
        c,
        555,
        92,
        620,
        230,
        "DESIGN BASIS",
        [
            "Outside envelope 210 W x 150 H x 115 D; 18 mm front-view corner radii; nominal wall 3.0 mm.",
            "Cream front baffle is a separately printed 202 x 142 x 4 panel, recessed 1.0 mm and attached with six M3 fasteners.",
            "Left chamber is permanently sealed except for a gasketed front baffle and sealed speaker-wire pass-through.",
            "Right bay is rear-serviceable and ventilated. Internal power bank is optional; the same shell supports an external-bank panel.",
            "NFC target is a solid top-right pad; no opening through the top wall.",
        ],
    )


def sheet2(c):
    sheet_frame(c, 2, "Front baffle manufacturing detail")
    txt(c, 42, PAGE_H - 54, "FRONT BAFFLE - VISIBLE FACE", 12, INK, "Helvetica-Bold")
    v = View(c, 72, 170, 2.8)
    draw_front(v)
    x0, y0 = v.p(0, 0)
    x1, y1 = v.p(210, 150)
    dim_h(c, x0, x1, y0, y0 - 31, "210 BODY / 202 BAFFLE")
    dim_v(c, y0, y1, x0, x0 - 34, "150 BODY / 142 BAFFLE")
    for x, label in ((58, "58"), (132, "132"), (159, "159"), (186, "186")):
        X, _ = v.p(x, 0)
        line(c, X, y0, X, y0 - 16, DIM, 0.5)
        txt(c, X, y0 - 25, label, 6.5, DIM, align="center")
    for z, label in ((44, "44"), (78, "78"), (100, "100")):
        _, Y = v.p(0, z)
        line(c, x0, Y, x0 - 16, Y, DIM, 0.5)
        txt(c, x0 - 20, Y - 2, label, 6.5, DIM, align="right")
    dim_h(c, v.p(132, 44)[0], v.p(159, 44)[0], v.p(132, 44)[1], v.p(132, 44)[1] + 42, "27 TYP")
    leader(c, *v.p(58, 78), 720, 610, "SPEAKER CUTOUT DIA 79.0 PROTOTYPE")
    leader(c, *v.p(88.4, 108.4), 720, 584, "4x RADIAL SLOT 4.8 x 6.0 ON DIA 86 BCD")
    leader(c, *v.p(132, 44), 720, 530, "3x DIA 16.2 PROTOTYPE; DIA 20 CAP KEEP-OUT")
    leader(c, *v.p(159, 100), 720, 500, "DIA 7.0 PROTOTYPE SHAFT HOLE; DIA 38 KNOB")
    leader(c, *v.p(14, 136), 720, 462, "6x M3 BAFFLE FASTENERS AT SHOWN COORDINATES")

    note_box(
        c,
        720,
        164,
        455,
        268,
        "FABRICATION NOTES",
        [
            "All X/Z coordinates reference the outer-body lower-left corner shown; baffle insert begins at X=4, Z=4.",
            "Locally reinforce the rear of the baffle to 6 mm around the speaker and controls using ribs.",
            "Recess speaker flange 1.5-2.0 mm and add a 1.0 mm closed-cell foam gasket.",
            "Reserve a 96 x 96 collision envelope for the driver even though the initial cutout is 79.0 mm.",
            "Button holes and encoder hole are prototype dimensions. Print the fit coupons on Sheet 6 before cutting final CAD.",
            "Buttons are identical round parts: blue previous, green play/pause, red next. Icons are intentionally omitted in V1 CAD.",
        ],
        warning=True,
    )


def sheet3(c):
    sheet_frame(c, 3, "Internal zoning and sections")
    txt(
        c,
        42,
        PAGE_H - 54,
        "SECTION A-A - HORIZONTAL PLAN THROUGH COMPONENTS",
        12,
        INK,
        "Helvetica-Bold",
    )
    v = View(c, 60, 430, 2.35)
    v.rect(0, 0, 210, 115, 18, None, INK, 1.4)
    v.rect(3, 4, 109, 108, 9, HexColor("#EEF1E6"), DIM, 0.8)
    v.rect(115, 4, 92, 108, 8, HexColor("#F3F5F6"), DIM, 0.8)
    v.rect(112, 3, 3, 109, 0, ACCENT, ACCENT, 1)
    v.rect(35, 3, 46, 45, 3, None, INK, 0.9, [4, 3])
    v.label(58, 8, "SPEAKER MAGNET\nKEEP-OUT", 5.5, DIM, "center")
    v.rect(120, 95, 65, 17, 3, HexColor("#DCCCA7"), INK, 0.8)
    v.rect(181, 18, 26, 70, 2, HexColor("#B9D2DC"), INK, 0.8)
    v.rect(149, 44, 48, 46, 2, HexColor("#D9C8E2"), INK, 0.8)
    v.rect(143, 4, 32, 35, 2, HexColor("#D7DFCA"), INK, 0.8)
    v.rect(116, 12, 26, 28, 2, HexColor("#E6C3B7"), INK, 0.8)
    v.label(56, 60, "SEALED\n1.50 L NET", 8, DIM, "center")
    v.label(152, 104, "POWER BANK 65 x 17", 6, INK, "center")
    v.label(194, 50, "PI 26 x 70", 6, INK, "center")
    v.label(173, 66, "PN532 48 x 46", 6, INK, "center")
    v.label(159, 20, "ENCODER", 6, INK, "center")
    v.label(129, 25, "AMP", 6, INK, "center")
    x0, y0 = v.p(0, 0)
    x1, y1 = v.p(210, 115)
    dim_h(c, x0, x1, y0, y0 - 27, "210")
    dim_v(c, y0, y1, x0, x0 - 25, "115")
    dim_h(c, v.p(0, 0)[0], v.p(112, 0)[0], y1, y1 + 22, "112 TO PARTITION")

    txt(
        c,
        42,
        390,
        "SECTION B-B - VERTICAL FRONT/REAR CUT AT ELECTRONICS BAY",
        12,
        INK,
        "Helvetica-Bold",
    )
    s = View(c, 60, 92, 1.90)
    s.rect(0, 0, 115, 150, 14, None, INK, 1.4)
    s.rect(3, 3, 109, 144, 10, HexColor("#F5F6F6"), DIM, 0.7)
    s.rect(0, 0, 4, 150, 0, CREAM, INK, 1)
    s.rect(95, 8, 17, 95, 2, HexColor("#DCCCA7"), INK, 0.8)
    s.rect(18, 70, 70, 60, 2, HexColor("#B9D2DC"), INK, 0.8)
    s.rect(44, 137, 46, 10, 2, HexColor("#D9C8E2"), INK, 0.8)
    s.rect(4, 83, 35, 32, 2, HexColor("#D7DFCA"), INK, 0.8)
    s.rect(112, 8, 3.2, 134, 0, SAGE, INK, 1)
    s.label(103.5, 50, "BANK", 6, INK, "center")
    s.label(53, 98, "PI / HEADER", 6, INK, "center")
    s.label(67, 141, "PN532", 6, INK, "center")
    s.label(21, 98, "ENCODER", 6, INK, "center")
    s.label(58, 13, "10 MIN CABLE CORRIDOR", 6, DIM, "center")
    x0, y0 = s.p(0, 0)
    x1, y1 = s.p(115, 150)
    dim_h(c, x0, x1, y0, y0 - 24, "115")
    dim_v(c, y0, y1, x0, x0 - 25, "150")

    note_box(
        c,
        335,
        92,
        840,
        282,
        "COLLISION ENVELOPES - NOT CARRIER GEOMETRY",
        [
            "Power-bank cradle: X=120..185, Y=95..112, Z=8..103. Internal clear size 65 W x 17 D x 95 H.",
            "Pi side carrier: X=181..207, Y=18..88, Z=70..130. Preserve 26 mm inward thickness and microSD access.",
            "PN532 carrier: X=149..197, Y=44..90, Z=137..148. Keep antenna parallel to the 2.0 mm top window.",
            "Encoder: X=143..175, Y=4..39, Z=83..115. Amplifier: X=116..142, Y=12..40, Z=94..118.",
            "Maintain a 10 mm cable corridor along the bay bottom and partition. Route NFC harness down the right wall.",
            "Speaker-wire pass-through is one 6-8 mm sealed hole high on the partition. Do not vent the left chamber.",
        ],
    )


def vent_slots(v, x, y, cols=2):
    for col in range(cols):
        for row in range(4):
            v.rect(x + col * 35, y + row * 12, 25, 3, 1.5, None, DIM, 0.7)


def sheet4(c):
    sheet_frame(c, 4, "Rear service panel and power variants")
    txt(c, 42, PAGE_H - 54, "REAR ELEVATION - COMMON APERTURE", 12, INK, "Helvetica-Bold")
    v = View(c, 60, 390, 2.45)
    v.rect(0, 0, 210, 150, 18, SAGE, INK, 1.3)
    v.rect(119, 8, 83, 134, 8, white, ACCENT, 1.1, [5, 3])
    v.rect(115, 4, 91, 142, 10, CREAM, INK, 1)
    vent_slots(v, 123, 18)
    vent_slots(v, 123, 92)
    for x, z in ((121, 10), (200, 10), (121, 140), (200, 140)):
        v.circle(x, z, 4.5, white, INK, 0.8)
    v.label(160, 74, "REMOVABLE\nELECTRONICS PANEL", 8, INK, "center")
    v.label(58, 75, "SOLID REAR WALL\nSEALED CHAMBER", 8, DIM, "center")
    dim_h(c, v.p(119, 8)[0], v.p(202, 8)[0], v.p(119, 8)[1], v.p(119, 8)[1] - 22, "83 APERTURE")
    dim_v(c, v.p(119, 8)[1], v.p(119, 142)[1], v.p(119, 8)[0], v.p(119, 8)[0] - 22, "134 APERTURE")

    txt(c, 690, PAGE_H - 54, "PANEL VARIANT A - INTERNAL BANK", 12, INK, "Helvetica-Bold")
    a = View(c, 720, 408, 2.25)
    a.rect(0, 0, 91, 142, 10, CREAM, INK, 1.1)
    vent_slots(a, 8, 8, 2)
    a.rect(13, 35, 65, 95, 4, HexColor("#DCCCA7"), ACCENT, 1)
    a.label(45.5, 82, "REMOVABLE CRADLE\n65 x 95 x 17 CLEAR", 7, INK, "center")
    a.rect(66, 6, 25, 25, 2, None, ACCENT, 0.8, [3, 2])
    a.label(78, 18, "PWR\nRSV", 5, ACCENT, "center")
    leader(c, *a.p(78, 130), 1000, 700, "PORTS UP; 25 MIN CABLE BEND")

    txt(c, 690, 356, "PANEL VARIANT B - EXTERNAL BANK", 12, INK, "Helvetica-Bold")
    b = View(c, 720, 90, 2.25)
    b.rect(0, 0, 91, 142, 10, CREAM, INK, 1.1)
    vent_slots(b, 8, 18, 2)
    vent_slots(b, 8, 92, 2)
    b.rect(34, 0, 23, 8, 3, white, ACCENT, 1)
    b.label(45.5, 68, "VENTED FLAT PANEL", 7, INK, "center")
    leader(c, *b.p(45.5, 5), 1000, 110, "BOTTOM CABLE NOTCH + STRAIN RELIEF")

    note_box(
        c,
        1000,
        384,
        175,
        272,
        "REAR-PANEL RULES",
        [
            "Cover panel approximately 91 x 142 x 3.2 with radius 10.",
            "Use four M3 heat-set inserts or captured nuts.",
            "Vent electronics only: 8 slots, each 25 x 3, four high and four low.",
            "Reserve an uncut 25 x 25 power-control area until shutdown hardware is selected.",
            "Internal bank cradle attaches to the removable panel, never traps the cell, and uses a soft strap.",
            "Actual charging-port offset remains measure-to-fit.",
        ],
        warning=True,
    )


def sheet5(c):
    sheet_frame(c, 5, "NFC stage and reader carrier detail")
    txt(c, 42, PAGE_H - 54, "TOP STAGE PLAN", 12, INK, "Helvetica-Bold")
    v = View(c, 60, 400, 3.2)
    v.rect(115, 0, 95, 115, 10, SAGE, INK, 1.3)
    v.circle(171, 67, 62, CREAM, INK, 1.1)
    v.rect(149, 44, 48, 46, 3, None, ACCENT, 1, [4, 2])
    center_mark(v, 171, 67, 5)
    v.label(171, 65, "TAP / SIT\nFIGURE HERE", 7, INK, "center")
    v.label(173, 47, "PN532 48 x 46 RESERVE", 6, ACCENT, "center")
    x0, y0 = v.p(115, 0)
    dim_h(c, v.p(115, 0)[0], v.p(171, 0)[0], y0, y0 - 25, "56")
    dim_h(c, v.p(171, 0)[0], v.p(210, 0)[0], y0, y0 - 25, "39")
    dim_v(c, v.p(115, 0)[1], v.p(115, 67)[1], x0, x0 - 25, "67")
    leader(c, *v.p(202, 67), 690, 666, "DIA 62 PAD / 0.8 RAISED OR RECESSED RING")

    txt(c, 42, 352, "SECTION C-C THROUGH NFC WINDOW", 12, INK, "Helvetica-Bold")
    s = View(c, 70, 122, 4.6)
    s.rect(0, 50, 95, 3, 0, SAGE, INK, 1)
    s.rect(25, 50, 62, 2, 0, CREAM, INK, 1)
    s.rect(32, 39, 48, 10, 2, HexColor("#D9C8E2"), ACCENT, 1)
    s.rect(35, 34, 42, 5, 1, LIGHT, DIM, 0.8)
    s.line(0, 20, 95, 20, DIM, 0.7, [4, 3])
    s.label(56, 43, "PN532 ANTENNA PARALLEL TO ROOF", 6, INK, "center")
    s.label(56, 35, "SLOTTED REMOVABLE CARRIER", 6, DIM, "center")
    leader(c, *s.p(52, 52), 650, 346, "LOCAL TOP WALL 2.0")
    leader(c, *s.p(80, 44), 650, 302, "10 mm BOARD + HEADER ENVELOPE")
    leader(c, *s.p(77, 36), 650, 258, "NYLON M2.5 FASTENERS PREFERRED")

    note_box(
        c,
        700,
        114,
        475,
        430,
        "NFC / RF CONSTRAINTS",
        [
            "Pad center: X=171, Y=67. Stage is solid; never cut an open hole through the top.",
            "Thin only the antenna window to 2.0 mm. Keep surrounding shell at the nominal 3.0 mm wall.",
            "Reserve X=149..197, Y=44..90, Z=137..148 for board, carrier, connector, and wiring.",
            "No steel screws, battery, Pi, coiled speaker wire, or amplifier directly beneath the antenna.",
            "Route SPI harness down the right wall and maintain 40 mm separation from amplifier/speaker wiring wherever practical.",
            "Carrier mounting holes are intentionally slotted because PN532 clone-board patterns vary.",
            "Acceptance test: ten consecutive reads/removals with the real tag and figure, final 2.0 mm roof coupon, production carrier, and speaker playing.",
            "If read range is marginal, adjust carrier standoff first; do not make the cosmetic pad thinner than 2.0 mm without a strength test.",
        ],
        warning=True,
    )


def exploded_box(c, x, y, w, h, label, num, fill):
    rr(c, x, y, w, h, 8, fill, INK, 1)
    c.setFillColor(ACCENT)
    c.circle(x + 18, y + h - 18, 11, fill=1, stroke=0)
    txt(c, x + 18, y + h - 21, str(num), 8, white, "Helvetica-Bold", align="center")
    txt(c, x + w / 2, y + h / 2 - 3, label, 8, INK, "Helvetica-Bold", align="center")


def sheet6(c):
    sheet_frame(c, 6, "Exploded assembly, printed parts, and fit coupons")
    txt(
        c,
        42,
        PAGE_H - 54,
        "EXPLODED ASSEMBLY - SCHEMATIC / NOT TO SCALE",
        12,
        INK,
        "Helvetica-Bold",
    )
    exploded_box(c, 55, 425, 160, 205, "CREAM FRONT\nBAFFLE", 2, CREAM)
    exploded_box(c, 275, 405, 260, 245, "SAGE MAIN SHELL\n+ SEALED PARTITION", 1, SAGE)
    exploded_box(c, 595, 430, 165, 195, "REAR PANEL\nA OR B", 3, CREAM)
    exploded_box(c, 820, 550, 145, 75, "PN532\nCARRIER", 7, HexColor("#D9C8E2"))
    exploded_box(c, 820, 440, 145, 75, "PI CARRIER", 6, HexColor("#B9D2DC"))
    exploded_box(c, 820, 330, 145, 75, "AMP CARRIER", 8, HexColor("#E6C3B7"))
    exploded_box(c, 1020, 500, 145, 75, "BANK CRADLE\nOPTIONAL", 5, HexColor("#DCCCA7"))
    exploded_box(c, 1020, 390, 145, 75, "ENCODER\nADAPTER", 9, HexColor("#D7DFCA"))
    for x1, y1, x2, y2 in (
        (215, 525, 275, 525),
        (535, 525, 595, 525),
        (760, 525, 820, 588),
        (760, 500, 820, 478),
        (760, 470, 820, 368),
        (965, 550, 1020, 538),
        (965, 470, 1020, 428),
    ):
        line(c, x1, y1, x2, y2, DIM, 1, [5, 3])
        arrow(c, x2, y2, math.atan2(y2 - y1, x2 - x1), DIM)

    txt(c, 42, 292, "FIT COUPONS - PRINT BEFORE FINAL PARTS", 12, INK, "Helvetica-Bold")
    # Button coupon
    rr(c, 55, 105, 235, 150, 8, white, INK, 1)
    txt(c, 68, 235, "A. BUTTON HOLES", 8, INK, "Helvetica-Bold")
    for i, d in enumerate((16.0, 16.2, 16.4)):
        x = 105 + i * 65
        c.circle(x, 175, d * 2.0, stroke=1, fill=0)
        txt(c, x, 136, f"DIA {d:.1f}", 7, DIM, align="center")
    txt(c, 68, 116, "Use final filament, orientation, and slicer.", 7, INK)
    # Speaker coupon
    rr(c, 315, 105, 250, 150, 8, white, INK, 1)
    txt(c, 328, 235, "B. SPEAKER / SLOT ARC", 8, INK, "Helvetica-Bold")
    c.arc(350, 130, 500, 250, 215, 110)
    for a in (225, 270, 315):
        x = 425 + 43 * 1.7 * math.cos(math.radians(a))
        y = 190 + 43 * 1.7 * math.sin(math.radians(a))
        rr(c, x - 5, y - 3, 10, 6, 3, white, INK, 0.8)
    txt(c, 328, 116, "Verify frame, DIA 79 cutout, and 4.8 x 6 slots.", 7, INK)
    # NFC coupon
    rr(c, 590, 105, 300, 150, 8, white, INK, 1)
    txt(c, 603, 235, "C. NFC ROOF THICKNESS", 8, INK, "Helvetica-Bold")
    for i, t in enumerate((1.6, 2.0, 2.4, 3.0)):
        x = 620 + i * 63
        rr(c, x, 152, 50, 48, 5, CREAM, INK, 0.8)
        txt(c, x + 25, 170, f"{t:.1f}", 8, INK, "Helvetica-Bold", align="center")
    txt(c, 603, 116, "Test 10 reads at each thickness with speaker playing.", 7, INK)
    # Fasteners
    note_box(
        c,
        920,
        105,
        255,
        150,
        "RELEASE GATES",
        [
            "Measure speaker frame and magnet depth.",
            "Measure every clone board and connector.",
            "Verify encoder is GPIO-safe at 3.3 V.",
            "Confirm bank port offsets and cable bends.",
            "Pass seal, NFC, thermal, idle, and shutdown tests.",
        ],
        warning=True,
    )


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    for fn in (sheet1, sheet2, sheet3, sheet4, sheet5, sheet6):
        fn(c)
        c.showPage()
    c.save()
    print(OUT)


if __name__ == "__main__":
    main()
