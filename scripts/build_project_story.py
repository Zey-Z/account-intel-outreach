from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "AI_Account_Intelligence_Project_Story.pdf"
PAGE_W, PAGE_H = letter

INK = colors.HexColor("#15252B")
MUTED = colors.HexColor("#65767D")
LINE = colors.HexColor("#D7E0E2")
PAPER = colors.HexColor("#F7FAF8")
GREEN = colors.HexColor("#2E7D62")
TEAL = colors.HexColor("#1F6F7A")
GOLD = colors.HexColor("#C9972D")
RED = colors.HexColor("#B7584A")
BLUE = colors.HexColor("#315A8A")


def text(c: canvas.Canvas, value: str, x: float, y: float, size: float, color=INK, font="Helvetica"):
    c.setFillColor(color)
    c.setFont(font, size)
    c.drawString(x, y, value)


def right(c: canvas.Canvas, value: str, x: float, y: float, size: float, color=MUTED, font="Helvetica"):
    c.setFillColor(color)
    c.setFont(font, size)
    c.drawRightString(x, y, value)


def para(c: canvas.Canvas, value: str, x: float, top: float, width: float, size=9.0, leading=12.0, color=MUTED):
    style = ParagraphStyle(
        "story",
        fontName="Helvetica",
        fontSize=size,
        leading=leading,
        textColor=color,
        spaceAfter=0,
    )
    item = Paragraph(value, style)
    _, height = item.wrap(width, 1000)
    item.drawOn(c, x, top - height)
    return height


def header(c: canvas.Canvas, page: int, eyebrow: str, title: str, subtitle: str):
    c.setFillColor(PAPER)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    text(c, eyebrow.upper(), 42, PAGE_H - 45, 8, GREEN, "Helvetica-Bold")
    right(c, f"PROJECT STORY  |  {page} / 2", PAGE_W - 42, PAGE_H - 45, 8)
    text(c, title, 42, PAGE_H - 88, 25, INK, "Helvetica-Bold")
    para(c, subtitle, 42, PAGE_H - 105, PAGE_W - 84, 10.2, 13.5, MUTED)


def section_title(c: canvas.Canvas, value: str, x: float, y: float):
    c.setFillColor(GREEN)
    c.roundRect(x, y - 2, 5, 16, 2.5, fill=1, stroke=0)
    text(c, value, x + 14, y, 12, INK, "Helvetica-Bold")


def flow_box(c: canvas.Canvas, x: float, y: float, width: float, title: str, body: str, accent):
    c.setFillColor(colors.white)
    c.setStrokeColor(accent)
    c.setLineWidth(1.2)
    c.roundRect(x, y, width, 66, 8, fill=1, stroke=1)
    text(c, title, x + 10, y + 43, 8.7, INK, "Helvetica-Bold")
    para(c, body, x + 10, y + 34, width - 20, 7.2, 8.8, MUTED)


def arrow(c: canvas.Canvas, x1: float, y: float, x2: float):
    c.setStrokeColor(colors.HexColor("#8FA1A6"))
    c.setFillColor(colors.HexColor("#8FA1A6"))
    c.line(x1, y, x2, y)
    c.line(x2, y, x2 - 5, y + 3)
    c.line(x2, y, x2 - 5, y - 3)


def decision_card(c: canvas.Canvas, x: float, y: float, width: float, height: float, title: str, body: str, accent):
    c.setFillColor(colors.white)
    c.setStrokeColor(LINE)
    c.roundRect(x, y, width, height, 8, fill=1, stroke=1)
    c.setFillColor(accent)
    c.roundRect(x, y + height - 7, width, 7, 3, fill=1, stroke=0)
    text(c, title, x + 12, y + height - 28, 9.3, INK, "Helvetica-Bold")
    para(c, body, x + 12, y + height - 41, width - 24, 7.7, 9.8, MUTED)


def layer(c: canvas.Canvas, y: float, title: str, tools: str, meaning: str, accent):
    x = 42
    width = PAGE_W - 84
    c.setFillColor(colors.white)
    c.setStrokeColor(LINE)
    c.roundRect(x, y, width, 58, 8, fill=1, stroke=1)
    c.setFillColor(accent)
    c.roundRect(x, y, 8, 58, 4, fill=1, stroke=0)
    text(c, title, x + 20, y + 35, 9.5, INK, "Helvetica-Bold")
    text(c, tools, x + 20, y + 17, 7.7, accent, "Helvetica-Bold")
    para(c, meaning, x + 170, y + 43, width - 190, 8.2, 10.4, MUTED)


def metric(c: canvas.Canvas, x: float, y: float, width: float, value: str, label: str):
    c.setFillColor(colors.white)
    c.setStrokeColor(LINE)
    c.roundRect(x, y, width, 55, 8, fill=1, stroke=1)
    text(c, value, x + 11, y + 32, 13, INK, "Helvetica-Bold")
    text(c, label, x + 11, y + 14, 7.1, MUTED)


def footer(c: canvas.Canvas, page: int):
    c.setStrokeColor(LINE)
    c.line(42, 35, PAGE_W - 42, 35)
    text(c, "AI Account Intelligence | Independent portfolio deployment", 42, 20, 7.2, MUTED)
    right(c, str(page), PAGE_W - 42, 20, 7.2)


def page_one(c: canvas.Canvas):
    header(
        c,
        1,
        "Business problem and product flow",
        "From account research to a reviewable decision",
        "B2B teams repeatedly research target companies, judge whether they fit, write a first message, and copy the result into a CRM. This system turns that manual loop into a visible workflow without giving AI the final say.",
    )

    section_title(c, "The job to be done", 42, 622)
    para(
        c,
        "For each target account, the workflow answers: <b>What is happening?</b> using public evidence; <b>Is this a fit?</b> using a configurable ideal customer profile; and <b>What should happen next?</b> using a draft that a person reviews. The result is not an auto-send sales bot. It is an AI research desk with a human approval counter.",
        42,
        606,
        PAGE_W - 84,
        9.1,
        12.3,
    )

    section_title(c, "One company through the system", 42, 520)
    y = 432
    gap = 10
    width = (PAGE_W - 84 - 4 * gap) / 5
    nodes = [
        ("1. Intake", "Zapier or API submits company + ICP.", GREEN),
        ("2. Research", "Tavily retrieves public pages and URLs.", TEAL),
        ("3. Reason", "CrewAI analyzes fit and drafts from evidence.", GOLD),
        ("4. Control", "Harness validates facts, state, and confidence.", BLUE),
        ("5. Decide", "Slack review controls HubSpot sync.", RED),
    ]
    for index, item in enumerate(nodes):
        x = 42 + index * (width + gap)
        flow_box(c, x, y, width, *item)
        if index < 4:
            arrow(c, x + width + 2, y + 33, x + width + gap - 3)

    section_title(c, "Six choices that make the workflow dependable", 42, 382)
    card_w = (PAGE_W - 84 - 12) / 2
    cards = [
        ("CrewAI roles, deterministic control", "Researcher, Analyst, and Writer handle uncertain reasoning. Python owns validation, status, retries, and database writes.", GREEN),
        ("A worker for long tasks", "FastAPI returns a tracking ID quickly. A database-backed worker claims the queued run and performs the slower agent work.", TEAL),
        ("Evidence travels with claims", "Every accepted company claim retains its source URL, type, retrieval time, and grounding result.", GOLD),
        ("Human approval before CRM", "Slack captures approve, reject, or revise. Only approved drafts become HubSpot Notes; no outreach is auto-sent.", RED),
        ("One system of record", "PostgreSQL stores runs, companies, findings, analysis, drafts, and the event timeline so the process remains inspectable.", BLUE),
        ("Two modes for two jobs", "Offline deterministic mode makes CI repeatable. CrewAI + Tavily mode demonstrates live agent and web-research behavior.", GREEN),
    ]
    card_h = 88
    row_gap = 10
    start_y = 273
    for index, item in enumerate(cards):
        row = index // 2
        col = index % 2
        decision_card(c, 42 + col * (card_w + 12), start_y - row * (card_h + row_gap), card_w, card_h, *item)

    footer(c, 1)


def page_two(c: canvas.Canvas):
    header(
        c,
        2,
        "Architecture, evidence, and operating boundary",
        "A complete workflow with an honest boundary",
        "The value of the project is not that an LLM can write an email. The value is the surrounding operating system: evidence, state, review, observability, release controls, and an honest boundary between demonstrated behavior and enterprise scale.",
    )

    section_title(c, "Three layers", 42, 620)
    layer(c, 535, "Business workflow", "Zapier | Slack | HubSpot | Power BI", "Lets non-technical users start work, make the decision, file approved output, and monitor the process.", GREEN)
    layer(c, 467, "Agent core", "CrewAI | Tavily | ICP profiles", "Collects public evidence, explains account fit, and prepares a draft with structured outputs.", TEAL)
    layer(c, 399, "Control harness", "FastAPI | Worker | PostgreSQL | Validation", "Owns lifecycle, evidence checks, retries, security boundaries, events, and long-running execution.", GOLD)

    section_title(c, "What was actually verified", 42, 360)
    gap = 9
    metric_w = (PAGE_W - 84 - 3 * gap) / 4
    metrics = [
        ("82 tests", "Offline CI suite"),
        ("5 / 5", "Grounded live findings"),
        ("65", "Verified fit score"),
        ("15 runs", "Power BI snapshot"),
    ]
    for index, item in enumerate(metrics):
        metric(c, 42 + index * (metric_w + gap), 287, metric_w, *item)

    para(
        c,
        "The Oscar Health smoke test ran CrewAI + Tavily on Render, stored five grounded findings in Neon, reached Slack review, recorded a human approval, and created an associated HubSpot Note. GitHub protected pull requests with Ruff, unit tests, and a Docker build; deployment ran behind a test gate. Power BI refreshed from protected, schema-validated CSV exports.",
        42,
        274,
        PAGE_W - 84,
        8.7,
        11.7,
    )

    section_title(c, "Operating model", 42, 205)
    decision_card(
        c,
        42,
        110,
        (PAGE_W - 96) / 2,
        88,
        "Human approval is a system rule",
        "Slack controls the business decision. Only approved drafts become HubSpot Notes; rejected or uncertain work stays outside the CRM and remains visible in the event history.",
        BLUE,
    )
    decision_card(
        c,
        54 + (PAGE_W - 96) / 2,
        110,
        (PAGE_W - 96) / 2,
        88,
        "What enterprise scale would add",
        "A durable queue, shared rate limits, centralized alerts and tracing, backup and restore drills, reviewer authorization, incident procedures, and scheduled dashboard refresh.",
        RED,
    )

    para(
        c,
        "The core product rule remains unchanged at either scale: <b>AI prepares evidence and a draft; a person approves the business action.</b>",
        42,
        94,
        PAGE_W - 84,
        8.8,
        11.5,
        INK,
    )
    footer(c, 2)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT), pagesize=letter)
    c.setTitle("AI Account Intelligence Project Story")
    page_one(c)
    c.showPage()
    page_two(c)
    c.showPage()
    c.save()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
