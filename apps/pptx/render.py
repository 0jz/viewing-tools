"""Paint a parser.Slide with QPainter at any scale."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPixmap, QPolygonF, QRadialGradient, QTextBlockFormat, QTextCharFormat, QTextCursor,
                           QTextDocument, QTextOption)

from .parser import Deck, Item, LineSpec, Slide, TextBody

ALIGN = {"l": Qt.AlignLeft, "ctr": Qt.AlignHCenter, "r": Qt.AlignRight, "just": Qt.AlignJustify, "dist": Qt.AlignJustify}
DEFAULT_FONT = "Segoe UI"


# --------------------------------------------------------------------------- text
def build_doc(body: TextBody, width: float) -> QTextDocument:
    doc = QTextDocument()
    doc.setDocumentMargin(0)
    opt = QTextOption()
    opt.setWrapMode(QTextOption.WordWrap if body.wrap else QTextOption.NoWrap)
    doc.setDefaultTextOption(opt)
    cur = QTextCursor(doc)
    first = True
    for p in body.paras:
        bf = QTextBlockFormat()
        bf.setAlignment(ALIGN.get(p.align, Qt.AlignLeft))
        left = max(p.mar_l, 0.0)
        bf.setLeftMargin(left)
        bf.setTextIndent(p.indent)
        bf.setTopMargin(0 if first else p.bef)
        bf.setBottomMargin(p.aft)
        if p.line_pct:
            bf.setLineHeight(p.line_pct, QTextBlockFormat.ProportionalHeight)
        elif p.line_px:
            bf.setLineHeight(p.line_px, QTextBlockFormat.FixedHeight)
        if p.bullet is not None and left > 0:
            bf.setTabPositions([QTextOption.Tab(left, QTextOption.LeftTab)])
        if first:
            cur.setBlockFormat(bf)
            first = False
        else:
            cur.insertBlock(bf)

        def fmt(size, color, font="", bold=False, italic=False, u=False, st=False, caps=False, base=0, sp=0.0):
            cf = QTextCharFormat()
            f = QFont(font or DEFAULT_FONT)
            f.setPixelSize(max(1, int(round(size * (0.65 if base else 1)))))
            f.setBold(bold)
            f.setItalic(italic)
            f.setUnderline(u)
            f.setStrikeOut(st)
            if caps:
                f.setCapitalization(QFont.AllUppercase)
            if sp:
                f.setLetterSpacing(QFont.AbsoluteSpacing, sp)
            cf.setFont(f)
            cf.setForeground(QBrush(color if color is not None else QColor(0, 0, 0)))
            if base:
                cf.setVerticalAlignment(QTextCharFormat.AlignSuperScript if base > 0 else QTextCharFormat.AlignSubScript)
            return cf

        if p.bullet is not None:
            b = p.bullet
            cur.insertText(b.text + "\t", fmt(b.size, b.color, b.font))
        any_run = False
        for r in p.runs:
            cf = fmt(r.size, r.color, r.font, r.bold, r.italic, r.underline, r.strike, r.caps, r.baseline, r.spacing)
            if r.br:
                cur.insertText(" ", cf)
            else:
                cur.insertText(r.text.replace("\n", " ").replace("\x0b", " "), cf)
                any_run = True
        if not any_run and p.bullet is None:
            cur.insertText("​", fmt(p.end_size, None))
    doc.setTextWidth(width)
    return doc


def draw_text(p: QPainter, body: TextBody, w: float, h: float, cache: dict, key):
    if body.vertical:
        p.save()
        p.translate(w, 0)
        p.rotate(90)
        w, h = h, w
    avail = max(1.0, w - body.l - body.r)
    ck = (key, round(avail, 1))
    doc = cache.get(ck)
    if doc is None:
        doc = build_doc(body, avail)
        cache[ck] = doc
    dh = doc.size().height()
    inner = h - body.t - body.b
    dy = {"ctr": (inner - dh) / 2, "b": inner - dh}.get(body.anchor, 0.0)
    p.save()
    p.translate(body.l, body.t + dy)
    doc.drawContents(p)
    p.restore()
    if body.vertical:
        p.restore()


# --------------------------------------------------------------------------- shapes
def item_path(it: Item) -> QPainterPath:
    path = QPainterPath()
    r = QRectF(0, 0, it.w, it.h)
    if it.geom == "ellipse":
        path.addEllipse(r)
    elif it.geom == "round":
        path.addRoundedRect(r, it.radius, it.radius)
    elif it.geom == "poly":
        pts = []
        for pair in it.poly.split():
            x, y = pair.split(",")
            pts.append(QPointF(float(x) / 100 * it.w, float(y) / 100 * it.h))
        path.addPolygon(QPolygonF(pts))
        path.closeSubpath()
    elif it.geom == "path" and it.path is not None:
        path = it.path
    else:
        path.addRect(r)
    return path


def make_brush(fill, w, h) -> QBrush | None:
    if not fill:
        return None
    kind = fill[0]
    if kind == "solid":
        return QBrush(fill[1])
    if kind == "grad":
        _, stops, angle, radial = fill
        if radial:
            g = QRadialGradient(QPointF(w / 2, h / 2), max(w, h) / 2)
        else:
            a = math.radians(angle)
            dx, dy = math.cos(a), math.sin(a)
            half = (abs(w * dx) + abs(h * dy)) / 2
            c = QPointF(w / 2, h / 2)
            g = QLinearGradient(c - QPointF(dx, dy) * half, c + QPointF(dx, dy) * half)
        for pos, col in stops:
            g.setColorAt(min(1.0, max(0.0, pos)), col)
        return QBrush(g)
    return None


def make_pen(ln: LineSpec | None) -> QPen:
    if ln is None:
        return QPen(Qt.NoPen)
    pen = QPen(ln.color, ln.width)
    pen.setStyle({"dash": Qt.DashLine, "dot": Qt.DotLine}.get(ln.dash, Qt.SolidLine))
    pen.setJoinStyle(Qt.MiterJoin)
    return pen


def draw_arrow(p: QPainter, tip: QPointF, frm: QPointF, ln: LineSpec):
    d = tip - frm
    n = math.hypot(d.x(), d.y())
    if n == 0:
        return
    ux, uy = d.x() / n, d.y() / n
    size = max(6.0, ln.width * 4)
    base = tip - QPointF(ux, uy) * size
    off = QPointF(-uy, ux) * size / 2.2
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(ln.color))
    p.drawPolygon(QPolygonF([tip, base + off, base - off]))


def draw_item(p: QPainter, it: Item, base, cache: dict):
    p.setWorldTransform(it.tf * base)
    if it.kind == "line":
        ln = it.line
        p.setPen(make_pen(ln))
        a, b = QPointF(0, 0), QPointF(it.w, it.h)
        p.drawLine(a, b)
        if ln.head:
            draw_arrow(p, a, b, ln)
        if ln.tail:
            draw_arrow(p, b, a, ln)
    elif it.kind == "image":
        img: QImage = it.image
        l, t, r, b = it.crop
        iw, ih = img.width(), img.height()
        src = QRectF(l * iw, t * ih, max(1.0, iw * (1 - l - r)), max(1.0, ih * (1 - t - b)))
        p.save()
        if it.geom != "rect":
            p.setClipPath(item_path(it))
        p.drawImage(QRectF(0, 0, it.w, it.h), img, src)
        p.restore()
        if it.line is not None:
            p.setPen(make_pen(it.line))
            p.setBrush(Qt.NoBrush)
            p.drawPath(item_path(it))
    elif it.kind == "placeholder":
        p.setPen(QPen(QColor(150, 160, 170), 1, Qt.DashLine))
        p.setBrush(QColor(150, 160, 170, 40))
        p.drawRect(QRectF(0, 0, it.w, it.h))
        p.setPen(QColor(100, 110, 120))
        f = QFont(DEFAULT_FONT)
        f.setPixelSize(14)
        p.setFont(f)
        p.drawText(QRectF(0, 0, it.w, it.h), Qt.AlignCenter | Qt.TextWordWrap, it.label)
    elif it.kind == "table":
        for ci, c in enumerate(it.cells):
            rect = QRectF(c.x, c.y, c.w, c.h)
            if c.fill is not None:
                p.fillRect(rect, c.fill)
            for side, ln in c.borders.items():
                if ln is None:
                    continue
                p.setPen(make_pen(ln))
                if side == "l":
                    p.drawLine(rect.topLeft(), rect.bottomLeft())
                elif side == "r":
                    p.drawLine(rect.topRight(), rect.bottomRight())
                elif side == "t":
                    p.drawLine(rect.topLeft(), rect.topRight())
                else:
                    p.drawLine(rect.bottomLeft(), rect.bottomRight())
            if c.text.paras:
                p.save()
                p.translate(c.x, c.y)
                p.setClipRect(QRectF(0, 0, c.w, c.h))
                draw_text(p, c.text, c.w, c.h, cache, (id(it), ci))
                p.restore()
    else:  # shape
        brush = make_brush(it.fill, it.w, it.h)
        if brush is not None or it.line is not None:
            p.setPen(make_pen(it.line))
            p.setBrush(brush if brush is not None else Qt.NoBrush)
            if it.geom == "rect":
                p.drawRect(QRectF(0, 0, it.w, it.h))
            else:
                p.drawPath(item_path(it))
        if it.fill and it.fill[0] == "img" and it.fill[1] is not None:
            p.save()
            p.setClipPath(item_path(it))
            p.drawImage(QRectF(0, 0, it.w, it.h), it.fill[1])
            p.restore()
    if it.text is not None and it.kind in ("shape", "line"):
        p.setWorldTransform(it.text_tf * base)
        draw_text(p, it.text, it.w, it.h, cache, id(it))


def paint_slide(p: QPainter, slide: Slide, cache: dict):
    """Paint into the painter's current coordinate system (slide px units)."""
    p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
    base = p.worldTransform()
    for it in slide.items:
        p.save()
        draw_item(p, it, base, cache)
        p.restore()
        p.setWorldTransform(base)


def paint_background(p: QPainter, slide: Slide, w: float, h: float):
    bg = slide.background
    p.fillRect(QRectF(0, 0, w, h), QColor(255, 255, 255))
    if bg and bg[0] != "none":
        if bg[0] == "img" and bg[1] is not None:
            p.drawImage(QRectF(0, 0, w, h), bg[1])
        else:
            b = make_brush(bg, w, h)
            if b is not None:
                p.fillRect(QRectF(0, 0, w, h), b)


def render_pixmap(deck: Deck, index: int, width: int, cache: dict | None = None) -> QPixmap:
    scale = width / deck.width
    pm = QPixmap(width, max(1, round(deck.height * scale)))
    pm.fill(Qt.white)
    p = QPainter(pm)
    p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
    p.scale(scale, scale)
    try:
        s = deck.slide(index)
        paint_background(p, s, deck.width, deck.height)
        paint_slide(p, s, cache if cache is not None else {})
    except Exception as e:  # keep the app alive on a malformed slide
        p.setPen(QColor(180, 0, 0))
        p.drawText(QRectF(20, 20, deck.width - 40, 100), Qt.TextWordWrap, f"Could not render slide: {e}")
    p.end()
    return pm
