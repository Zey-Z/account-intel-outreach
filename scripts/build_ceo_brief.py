from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs"
PDF_PATH = OUT / "AI_Account_Intelligence_Brief.pdf"
HTML_PATH = OUT / "AI_Account_Intelligence_Brief.html"

PAGE_W, PAGE_H = landscape(letter)
INK = colors.HexColor("#15252B")
MUTED = colors.HexColor("#65767D")
LINE = colors.HexColor("#D7E0E2")
PAPER = colors.HexColor("#F7FAF8")
GREEN = colors.HexColor("#2E7D62")
TEAL = colors.HexColor("#1F6F7A")
GOLD = colors.HexColor("#C9972D")
RED = colors.HexColor("#B7584A")
BLUE = colors.HexColor("#315A8A")


def draw_text(c: canvas.Canvas, text: str, x: float, y: float, size: float, color=INK, font="Helvetica"):
    c.setFillColor(color)
    c.setFont(font, size)
    c.drawString(x, y, text)


def draw_right(c: canvas.Canvas, text: str, x: float, y: float, size: float, color=INK, font="Helvetica"):
    c.setFillColor(color)
    c.setFont(font, size)
    c.drawRightString(x, y, text)


def paragraph(c: canvas.Canvas, text: str, x: float, top: float, width: float, size=9.0, leading=11.5, color=MUTED):
    style = ParagraphStyle(
        "brief",
        fontName="Helvetica",
        fontSize=size,
        leading=leading,
        textColor=color,
        spaceAfter=0,
    )
    item = Paragraph(text, style)
    _, height = item.wrap(width, 1000)
    item.drawOn(c, x, top - height)
    return height


def pill(c: canvas.Canvas, text: str, x: float, y: float):
    width = stringWidth(text, "Helvetica-Bold", 8) + 20
    c.setFillColor(GREEN)
    c.roundRect(x, y, width, 18, 9, fill=1, stroke=0)
    draw_text(c, text, x + 10, y + 5, 8, colors.white, "Helvetica-Bold")


def kpi(c: canvas.Canvas, x: float, y: float, width: float, value: str, label: str):
    c.setFillColor(colors.white)
    c.setStrokeColor(LINE)
    c.roundRect(x, y, width, 50, 8, fill=1, stroke=1)
    draw_text(c, value, x + 12, y + 28, 13, INK, "Helvetica-Bold")
    draw_text(c, label, x + 12, y + 12, 7.3, MUTED)


def flow_node(c: canvas.Canvas, x: float, y: float, width: float, label: str, sub: str, accent):
    c.setFillColor(colors.white)
    c.setStrokeColor(accent)
    c.setLineWidth(1.3)
    c.roundRect(x, y, width, 54, 8, fill=1, stroke=1)
    draw_text(c, label, x + 10, y + 35, 8.5, INK, "Helvetica-Bold")
    paragraph(c, sub, x + 10, y + 25, width - 20, 7.0, 8.2, MUTED)


def arrow(c: canvas.Canvas, x1: float, y: float, x2: float):
    c.setStrokeColor(colors.HexColor("#8FA1A6"))
    c.setFillColor(colors.HexColor("#8FA1A6"))
    c.setLineWidth(1.1)
    c.line(x1, y, x2, y)
    c.line(x2, y, x2 - 5, y + 3)
    c.line(x2, y, x2 - 5, y - 3)


def card(c: canvas.Canvas, x: float, y: float, width: float, height: float, title: str, body: str, accent):
    c.setFillColor(colors.white)
    c.setStrokeColor(LINE)
    c.roundRect(x, y, width, height, 10, fill=1, stroke=1)
    c.setFillColor(accent)
    c.roundRect(x, y + height - 8, width, 8, 4, fill=1, stroke=0)
    draw_text(c, title, x + 14, y + height - 30, 10, INK, "Helvetica-Bold")
    paragraph(c, body, x + 14, y + height - 46, width - 28, 8.4, 10.8, MUTED)


def build_pdf() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(PDF_PATH), pagesize=(PAGE_W, PAGE_H))
    c.setTitle("AI Account Intelligence Executive Brief")
    c.setFillColor(PAPER)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    margin = 36
    top = PAGE_H - margin
    pill(c, "EXECUTIVE BRIEF", margin, top - 4)
    draw_right(c, "Portfolio AI agent system | Live workflow verified", PAGE_W - margin, top + 1, 8.5, MUTED)

    draw_text(c, "AI Account Intelligence & Outreach Ops", margin, top - 48, 24, INK, "Helvetica-Bold")
    paragraph(
        c,
        "A human-approved multi-agent workflow that researches target accounts, explains ICP fit, and prepares source-grounded outreach. AI handles the repetitive first pass; a person controls the business decision before CRM sync.",
        margin,
        top - 66,
        PAGE_W - 2 * margin,
        10.2,
        13,
        MUTED,
    )

    kpi_y = top - 151
    gap = 8
    kpi_w = (PAGE_W - 2 * margin - 3 * gap) / 4
    metrics = [
        ("3 agents", "Researcher / Analyst / Writer"),
        ("5 / 5 grounded", "Verified Oscar Health findings"),
        ("82 tests", "Offline CI quality gate"),
        ("15 runs", "Verified Power BI snapshot"),
    ]
    for index, metric in enumerate(metrics):
        kpi(c, margin + index * (kpi_w + gap), kpi_y, kpi_w, *metric)

    flow_title_y = kpi_y - 34
    draw_text(c, "One Run, End to End", margin, flow_title_y, 13, INK, "Helvetica-Bold")
    draw_text(c, "Like an AI research desk with a human approval counter.", margin + 132, flow_title_y + 1, 8.5, MUTED)

    flow_y = flow_title_y - 72
    node_gap = 14
    node_w = (PAGE_W - 2 * margin - 5 * node_gap) / 6
    nodes = [
        ("Zapier / API", "Company + domain + ICP", GREEN),
        ("Research", "Public sources + evidence", TEAL),
        ("Qualify", "Fit score + rationale", GOLD),
        ("Draft", "Evidence-bound copy", BLUE),
        ("Human Review", "Approve, reject, revise", RED),
        ("CRM + BI", "Approved record + metrics", GREEN),
    ]
    for index, node in enumerate(nodes):
        x = margin + index * (node_w + node_gap)
        flow_node(c, x, flow_y, node_w, *node)
        if index < len(nodes) - 1:
            arrow(c, x + node_w + 2, flow_y + 27, x + node_w + node_gap - 3)

    card_y = 70
    card_gap = 12
    card_w = (PAGE_W - 2 * margin - 2 * card_gap) / 3
    card_h = 151
    card(
        c,
        margin,
        card_y,
        card_w,
        card_h,
        "Business Value",
        "Turns scattered account research into a repeatable workflow. Teams receive faster first-pass research, visible reasoning, reusable ICP rules, and a trackable handoff instead of an isolated AI answer.",
        GREEN,
    )
    card(
        c,
        margin + card_w + card_gap,
        card_y,
        card_w,
        card_h,
        "Control Model",
        "Public company data only. Every accepted claim keeps a source URL. The harness validates evidence and confidence, logs state changes, and routes uncertainty to a person. The system never auto-sends outreach.",
        TEAL,
    )
    card(
        c,
        margin + 2 * (card_w + card_gap),
        card_y,
        card_w,
        card_h,
        "Verified Delivery",
        "CrewAI + Tavily ran on Render with Neon PostgreSQL. Slack recorded approval, HubSpot received the approved Note, Power BI refreshed from protected CSV exports, and CI gated deployment.",
        GOLD,
    )

    c.setStrokeColor(LINE)
    c.line(margin, 51, PAGE_W - margin, 51)
    draw_text(c, "Deployment scope: independent portfolio environment using public company data.", margin, 36, 7.2, MUTED)
    draw_right(c, "Human-approved drafts | No auto-send | Demo infrastructure", PAGE_W - margin, 36, 7.2, MUTED)
    c.showPage()
    c.save()


def build_html() -> None:
    html = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>AI Account Intelligence Executive Brief</title>
<style>
:root{--ink:#15252b;--muted:#65767d;--line:#d7e0e2;--paper:#f7faf8;--green:#2e7d62;--teal:#1f6f7a;--gold:#c9972d;--red:#b7584a;--blue:#315a8a}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:Arial,Helvetica,sans-serif}.page{width:1056px;height:816px;padding:48px;margin:auto}.top{display:flex;justify-content:space-between;align-items:center;color:var(--muted);font-size:12px}.pill{background:var(--green);color:#fff;border-radius:999px;padding:7px 13px;font-weight:700}h1{font-size:34px;margin:28px 0 10px}.lede{color:var(--muted);font-size:15px;line-height:1.45}.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:26px 0}.kpi,.node,.card{background:#fff;border:1px solid var(--line);border-radius:10px}.kpi{padding:13px}.kpi b{display:block;font-size:20px}.kpi span,.node span,.card p{color:var(--muted)}.flow{display:grid;grid-template-columns:repeat(6,1fr);gap:12px}.node{padding:12px;min-height:74px}.node b{display:block;margin-bottom:7px}.node span{font-size:11px}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:30px}.card{padding:18px;min-height:150px;border-top:8px solid var(--green)}.card:nth-child(2){border-top-color:var(--teal)}.card:nth-child(3){border-top-color:var(--gold)}.card h3{font-size:16px}.card p{font-size:13px;line-height:1.45}.footer{border-top:1px solid var(--line);margin-top:22px;padding-top:10px;display:flex;justify-content:space-between;color:var(--muted);font-size:11px}
</style></head><body><main class="page">
<div class="top"><div class="pill">EXECUTIVE BRIEF</div><div>Portfolio AI agent system | Live workflow verified</div></div>
<h1>AI Account Intelligence &amp; Outreach Ops</h1><p class="lede">A human-approved multi-agent workflow that researches target accounts, explains ICP fit, and prepares source-grounded outreach. AI handles the repetitive first pass; a person controls the business decision before CRM sync.</p>
<section class="kpis"><div class="kpi"><b>3 agents</b><span>Researcher / Analyst / Writer</span></div><div class="kpi"><b>5 / 5 grounded</b><span>Verified Oscar Health findings</span></div><div class="kpi"><b>82 tests</b><span>Offline CI quality gate</span></div><div class="kpi"><b>15 runs</b><span>Verified Power BI snapshot</span></div></section>
<h2>One Run, End to End</h2><section class="flow"><div class="node"><b>Zapier / API</b><span>Company + domain + ICP</span></div><div class="node"><b>Research</b><span>Public sources + evidence</span></div><div class="node"><b>Qualify</b><span>Fit score + rationale</span></div><div class="node"><b>Draft</b><span>Evidence-bound copy</span></div><div class="node"><b>Human Review</b><span>Approve, reject, revise</span></div><div class="node"><b>CRM + BI</b><span>Approved record + metrics</span></div></section>
<section class="cards"><div class="card"><h3>Business Value</h3><p>Turns scattered account research into a repeatable workflow with visible reasoning, reusable ICP rules, and a trackable handoff.</p></div><div class="card"><h3>Control Model</h3><p>Every accepted claim keeps a source URL. Validation and status are controlled outside the agents. The system never auto-sends outreach.</p></div><div class="card"><h3>Verified Delivery</h3><p>CrewAI + Tavily ran on Render with Neon. Slack approval, HubSpot filing, Power BI refresh, and CI-gated deployment were exercised.</p></div></section>
<div class="footer"><span>Independent portfolio deployment using public company data.</span><span>Human-approved drafts | No auto-send | Demo infrastructure</span></div>
</main></body></html>"""
    HTML_PATH.write_text(html, encoding="utf-8")


def main() -> None:
    build_pdf()
    build_html()
    print(f"wrote {PDF_PATH}")
    print(f"wrote {HTML_PATH}")


if __name__ == "__main__":
    main()
