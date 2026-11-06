"""Parse a .pptx (OOXML) into a resolution-independent draw list.

Coordinates are CSS-like pixels (EMU / 9525), so a 13.33in slide is 1280 px wide.
Nothing here paints; `render.py` consumes the Slide/Item objects.
"""
from __future__ import annotations

import colorsys
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage, QPainterPath, QTransform

EMU = 9525.0
PT = 96.0 / 72.0
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


class PptxError(Exception):
    """Raised for files that are not a readable .pptx."""


# --------------------------------------------------------------------------- XML helpers
def lname(e) -> str:
    t = e.tag
    return t.rsplit("}", 1)[-1] if isinstance(t, str) else ""


def kids(e, n):
    return [c for c in e if lname(c) == n] if e is not None else []


def kid(e, n):
    if e is None:
        return None
    for c in e:
        if lname(c) == n:
            return c
    return None


def path(e, *names):
    for n in names:
        e = kid(e, n)
        if e is None:
            return None
    return e


def attr(e, n, d=None):
    if e is None:
        return d
    v = e.get(n)
    if v is not None:
        return v
    for k, val in e.attrib.items():  # namespaced, e.g. r:embed
        if k.rsplit("}", 1)[-1] == n:
            return val
    return d


def num(e, n, d=0.0):
    v = attr(e, n)
    try:
        return float(v) if v is not None else d
    except ValueError:
        return d


def first(*vals):
    for v in vals:
        if v is not None:
            return v
    return None


def first_attr(els, n):
    for e in els:
        if e is not None:
            v = e.get(n)
            if v is not None:
                return v
    return None


def first_kid(els, n):
    for e in els:
        k = kid(e, n)
        if k is not None:
            return k
    return None


# --------------------------------------------------------------------------- package
class Package:
    def __init__(self, filename: str):
        try:
            self.zf = zipfile.ZipFile(filename)
        except (zipfile.BadZipFile, OSError) as e:
            raise PptxError("The file is not a valid .pptx (not a zip archive, or it is corrupt).") from e
        self.names = set(self.zf.namelist())
        if "ppt/presentation.xml" not in self.names:
            raise PptxError("Not a PowerPoint presentation: ppt/presentation.xml is missing.")
        self._xml: dict[str, Optional[ET.Element]] = {}
        self._rels: dict[str, dict] = {}
        self._img: dict[str, Optional[QImage]] = {}

    def xml(self, p: str):
        if p not in self._xml:
            try:
                self._xml[p] = ET.fromstring(self.zf.read(p)) if p in self.names else None
            except (ET.ParseError, KeyError, zipfile.BadZipFile):
                self._xml[p] = None
        return self._xml[p]

    def rels(self, part: str) -> dict:
        if part not in self._rels:
            d, name = posixpath.split(part)
            r = self.xml(posixpath.join(d, "_rels", name + ".rels"))
            out = {}
            for e in r if r is not None else []:
                tgt = e.get("Target", "")
                ext = e.get("TargetMode") == "External"
                if not ext:
                    tgt = tgt[1:] if tgt.startswith("/") else posixpath.normpath(posixpath.join(d, tgt))
                out[e.get("Id")] = (e.get("Type", ""), tgt, ext)
            self._rels[part] = out
        return self._rels[part]

    def rel_of_type(self, part: str, suffix: str):
        for typ, tgt, ext in self.rels(part).values():
            if typ.endswith("/" + suffix):
                return tgt
        return None

    def image(self, p: str) -> Optional[QImage]:
        if p not in self._img:
            img = None
            if p in self.names:
                im = QImage.fromData(self.zf.read(p))
                img = im if not im.isNull() else None
            self._img[p] = img
        return self._img[p]


# --------------------------------------------------------------------------- colors
PRESET = {"black": "000000", "white": "FFFFFF", "red": "FF0000", "green": "008000", "blue": "0000FF",
          "yellow": "FFFF00", "gray": "808080", "grey": "808080", "orange": "FFA500"}
COLOR_TAGS = {"srgbClr", "schemeClr", "sysClr", "prstClr", "scrgbClr", "hslClr"}


@dataclass
class Theme:
    colors: dict = field(default_factory=dict)
    major: str = ""
    minor: str = ""
    ln_w: list = field(default_factory=list)


def parse_theme(root) -> Theme:
    t = Theme()
    cs = path(root, "themeElements", "clrScheme")
    for c in cs if cs is not None else []:
        v = c[0] if len(c) else None
        if v is not None:
            t.colors[lname(c)] = (v.get("val") if lname(v) == "srgbClr" else v.get("lastClr")) or "000000"
    fs = path(root, "themeElements", "fontScheme")
    t.major = attr(path(fs, "majorFont", "latin"), "typeface", "") or ""
    t.minor = attr(path(fs, "minorFont", "latin"), "typeface", "") or ""
    for ln in kids(path(root, "themeElements", "fmtScheme", "lnStyleLst"), "ln"):
        t.ln_w.append(num(ln, "w", 9525))
    return t


def _hex(h: str):
    h = (h or "000000").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    except ValueError:
        return [0, 0, 0]


def color_of(parent, ctx) -> Optional[QColor]:
    if parent is None:
        return None
    c = next((k for k in parent if lname(k) in COLOR_TAGS), None)
    if c is None:
        return None
    n = lname(c)
    if n == "srgbClr":
        hx = c.get("val")
    elif n == "sysClr":
        hx = c.get("lastClr") or ("FFFFFF" if c.get("val") == "window" else "000000")
    elif n == "prstClr":
        hx = PRESET.get(c.get("val"), "000000")
    elif n == "schemeClr":
        v = c.get("val")
        hx = ctx.theme.colors.get(ctx.clrmap.get(v, v)) or ctx.theme.colors.get(v) or "000000"
    else:
        hx = "000000"
    rgb = _hex(hx)
    alpha = 1.0
    for m in c:
        v = num(m, "val") / 100000.0
        t = lname(m)
        if t in ("lumMod", "lumOff", "satMod"):
            h, l, s = colorsys.rgb_to_hls(*(x / 255 for x in rgb))
            if t == "lumMod":
                l = min(1, max(0, l * v))
            elif t == "lumOff":
                l = min(1, max(0, l + v))
            else:
                s = min(1, max(0, s * v))
            rgb = [round(x * 255) for x in colorsys.hls_to_rgb(h, l, s)]
        elif t == "tint":
            rgb = [round(x * v + 255 * (1 - v)) for x in rgb]
        elif t == "shade":
            rgb = [round(x * v) for x in rgb]
        elif t == "alpha":
            alpha = v
    q = QColor(*rgb)
    q.setAlphaF(alpha)
    return q


# --------------------------------------------------------------------------- draw-list model
@dataclass
class LineSpec:
    width: float
    color: QColor
    dash: str = "solid"  # solid | dash | dot
    head: bool = False
    tail: bool = False


@dataclass
class Run:
    text: str
    size: float
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    caps: bool = False
    baseline: int = 0
    spacing: float = 0.0
    color: Optional[QColor] = None
    font: str = ""
    br: bool = False


@dataclass
class Bullet:
    text: str
    color: Optional[QColor]
    size: float
    font: str = ""


@dataclass
class Para:
    runs: list
    align: str = "l"
    mar_l: float = 0.0
    indent: float = 0.0
    bef: float = 0.0
    aft: float = 0.0
    line_pct: Optional[float] = None
    line_px: Optional[float] = None
    bullet: Optional[Bullet] = None
    end_size: float = 18 * PT


@dataclass
class TextBody:
    paras: list
    l: float = 10.0
    t: float = 5.0
    r: float = 10.0
    b: float = 5.0
    anchor: str = "t"
    wrap: bool = True
    vertical: bool = False


@dataclass
class Cell:
    x: float
    y: float
    w: float
    h: float
    fill: Optional[QColor]
    borders: dict
    text: TextBody


@dataclass
class Item:
    kind: str  # shape | line | image | table | placeholder
    w: float
    h: float
    tf: QTransform
    text_tf: QTransform
    geom: str = "rect"  # rect | round | ellipse | poly | path | none
    radius: float = 0.0
    poly: str = ""
    path: Optional[QPainterPath] = None
    fill: Optional[tuple] = None  # ('solid', QColor) | ('grad', stops, angle, radial) | ('img', QImage)
    line: Optional[LineSpec] = None
    text: Optional[TextBody] = None
    image: Optional[QImage] = None
    crop: tuple = (0.0, 0.0, 0.0, 0.0)
    cells: list = field(default_factory=list)
    label: str = ""
    alt: str = ""


@dataclass
class Slide:
    items: list
    background: Optional[tuple]
    notes: str
    index: int


# --------------------------------------------------------------------------- context
@dataclass
class Ctx:
    pkg: Package
    theme: Theme
    clrmap: dict
    rels: dict
    layout: Optional[ET.Element]
    master: Optional[ET.Element]
    txstyles: Optional[ET.Element]
    pres_style: Optional[ET.Element]
    slide_no: int


def fill_spec(sppr, ctx):
    if sppr is None:
        return None
    for c in sppr:
        n = lname(c)
        if n == "noFill":
            return ("none",)
        if n == "solidFill":
            col = color_of(c, ctx)
            return ("solid", col) if col else ("none",)
        if n == "gradFill":
            stops = []
            gl = kid(c, "gsLst")
            for gs in kids(gl, "gs"):
                col = color_of(gs, ctx)
                if col:
                    stops.append((num(gs, "pos") / 100000.0, col))
            if not stops:
                return None
            lin = kid(c, "lin")
            return ("grad", stops, num(lin, "ang") / 60000.0, kid(c, "path") is not None)
        if n == "blipFill":
            blip = kid(c, "blip")
            rel = ctx.rels.get(attr(blip, "embed"))
            img = ctx.pkg.image(rel[1]) if rel else None
            return ("img", img) if img is not None else None
        if n == "pattFill":
            col = color_of(kid(c, "fgClr"), ctx) or color_of(kid(c, "bgClr"), ctx)
            return ("solid", col) if col else None
    return None


def line_spec(ln, ctx, style=None) -> Optional[LineSpec]:
    w = None
    color = None
    dash = "solid"
    none = False
    head = tail = False
    if ln is not None:
        if ln.get("w") is not None:
            w = num(ln, "w")
        for c in ln:
            n = lname(c)
            if n == "noFill":
                none = True
            elif n == "solidFill":
                color = color_of(c, ctx)
            elif n == "prstDash":
                v = c.get("val", "")
                dash = "dash" if "dash" in v.lower() else "dot" if "dot" in v.lower() else "solid"
            elif n == "headEnd":
                head = c.get("type", "none") != "none"
            elif n == "tailEnd":
                tail = c.get("type", "none") != "none"
    ref = kid(style, "lnRef")
    if not none and color is None and ref is not None and num(ref, "idx") > 0:
        color = color_of(ref, ctx)
        if w is None:
            i = int(num(ref, "idx")) - 1
            w = ctx.theme.ln_w[i] if 0 <= i < len(ctx.theme.ln_w) else 9525
    if none or color is None:
        return None
    return LineSpec(max(1.0, (9525 if w is None else w) / EMU), color, dash, head, tail)


# --------------------------------------------------------------------------- placeholders & xfrm
def ph_of(sp):
    return first(path(sp, "nvSpPr", "nvPr", "ph"), path(sp, "nvPicPr", "nvPr", "ph"),
                 path(sp, "nvGraphicFramePr", "nvPr", "ph"))


def ph_kind(ph) -> str:
    t = attr(ph, "type")
    if t in ("title", "ctrTitle"):
        return "title"
    if t in ("dt", "ftr", "sldNum"):
        return t
    return "body"


def find_ph(root, ph, is_master):
    if root is None or ph is None:
        return None
    tree = path(root, "cSld", "spTree")
    cands = [e for e in (tree if tree is not None else []) if ph_of(e) is not None]
    idx = attr(ph, "idx")
    if not is_master and idx is not None:
        for e in cands:
            if attr(ph_of(e), "idx") == idx:
                return e
    kind = ph_kind(ph)
    for e in cands:
        if ph_kind(ph_of(e)) == kind and (kind != "body" or attr(ph_of(e), "idx") == idx or is_master):
            return e
    for e in cands:
        if ph_kind(ph_of(e)) == kind:
            return e
    return None


def get_xfrm(node):
    if node is None:
        return None
    x = first(path(node, "spPr", "xfrm"), path(node, "grpSpPr", "xfrm"), kid(node, "xfrm"))
    if x is None:
        return None
    off, ext = kid(x, "off"), kid(x, "ext")
    if off is None or ext is None:
        return None
    co, ce = kid(x, "chOff"), kid(x, "chExt")
    return {
        "x": num(off, "x") / EMU, "y": num(off, "y") / EMU, "w": num(ext, "cx") / EMU, "h": num(ext, "cy") / EMU,
        "rot": num(x, "rot") / 60000.0, "fh": attr(x, "flipH") == "1", "fv": attr(x, "flipV") == "1",
        "co": (num(co, "x") / EMU, num(co, "y") / EMU) if co is not None else None,
        "ce": (num(ce, "cx") / EMU, num(ce, "cy") / EMU) if ce is not None else None,
    }


def make_tf(parent: QTransform, xf, flips=True) -> QTransform:
    t = QTransform(parent)
    t.translate(xf["x"], xf["y"])
    if xf["rot"] or (flips and (xf["fh"] or xf["fv"])):
        t.translate(xf["w"] / 2, xf["h"] / 2)
        if xf["rot"]:
            t.rotate(xf["rot"])
        if flips and (xf["fh"] or xf["fv"]):
            t.scale(-1 if xf["fh"] else 1, -1 if xf["fv"] else 1)
        t.translate(-xf["w"] / 2, -xf["h"] / 2)
    return t


# --------------------------------------------------------------------------- text
BU_TAGS = {"buNone", "buChar", "buAutoNum", "buBlip"}


def _roman(n):
    out = ""
    for v, s in [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"),
                 (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]:
        while n >= v:
            out += s
            n -= v
    return out


def _alpha(n):
    s = ""
    n -= 1
    while True:
        s = chr(97 + n % 26) + s
        n = n // 26 - 1
        if n < 0:
            return s


def auto_num(kind: str, n: int) -> str:
    if kind.startswith("alphaLc"):
        t = _alpha(n)
    elif kind.startswith("alphaUc"):
        t = _alpha(n).upper()
    elif kind.startswith("romanLc"):
        t = _roman(n)
    elif kind.startswith("romanUc"):
        t = _roman(n).upper()
    else:
        t = str(n)
    if "ParenBoth" in kind:
        return f"({t})"
    if "ParenR" in kind:
        return f"{t})"
    if "Plain" in kind:
        return t
    return t + "."


def run_color(props, ctx):
    for p in props:
        f = kid(p, "solidFill")
        if f is not None:
            c = color_of(f, ctx)
            if c is not None:
                return c
    return None


def font_of(props, ctx) -> str:
    for p in props:
        lat = kid(p, "latin")
        if lat is not None:
            f = lat.get("typeface")
            if not f:
                continue
            if f == "+mj-lt":
                f = ctx.theme.major
            elif f == "+mn-lt":
                f = ctx.theme.minor
            if f and not f.startswith("+"):
                return f
    return ""


def build_text(txbody, ctx, chain, color=None, force=False, scale=1.0, def_size=18.0, nowrap=False) -> list:
    paras = []
    counters: list = []
    for p in kids(txbody, "p"):
        ppr = kid(p, "pPr")
        lvl = int(num(ppr, "lvl"))
        lvls = [x for x in (kid(l, f"lvl{lvl + 1}pPr") for l in chain) if x is not None]
        pprs = ([ppr] if ppr is not None else []) + lvls
        defs = [x for x in (kid(l, "defRPr") for l in lvls) if x is not None]
        end_rpr = kid(p, "endParaRPr")

        def size_of(props):
            v = first_attr(props, "sz")
            return (float(v) / 100.0 if v else def_size) * PT * scale

        runs_el = [c for c in p if lname(c) in ("r", "br", "fld")]
        first_props = ([kid(runs_el[0], "rPr")] if runs_el and kid(runs_el[0], "rPr") is not None else []) + defs
        if not runs_el:
            first_props = ([end_rpr] if end_rpr is not None else []) + defs
        base = size_of(first_props)

        para = Para(runs=[])
        para.align = first_attr(pprs, "algn") or "l"
        marl, ind = first_attr(pprs, "marL"), first_attr(pprs, "indent")
        para.mar_l = float(marl) / EMU if marl else 0.0
        para.indent = float(ind) / EMU if ind else 0.0
        bu = None
        for e in pprs:
            bu = next((c for c in e if lname(c) in BU_TAGS), None)
            if bu is not None:
                break
        has_bullet = bu is not None and lname(bu) in ("buChar", "buAutoNum")
        ln = first_kid(pprs, "lnSpc")
        if ln is not None:
            pct, pts = kid(ln, "spcPct"), kid(ln, "spcPts")
            if pct is not None:
                para.line_pct = num(pct, "val") / 1000.0
            elif pts is not None:
                para.line_px = num(pts, "val") / 100.0 * PT

        def spc(e):
            if e is None:
                return 0.0
            pct, pts = kid(e, "spcPct"), kid(e, "spcPts")
            if pct is not None:
                return num(pct, "val") / 100000.0 * base * 1.2
            if pts is not None:
                return num(pts, "val") / 100.0 * PT
            return 0.0

        para.bef, para.aft = spc(first_kid(pprs, "spcBef")), spc(first_kid(pprs, "spcAft"))

        if has_bullet:
            if lname(bu) == "buChar":
                txt = bu.get("char") or "•"
            else:
                del counters[lvl + 1:]
                while len(counters) <= lvl:
                    counters.append(0)
                if counters[lvl] == 0:
                    counters[lvl] = int(num(bu, "startAt", 1)) - 1
                counters[lvl] += 1
                txt = auto_num(bu.get("type") or "arabicPeriod", counters[lvl])
            clr_el = first_kid(pprs, "buClr")
            bc = color_of(clr_el, ctx) if clr_el is not None else None
            if bc is None:
                bc = (run_color(first_props[:1], ctx) if force else run_color(first_props, ctx)) or color
            szp = first_kid(pprs, "buSzPct")
            bsize = num(szp, "val") / 100000.0 * base if szp is not None else base
            bf = first_kid(pprs, "buFont")
            bface = attr(bf, "typeface", "") or ""
            if bface.startswith("+"):
                bface = ""
            para.bullet = Bullet(txt, bc, bsize, bface)
            if para.indent >= 0 and para.mar_l == 0:
                para.indent = 0.0
        else:
            del counters[lvl:]
            if para.indent < 0 and para.mar_l == 0:
                para.indent = 0.0

        for r in runs_el:
            n = lname(r)
            if n == "br":
                para.runs.append(Run("\n", base, br=True))
                continue
            rpr = kid(r, "rPr")
            props = ([rpr] if rpr is not None else []) + defs
            t = ""
            te = kid(r, "t")
            if te is not None and te.text:
                t = te.text
            if n == "fld" and attr(r, "type", "").lower().startswith("slidenum"):
                t = str(ctx.slide_no)
            if not t:
                continue
            b, i = first_attr(props, "b"), first_attr(props, "i")
            u, st = first_attr(props, "u"), first_attr(props, "strike")
            col = (run_color([rpr] if rpr is not None else [], ctx) or color) if force else (run_color(props, ctx) or color)
            para.runs.append(Run(
                text=t, size=size_of(props), bold=b in ("1", "true"), italic=i in ("1", "true"),
                underline=bool(u and u != "none"), strike=bool(st and st != "noStrike"),
                caps=first_attr(props, "cap") == "all", baseline=int(first_attr(props, "baseline") or 0),
                spacing=float(first_attr(props, "spc") or 0) / 100.0 * PT, color=col, font=font_of(props, ctx)))
        para.end_size = size_of(([end_rpr] if end_rpr is not None else []) + defs)
        paras.append(para)
    return paras


# --------------------------------------------------------------------------- shapes
POLY = {
    "triangle": "50,0 100,100 0,100", "rtTriangle": "0,0 100,100 0,100", "diamond": "50,0 100,50 50,100 0,50",
    "parallelogram": "25,0 100,0 75,100 0,100", "trapezoid": "20,0 80,0 100,100 0,100",
    "pentagon": "50,0 100,38 82,100 18,100 0,38", "hexagon": "25,0 75,0 100,50 75,100 25,100 0,50",
    "octagon": "30,0 70,0 100,30 100,70 70,100 30,100 0,70 0,30",
    "rightArrow": "0,30 60,30 60,0 100,50 60,100 60,70 0,70", "leftArrow": "100,30 40,30 40,0 0,50 40,100 40,70 100,70",
    "upArrow": "30,100 30,40 0,40 50,0 100,40 70,40 70,100", "downArrow": "30,0 70,0 70,60 100,60 50,100 0,60 30,60",
    "chevron": "0,0 70,0 100,50 70,100 0,100 30,50", "homePlate": "0,0 75,0 100,50 75,100 0,100",
    "star5": "50,0 61,35 98,35 68,57 79,91 50,70 21,91 32,57 2,35 39,35",
    "plus": "35,0 65,0 65,35 100,35 100,65 65,65 65,100 35,100 35,65 0,65 0,35 35,35",
    "mathPlus": "35,0 65,0 65,35 100,35 100,65 65,65 65,100 35,100 35,65 0,65 0,35 35,35",
}


def _adj(geom, name, default):
    for gd in kids(kid(geom, "avLst"), "gd"):
        if gd.get("name") == name:
            m = re.search(r"val\s+(-?\d+)", gd.get("fmla", ""))
            if m:
                return float(m.group(1))
    return default


def _custom_path(cust, w, h) -> Optional[QPainterPath]:
    out = QPainterPath()
    got = False
    for pth in kids(kid(cust, "pathLst"), "path"):
        pw = num(pth, "w") or w * EMU
        ph = num(pth, "h") or h * EMU
        sx, sy = w / pw, h / ph

        def pt(e):
            p = kid(e, "pt")
            return QPointF(num(p, "x") * sx, num(p, "y") * sy)

        cur = QPointF()
        for c in pth:
            n = lname(c)
            if n == "moveTo":
                cur = pt(c)
                out.moveTo(cur)
            elif n == "lnTo":
                cur = pt(c)
                out.lineTo(cur)
            elif n == "cubicBezTo":
                p = [QPointF(num(x, "x") * sx, num(x, "y") * sy) for x in kids(c, "pt")]
                if len(p) == 3:
                    out.cubicTo(*p)
                    cur = p[2]
            elif n == "quadBezTo":
                p = [QPointF(num(x, "x") * sx, num(x, "y") * sy) for x in kids(c, "pt")]
                if len(p) == 2:
                    out.quadTo(*p)
                    cur = p[1]
            elif n == "arcTo":
                wr, hr = num(c, "wR") * sx, num(c, "hR") * sy
                st, sw = num(c, "stAng") / 60000.0, num(c, "swAng") / 60000.0
                if wr and hr:
                    import math
                    a = math.radians(st)
                    cx = cur.x() - wr * math.cos(a)
                    cy = cur.y() - hr * math.sin(a)
                    out.arcTo(cx - wr, cy - hr, wr * 2, hr * 2, -st, -sw)
                    cur = out.currentPosition()
            elif n == "close":
                out.closeSubpath()
            got = True
    return out if got else None


class Builder:
    """Builds draw-list items for one slide."""

    def __init__(self, ctx: Ctx):
        self.ctx = ctx
        self.items: list[Item] = []

    def node(self, n, G: QTransform):
        hid = first(path(n, "nvSpPr", "cNvPr"), path(n, "nvPicPr", "cNvPr"), path(n, "nvGrpSpPr", "cNvPr"),
                    path(n, "nvCxnSpPr", "cNvPr"), path(n, "nvGraphicFramePr", "cNvPr"))
        if hid is not None and hid.get("hidden") == "1":
            return
        t = lname(n)
        try:
            if t in ("sp", "cxnSp"):
                self.sp(n, G)
            elif t == "pic":
                self.pic(n, G)
            elif t == "grpSp":
                self.group(n, G)
            elif t == "graphicFrame":
                self.frame(n, G)
            elif t == "AlternateContent":
                f = first(kid(n, "Choice"), kid(n, "Fallback"))
                for c in f if f is not None else []:
                    self.node(c, G)
        except Exception:  # one bad shape must not blank the slide
            pass

    def tree(self, root, G, skip_ph=False):
        tree = path(root, "cSld", "spTree")
        for c in tree if tree is not None else []:
            if skip_ph and ph_of(c) is not None:
                continue
            self.node(c, G)

    def group(self, g, G):
        xf = get_xfrm(g)
        if xf is None:
            return
        t = make_tf(G, xf)
        co = xf["co"] or (xf["x"], xf["y"])
        ce = xf["ce"] or (xf["w"], xf["h"])
        sx = xf["w"] / ce[0] if ce[0] else 1.0
        sy = xf["h"] / ce[1] if ce[1] else 1.0
        t.scale(sx, sy)
        t.translate(-co[0], -co[1])
        for c in g:
            if lname(c) not in ("nvGrpSpPr", "grpSpPr"):
                self.node(c, t)

    def sp(self, sp, G):
        ctx = self.ctx
        ph = ph_of(sp)
        lsp = msp = None
        if ph is not None:
            lsp = find_ph(ctx.layout, ph, False)
            msp = find_ph(ctx.master, ph_of(lsp) if lsp is not None else ph, True)
        xf = first(get_xfrm(sp), get_xfrm(lsp), get_xfrm(msp))
        if xf is None:
            return
        sppr = kid(sp, "spPr")
        style = kid(sp, "style")
        w, h = xf["w"], xf["h"]
        item = Item("shape", w, h, make_tf(G, xf), make_tf(G, xf, flips=False))

        sppr_chain = [sppr, kid(lsp, "spPr") if lsp is not None else None, kid(msp, "spPr") if msp is not None else None]
        fill = None
        for p in sppr_chain:
            fill = fill_spec(p, ctx)
            if fill is not None:
                break
        if fill is None and style is not None:
            fr = kid(style, "fillRef")
            if fr is not None and num(fr, "idx") > 0:
                c = color_of(fr, ctx)
                fill = ("solid", c) if c else None
        if fill is not None and fill[0] == "none":
            fill = None
        item.fill = fill

        ln_el = None
        have_ln = False
        for p in sppr_chain:
            e = kid(p, "ln") if p is not None else None
            if e is not None:
                ln_el, have_ln = e, True
                break
        item.line = line_spec(ln_el, ctx, style)

        geom = kid(sppr, "prstGeom")
        prst = attr(geom, "prst", "rect")
        cust = kid(sppr, "custGeom")
        is_conn = lname(sp) == "cxnSp"
        if is_conn or prst in ("line", "straightConnector1") or prst.startswith("bentConnector") or prst.startswith("curvedConnector"):
            item.kind = "line"
            if item.line is None:
                item.line = LineSpec(1.0, QColor(0, 0, 0))
        elif cust is not None:
            item.geom = "path"
            item.path = _custom_path(cust, w, h)
            if item.path is None:
                item.geom = "rect"
        elif prst == "ellipse":
            item.geom = "ellipse"
        elif prst in ("roundRect", "flowChartTerminator"):
            item.geom = "round"
            frac = 0.5 if prst == "flowChartTerminator" else _adj(geom, "adj", 16667) / 100000.0
            item.radius = frac * min(w, h)
        elif prst in POLY:
            item.geom = "poly"
            item.poly = POLY[prst]

        txbody = kid(sp, "txBody")
        if txbody is not None and any(kid(p, "r") is not None or kid(p, "fld") is not None or kid(p, "br") is not None
                                      for p in kids(txbody, "p")):
            body_prs = [x for x in (kid(txbody, "bodyPr"),
                                    path(lsp, "txBody", "bodyPr") if lsp is not None else None,
                                    path(msp, "txBody", "bodyPr") if msp is not None else None) if x is not None]

            def bp(n):
                return first_attr(body_prs, n)

            chain = [x for x in (path(sp, "txBody", "lstStyle"),
                                 path(lsp, "txBody", "lstStyle") if lsp is not None else None,
                                 path(msp, "txBody", "lstStyle") if msp is not None else None) if x is not None]
            kind = ph_kind(ph) if ph is not None else "other"
            if ctx.txstyles is not None:
                st = kid(ctx.txstyles, "titleStyle" if kind == "title" else "bodyStyle" if kind == "body" else "otherStyle")
                if st is not None:
                    chain.append(st)
            if ctx.pres_style is not None:
                chain.append(ctx.pres_style)
            fref = kid(style, "fontRef") if style is not None else None
            fcol = color_of(fref, ctx) if fref is not None else None
            af = first_kid(body_prs, "normAutofit")
            scale = num(af, "fontScale") / 100000.0 if af is not None and af.get("fontScale") else 1.0
            paras = build_text(txbody, ctx, chain, color=fcol, force=fref is not None, scale=scale)
            item.text = TextBody(
                paras,
                l=float(bp("lIns") or 91440) / EMU, t=float(bp("tIns") or 45720) / EMU,
                r=float(bp("rIns") or 91440) / EMU, b=float(bp("bIns") or 45720) / EMU,
                anchor=bp("anchor") or "t", wrap=bp("wrap") != "none",
                vertical=(bp("vert") or "horz") not in ("horz", "eaVert"))
        if item.fill is None and item.line is None and item.text is None and item.kind != "line":
            return
        self.items.append(item)

    def pic(self, pic, G):
        ctx = self.ctx
        ph = ph_of(pic)
        lsp = find_ph(ctx.layout, ph, False) if ph is not None else None
        xf = first(get_xfrm(pic), get_xfrm(lsp))
        if xf is None:
            return
        bf = kid(pic, "blipFill")
        blip = kid(bf, "blip")
        rel = ctx.rels.get(attr(blip, "embed"))
        img = ctx.pkg.image(rel[1]) if rel else None
        c = path(pic, "nvPicPr", "cNvPr")
        item = Item("image" if img is not None else "placeholder", xf["w"], xf["h"], make_tf(G, xf), make_tf(G, xf, False),
                    image=img, label="Image (unsupported format)",
                    alt=attr(c, "descr") or attr(c, "name") or "Picture")
        src = kid(bf, "srcRect")
        item.crop = tuple(num(src, k) / 100000.0 for k in ("l", "t", "r", "b"))
        sppr = kid(pic, "spPr")
        g = kid(sppr, "prstGeom")
        prst = attr(g, "prst")
        if prst == "ellipse":
            item.geom = "ellipse"
        elif prst == "roundRect":
            item.geom = "round"
            item.radius = _adj(g, "adj", 16667) / 100000.0 * min(xf["w"], xf["h"])
        item.line = line_spec(kid(sppr, "ln"), ctx)
        self.items.append(item)

    def frame(self, gf, G):
        ctx = self.ctx
        xf = get_xfrm(gf)
        if xf is None:
            return
        data = path(gf, "graphic", "graphicData")
        tbl = kid(data, "tbl")
        tf = make_tf(G, xf)
        if tbl is not None:
            item = Item("table", xf["w"], xf["h"], tf, tf)
            item.cells = self.table(tbl)
            self.items.append(item)
            return
        uri = attr(data, "uri", "")
        label = "Chart" if "chart" in uri else "SmartArt diagram" if "diagram" in uri else \
            "Embedded object" if re.search("ole|object", uri, re.I) else "Content"
        self.items.append(Item("placeholder", xf["w"], xf["h"], tf, tf, label=f"{label} (not rendered)"))

    def table(self, tbl) -> list:
        ctx = self.ctx
        cols = [num(c, "w") / EMU for c in kids(kid(tbl, "tblGrid"), "gridCol")]
        pr = kid(tbl, "tblPr")
        first_row, band = attr(pr, "firstRow") == "1", attr(pr, "bandRow") == "1"
        acc = _hex(ctx.theme.colors.get("accent1", "4472C4"))
        rows = kids(tbl, "tr")
        heights = [num(r, "h") / EMU for r in rows]
        ys = [sum(heights[:i]) for i in range(len(rows))]
        xs = [sum(cols[:i]) for i in range(len(cols))]
        cells = []
        for ri, tr in enumerate(rows):
            ci = 0
            for tc in kids(tr, "tc"):
                span = int(num(tc, "gridSpan", 1))
                rspan = int(num(tc, "rowSpan", 1))
                if attr(tc, "hMerge") == "1" or attr(tc, "vMerge") == "1":
                    ci += 1
                    continue
                tcpr = kid(tc, "tcPr")
                fs = fill_spec(tcpr, ctx)
                bg = fs[1] if fs and fs[0] == "solid" else None
                color, bold = None, False
                if bg is None and fs is None:
                    if first_row and ri == 0:
                        bg, color, bold = QColor(*acc), QColor(255, 255, 255), True
                    elif band:
                        bg = QColor(*acc, 51 if ri % 2 else 26)
                borders = {}
                for key, tag in (("l", "lnL"), ("r", "lnR"), ("t", "lnT"), ("b", "lnB")):
                    e = kid(tcpr, tag)
                    borders[key] = line_spec(e, ctx) if e is not None else LineSpec(1.0, QColor(128, 128, 128, 90))
                tx = kid(tc, "txBody")
                chain = [ctx.pres_style] if ctx.pres_style is not None else []
                paras = build_text(tx, ctx, chain, color=color, force=color is not None)
                if bold:
                    for p in paras:
                        for r in p.runs:
                            r.bold = True
                body = TextBody(paras, l=num(tcpr, "marL", 91440) / EMU, t=num(tcpr, "marT", 45720) / EMU,
                                r=num(tcpr, "marR", 91440) / EMU, b=num(tcpr, "marB", 45720) / EMU,
                                anchor=attr(tcpr, "anchor", "t"))
                if ci < len(xs):
                    w = sum(cols[ci:ci + span])
                    h = sum(heights[ri:ri + rspan])
                    cells.append(Cell(xs[ci], ys[ri], w, h, bg, borders, body))
                ci += span
        return cells


# --------------------------------------------------------------------------- deck
class Deck:
    def __init__(self, filename: str):
        self.filename = filename
        self.pkg = Package(filename)
        pres = self.pkg.xml("ppt/presentation.xml")
        if pres is None:
            raise PptxError("The presentation XML could not be parsed.")
        sz = kid(pres, "sldSz")
        self.width = num(sz, "cx", 9144000) / EMU
        self.height = num(sz, "cy", 5143500) / EMU
        rels = self.pkg.rels("ppt/presentation.xml")
        self.parts = []
        for s in kids(kid(pres, "sldIdLst"), "sldId"):
            r = rels.get(s.get(f"{{{NS_REL}}}id"))
            if r and r[1] in self.pkg.names:
                self.parts.append(r[1])
        if not self.parts:
            raise PptxError("This presentation has no slides.")
        self.pres_style = kid(pres, "defaultTextStyle")
        self._cache: dict[int, Slide] = {}
        self._text: dict[int, str] = {}

    def __len__(self):
        return len(self.parts)

    def _ctx(self, part: str, i: int):
        pkg = self.pkg
        rels = pkg.rels(part)
        lpath = pkg.rel_of_type(part, "slideLayout")
        layout = pkg.xml(lpath) if lpath else None
        mpath = pkg.rel_of_type(lpath, "slideMaster") if lpath else None
        master = pkg.xml(mpath) if mpath else None
        tpath = pkg.rel_of_type(mpath, "theme") if mpath else None
        troot = pkg.xml(tpath) if tpath else None
        theme = parse_theme(troot) if troot is not None else Theme()
        clrmap = {}
        cm = kid(master, "clrMap")
        if cm is not None:
            clrmap = dict(cm.attrib)
        ctx = Ctx(pkg, theme, clrmap, rels, layout, master, kid(master, "txStyles") if master is not None else None,
                  self.pres_style, i + 1)
        return ctx, lpath, mpath

    def slide(self, i: int) -> Slide:
        if i in self._cache:
            return self._cache[i]
        part = self.parts[i]
        root = self.pkg.xml(part)
        ctx, lpath, mpath = self._ctx(part, i)
        b = Builder(ctx)
        ident = QTransform()
        bg = None
        for src, rels_part in ((root, part), (ctx.layout, lpath), (ctx.master, mpath)):
            if src is None:
                continue
            bgel = path(src, "cSld", "bg")
            if bgel is None:
                continue
            sub = Ctx(ctx.pkg, ctx.theme, ctx.clrmap, self.pkg.rels(rels_part), ctx.layout, ctx.master, ctx.txstyles,
                      ctx.pres_style, ctx.slide_no)
            pr = kid(bgel, "bgPr")
            if pr is not None:
                bg = fill_spec(pr, sub)
            else:
                ref = kid(bgel, "bgRef")
                c = color_of(ref, sub) if ref is not None else None
                bg = ("solid", c) if c else None
            if bg is not None:
                break
        show_master = attr(root, "showMasterSp") != "0"
        if show_master and ctx.layout is not None and attr(ctx.layout, "showMasterSp") != "0" and ctx.master is not None:
            b.ctx = Ctx(ctx.pkg, ctx.theme, ctx.clrmap, self.pkg.rels(mpath), ctx.layout, ctx.master, ctx.txstyles,
                        ctx.pres_style, ctx.slide_no)
            b.tree(ctx.master, ident, skip_ph=True)
        if show_master and ctx.layout is not None:
            b.ctx = Ctx(ctx.pkg, ctx.theme, ctx.clrmap, self.pkg.rels(lpath), ctx.layout, ctx.master, ctx.txstyles,
                        ctx.pres_style, ctx.slide_no)
            b.tree(ctx.layout, ident, skip_ph=True)
        b.ctx = ctx
        b.tree(root, ident)

        notes = ""
        npath = self.pkg.rel_of_type(part, "notesSlide")
        nroot = self.pkg.xml(npath) if npath else None
        if nroot is not None:
            tree = path(nroot, "cSld", "spTree")
            for sp in kids(tree, "sp"):
                ph = ph_of(sp)
                if ph is not None and attr(ph, "type") == "body":
                    notes = "\n".join("".join(t.text or "" for t in p.iter() if lname(t) == "t")
                                      for p in kids(kid(sp, "txBody"), "p")).strip()
        s = Slide(b.items, bg, notes, i)
        self._cache[i] = s
        return s

    def text(self, i: int) -> str:
        """All text on slide i (cheap; no layout), for find."""
        if i not in self._text:
            root = self.pkg.xml(self.parts[i])
            out = [t.text for t in root.iter() if lname(t) == "t" and t.text] if root is not None else []
            self._text[i] = "\n".join(out)
        return self._text[i]
