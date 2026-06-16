from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Paragraph
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs"
PDF_PATH = OUT / "AI_Account_Intelligence_CEO_Brief_EN.pdf"
HTML_PATH = OUT / "AI_Account_Intelligence_CEO_Brief_EN.html"

PAGE_W, PAGE_H = landscape(letter)

INK = colors.HexColor("#15252B")
MUTED = colors.HexColor("#65767D")
LINE = colors.HexColor("#D7E0E2")
PAPER = colors.HexColor("#F7FAF8")
CARD = colors.white
GREEN = colors.HexColor("#2E7D62")
TEAL = colors.HexColor("#1F6F7A")
GOLD = colors.HexColor("#C9972D")
RED = colors.HexColor("#B7584A")
BLUE = colors.HexColor("#315A8A")


def draw_text(c: canvas.Canvas, text: str, x: float, y: float, size: int, color=INK, font="Helvetica"):
    c.setFillColor(color)
    c.setFont(font, size)
    c.drawString(x, y, text)


def draw_right_text(c: canvas.Canvas, text: str, x: float, y: float, size: int, color=INK, font="Helvetica"):
    c.setFillColor(color)
    c.setFont(font, size)
    c.drawRightString(x, y, text)


def draw_para(c: canvas.Canvas, text: str, x: float, y: float, w: float, h: float, size: int = 9, leading: int = 11, color=INK):
    style = ParagraphStyle(
        name="brief",
        fontName="Helvetica",
        fontSize=size,
        leading=leading,
        textColor=color,
        spaceAfter=0,
    )
    p = Paragraph(text, style)
    p.wrapOn(c, w, h)
    p.drawOn(c, x, y)


def draw_para_top(c: canvas.Canvas, text: str, x: float, top_y: float, w: float, size: int = 9, leading: int = 11, color=INK):
    style = ParagraphStyle(
        name="brief_top",
        fontName="Helvetica",
        fontSize=size,
        leading=leading,
        textColor=color,
        spaceAfter=0,
    )
    p = Paragraph(text, style)
    _, para_h = p.wrap(w, 1000)
    p.drawOn(c, x, top_y - para_h)
    return para_h


def pill(c: canvas.Canvas, text: str, x: float, y: float, color, text_color=colors.white):
    width = stringWidth(text, "Helvetica-Bold", 8) + 18
    c.setFillColor(color)
    c.roundRect(x, y, width, 17, 8, fill=1, stroke=0)
    draw_text(c, text, x + 9, y + 5, 8, text_color, "Helvetica-Bold")
    return width


def card(c: canvas.Canvas, x: float, y: float, w: float, h: float, title: str, body: str, accent=GREEN):
    c.setFillColor(CARD)
    c.setStrokeColor(LINE)
    c.roundRect(x, y, w, h, 10, fill=1, stroke=1)
    c.setFillColor(accent)
    c.roundRect(x, y + h - 8, w, 8, 4, fill=1, stroke=0)
    draw_text(c, title, x + 14, y + h - 30, 10, INK, "Helvetica-Bold")
    draw_para_top(c, body, x + 14, y + h - 56, w - 28, 8.6, 11, MUTED)


def flow_node(c: canvas.Canvas, x: float, y: float, w: float, h: float, label: str, sub: str, color):
    c.setFillColor(colors.white)
    c.setStrokeColor(color)
    c.setLineWidth(1.4)
    c.roundRect(x, y, w, h, 8, fill=1, stroke=1)
    draw_text(c, label, x + 10, y + h - 18, 8.5, INK, "Helvetica-Bold")
    draw_para(c, sub, x + 10, y + 9, w - 20, h - 27, 7.2, 8.4, MUTED)


def arrow(c: canvas.Canvas, x1: float, y1: float, x2: float, y2: float):
    c.setStrokeColor(colors.HexColor("#8FA1A6"))
    c.setLineWidth(1.1)
    c.line(x1, y1, x2, y2)
    c.setFillColor(colors.HexColor("#8FA1A6"))
    c.line(x2, y2, x2 - 5, y2 + 3)
    c.line(x2, y2, x2 - 5, y2 - 3)


def build_pdf() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(PDF_PATH), pagesize=landscape(letter))
    c.setTitle("AI Account Intelligence CEO Brief")

    c.setFillColor(PAPER)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    margin = 0.46 * inch
    top = PAGE_H - margin

    pill(c, "EXECUTIVE BRIEF", margin, top - 16, GREEN)
    draw_right_text(c, "Portfolio AI Agent System | Demo-validated", PAGE_W - margin, top - 12, 8.5, MUTED)
    draw_text(c, "AI Account Intelligence & Outreach Ops System", margin, top - 48, 24, INK, "Helvetica-Bold")
    draw_para_top(
        c,
        "A human-approved multi-agent workflow that researches target accounts, scores ICP fit, drafts source-grounded outreach, "
        "and routes qualified cases to Slack review before CRM sync. It shows how AI agents can improve a business workflow without removing human judgment.",
        margin,
        top - 76,
        PAGE_W - 2 * margin,
        10.3,
        13,
        MUTED,
    )

    # KPI strip
    kpi_y = top - 154
    kpis = [
        ("3-agent crew", "Researcher / Analyst / Writer"),
        ("5 grounded findings", "Latest Render smoke test"),
        ("65 fit score", "Qualified for review"),
        ("23.4s latency", "Live CrewAI + Tavily run"),
    ]
    kpi_w = (PAGE_W - 2 * margin - 24) / 4
    for i, (big, small) in enumerate(kpis):
        x = margin + i * (kpi_w + 8)
        c.setFillColor(colors.white)
        c.setStrokeColor(LINE)
        c.roundRect(x, kpi_y, kpi_w, 48, 8, fill=1, stroke=1)
        draw_text(c, big, x + 12, kpi_y + 27, 13, INK, "Helvetica-Bold")
        draw_text(c, small, x + 12, kpi_y + 12, 7.5, MUTED)

    # User flow
    flow_title_y = kpi_y - 36
    draw_text(c, "User Flow", margin, flow_title_y, 13, INK, "Helvetica-Bold")
    draw_text(c, "The system behaves like an AI research desk with a human approval counter.", margin + 72, flow_title_y + 1, 8.5, MUTED)

    flow_y = flow_title_y - 76
    node_w = 105
    node_h = 52
    gap = 15
    nodes = [
        ("Zapier Input", "Company + domain + ICP profile", GREEN),
        ("Researcher", "Reads public sources and stores evidence", TEAL),
        ("Analyst", "Scores fit and explains the why", GOLD),
        ("Writer", "Drafts outreach, never sends", BLUE),
        ("Slack Review", "Approve, reject, or revise", RED),
        ("CRM / BI", "Approved records and reporting", GREEN),
    ]
    for i, (label, sub, color) in enumerate(nodes):
        x = margin + i * (node_w + gap)
        flow_node(c, x, flow_y, node_w, node_h, label, sub, color)
        if i < len(nodes) - 1:
            arrow(c, x + node_w + 2, flow_y + node_h / 2, x + node_w + gap - 4, flow_y + node_h / 2)

    # Bottom cards
    bottom_y = margin + 22
    card_h = 154
    card_w = (PAGE_W - 2 * margin - 24) / 3
    card(
        c,
        margin,
        bottom_y,
        card_w,
        card_h,
        "Product Spec",
        "<b>Input:</b> target company list and ICP profile.<br/>"
        "<b>Core:</b> CrewAI sequential agents, Tavily source extraction, validation harness, PostgreSQL state.<br/>"
        "<b>Output:</b> structured JSON, fit rationale, outreach draft, status history, and reviewable Slack card.",
        GREEN,
    )
    card(
        c,
        margin + card_w + 12,
        bottom_y,
        card_w,
        card_h,
        "Why It Matters",
        "Teams lose hours researching accounts, judging fit, and writing first drafts. This system turns that manual loop into a governed workflow: faster research, clearer evidence, reusable ICP logic, and human approval before action.",
        TEAL,
    )
    card(
        c,
        margin + 2 * (card_w + 12),
        bottom_y,
        card_w,
        card_h,
        "Control Model",
        "The AI is not allowed to become an unsupervised sales bot. It uses public company data only, keeps source URLs, logs every run, flags uncertainty, and sends qualified drafts to human review before any CRM movement.",
        GOLD,
    )

    # Footer
    c.setStrokeColor(LINE)
    c.line(margin, margin, PAGE_W - margin, margin)
    draw_text(c, "Current proof: Render live run produced sent_to_review with source-grounded evidence and Slack review delivery.", margin, margin - 16, 7.4, MUTED)
    draw_right_text(c, "Public company data only | Not HIPAA / not clinical / not auto-send", PAGE_W - margin, margin - 16, 7.4, MUTED)

    c.showPage()
    c.save()


def build_html() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>AI Account Intelligence CEO Brief</title>
  <style>
    :root { --ink:#15252B; --muted:#65767D; --line:#D7E0E2; --paper:#F7FAF8; --green:#2E7D62; --teal:#1F6F7A; --gold:#C9972D; --red:#B7584A; --blue:#315A8A; }
    body { margin:0; background:var(--paper); color:var(--ink); font-family: Arial, Helvetica, sans-serif; }
    .page { width:1056px; height:816px; padding:44px; box-sizing:border-box; margin:0 auto; }
    .top { display:flex; justify-content:space-between; align-items:center; font-size:12px; color:var(--muted); }
    .pill { background:var(--green); color:white; border-radius:999px; padding:7px 13px; font-weight:700; letter-spacing:.08em; }
    h1 { font-size:36px; margin:28px 0 12px; letter-spacing:-.02em; }
    .lede { font-size:16px; line-height:1.45; color:var(--muted); max-width:930px; }
    .kpis { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin:28px 0 24px; }
    .kpi, .card, .node { background:white; border:1px solid var(--line); border-radius:12px; }
    .kpi { padding:14px 16px; }
    .kpi b { display:block; font-size:20px; margin-bottom:5px; }
    .kpi span { color:var(--muted); font-size:12px; }
    .flow-head { display:flex; gap:18px; align-items:baseline; margin-bottom:12px; }
    .flow-head h2 { margin:0; font-size:19px; }
    .flow-head p { margin:0; color:var(--muted); font-size:13px; }
    .flow { display:grid; grid-template-columns:repeat(6,1fr); gap:14px; position:relative; }
    .node { min-height:72px; padding:12px; position:relative; }
    .node:not(:last-child)::after { content:""; position:absolute; right:-12px; top:35px; width:10px; border-top:2px solid #8FA1A6; }
    .node b { display:block; font-size:13px; margin-bottom:6px; }
    .node span { color:var(--muted); font-size:11px; line-height:1.25; }
    .node.green { border-color:var(--green); } .node.teal { border-color:var(--teal); } .node.gold { border-color:var(--gold); } .node.blue { border-color:var(--blue); } .node.red { border-color:var(--red); }
    .cards { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-top:34px; }
    .card { padding:18px; min-height:148px; border-top:9px solid var(--green); }
    .card:nth-child(2) { border-top-color:var(--teal); } .card:nth-child(3) { border-top-color:var(--gold); }
    .card h3 { margin:0 0 12px; font-size:16px; }
    .card p { margin:0; color:var(--muted); font-size:13px; line-height:1.45; }
    .footer { display:flex; justify-content:space-between; border-top:1px solid var(--line); margin-top:28px; padding-top:12px; color:var(--muted); font-size:11px; }
  </style>
</head>
<body>
  <main class="page">
    <div class="top"><div class="pill">EXECUTIVE BRIEF</div><div>Portfolio AI Agent System | Demo-validated</div></div>
    <h1>AI Account Intelligence & Outreach Ops System</h1>
    <p class="lede">A human-approved multi-agent workflow that researches target accounts, scores ICP fit, drafts source-grounded outreach, and routes qualified cases to Slack review before CRM sync. It shows how AI agents can improve a business workflow without removing human judgment.</p>
    <section class="kpis">
      <div class="kpi"><b>3-agent crew</b><span>Researcher / Analyst / Writer</span></div>
      <div class="kpi"><b>5 grounded findings</b><span>Latest Render smoke test</span></div>
      <div class="kpi"><b>65 fit score</b><span>Qualified for review</span></div>
      <div class="kpi"><b>23.4s latency</b><span>Live CrewAI + Tavily run</span></div>
    </section>
    <div class="flow-head"><h2>User Flow</h2><p>The system behaves like an AI research desk with a human approval counter.</p></div>
    <section class="flow">
      <div class="node green"><b>Zapier Input</b><span>Company + domain + ICP profile</span></div>
      <div class="node teal"><b>Researcher</b><span>Reads public sources and stores evidence</span></div>
      <div class="node gold"><b>Analyst</b><span>Scores fit and explains the why</span></div>
      <div class="node blue"><b>Writer</b><span>Drafts outreach, never sends</span></div>
      <div class="node red"><b>Slack Review</b><span>Approve, reject, or revise</span></div>
      <div class="node green"><b>CRM / BI</b><span>Approved records and reporting</span></div>
    </section>
    <section class="cards">
      <div class="card"><h3>Product Spec</h3><p><b>Input:</b> target company list and ICP profile.<br><b>Core:</b> CrewAI sequential agents, Tavily source extraction, validation harness, PostgreSQL state.<br><b>Output:</b> structured JSON, fit rationale, outreach draft, status history, and reviewable Slack card.</p></div>
      <div class="card"><h3>Why It Matters</h3><p>Teams lose hours researching accounts, judging fit, and writing first drafts. This system turns that manual loop into a governed workflow: faster research, clearer evidence, reusable ICP logic, and human approval before action.</p></div>
      <div class="card"><h3>Control Model</h3><p>The AI is not allowed to become an unsupervised sales bot. It uses public company data only, keeps source URLs, logs every run, flags uncertainty, and sends qualified drafts to human review before any CRM movement.</p></div>
    </section>
    <div class="footer"><span>Current proof: Render live run reached sent_to_review with source-grounded evidence and Slack review delivery.</span><span>Public company data only | Not HIPAA / not clinical / not auto-send</span></div>
  </main>
</body>
</html>
"""
    HTML_PATH.write_text(html, encoding="utf-8")


def main() -> None:
    build_pdf()
    build_html()
    print(f"wrote {PDF_PATH}")
    print(f"wrote {HTML_PATH}")


if __name__ == "__main__":
    main()
