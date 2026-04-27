#!/usr/bin/env python3
"""
PNL Reel Generator
Fetches cumulative PNL data from Firebase and creates an animated 9:16 reel.
Graph zooms out as more days are revealed. Floating semi-transparent symbols appear.
"""

import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from PIL import Image, ImageDraw, ImageFont
import subprocess
import os
import random
import io
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
URL   = "https://bhavpc-default-rtdb.asia-southeast1.firebasedatabase.app/pnlsudokutrader.json"
OUT   = "PNL_REEL/pnl_reel_all_fy.mp4"
AUDIO = os.path.expanduser("~/Desktop/bgms/Need for Speed 5： Porsche OST - Rezidue.mp3")
FPS = 30
FRAMES_PER_DAY = 4    # 395 days × 6 / 30 ≈ 79 s
LAST_N_DAYS = 1000000    # None = all days; set e.g. 5 to show only last 5 days
FY_TITLE_FILTER="FY 2025-2026"
REEL_TITLE="Trading Journey\nFY 2025-2026"

# Frame dimensions (9:16 portrait reel)
W, H = 1080, 1920

# Graph section in the frame
GRAPH_Y = 420          # y offset where graph is pasted (moved up — less header text)
GRAPH_W_PX = 1080
GRAPH_H_PX = 860       # taller graph

# Colors (RGB tuples for PIL)
BG      = (8,  8,  18)
GREEN   = (0,  230, 118)
RED     = (255, 23,  68)
GOLD    = (255, 215,  0)
WHITE   = (255, 255, 255)
GRAY    = (100, 100, 140)
DIM     = ( 30,  30,  55)
ACCENT  = ( 80, 100, 255)

# ── Helpers ───────────────────────────────────────────────────────────────────
def fmt_inr(val: float) -> str:
    sign = "+" if val >= 0 else "−"
    return f"{sign}₹{abs(val):,.0f}"

def ease_inout(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)

# ── Font loader ───────────────────────────────────────────────────────────────
_font_cache: dict = {}

def fnt(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]
    candidates = [
        ("/System/Library/Fonts/Helvetica.ttc",   1 if bold else 0),
        ("/System/Library/Fonts/HelveticaNeue.ttc", 1 if bold else 0),
        ("/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf", 0),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
         else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0),
    ]
    f = ImageFont.load_default()
    for path, idx in candidates:
        if os.path.exists(path):
            try:
                f = ImageFont.truetype(path, size, index=idx)
                break
            except Exception:
                try:
                    f = ImageFont.truetype(path, size)
                    break
                except Exception:
                    pass
    _font_cache[key] = f
    return f

# ── Data fetch & prep ─────────────────────────────────────────────────────────
def fetch() -> list:
    print("Fetching data from Firebase...", flush=True)
    r = requests.get(URL, timeout=30)
    r.raise_for_status()
    # Only titles that contain "FY" — avoids calendar-year duplicates
    fy_items = [item for item in r.json() if FY_TITLE_FILTER in item.get("title", "")]
    if not fy_items:
        raise ValueError("No FY entries found in Firebase data")
    print(f"  FY entries found: {[i['title'] for i in fy_items]}", flush=True)
    return fy_items

def prepare(fy_items: list) -> list:
    # Flatmap all pnl entries across every FY item, tag each with its FY label
    seen = {}  # dateMilli → day dict  (merge duplicates by summing ntpl + trades)
    for item in fy_items:
        fy_label = item.get("title", "")
        for e in item.get("pnl", []):
            ts     = e["dateMilli"]
            ntpl   = e.get("ntpl", 0.0)
            trades = [(t["symbol"], t["tradePNL"]) for t in e.get("trades", [])]
            expense = e.get("expense", 0.0)
            if ts in seen:
                seen[ts]["ntpl"]    += ntpl
                seen[ts]["expense"] += expense
                seen[ts]["trades"]  += trades
            else:
                seen[ts] = {
                    "date":    datetime.fromtimestamp(ts / 1000),
                    "ntpl":    ntpl,
                    "expense": expense,
                    "trades":  trades,
                    "ts":      ts,
                    "fy":      fy_label,
                }

    days = sorted(seen.values(), key=lambda d: d["ts"])

    cumulative = 0.0
    for d in days:
        cumulative += d["ntpl"]
        d["cum"] = cumulative
    return days

# ── Graph renderer (one per day) ──────────────────────────────────────────────
def render_graph(days_so_far: list, all_days: list = None) -> tuple[Image.Image, tuple[int, int]]:
    """
    Render cumulative PNL chart.
    Returns (PIL RGB Image at GRAPH_W_PX × GRAPH_H_PX, pixel-pos of last point).
    """
    n = len(days_so_far)
    fig, ax = plt.subplots(
        figsize=(GRAPH_W_PX / 100, GRAPH_H_PX / 100),
        dpi=100,
        facecolor="#08080A"
    )
    ax.set_facecolor("#08080A")

    if n == 0:
        plt.close(fig)
        blank = Image.new("RGB", (GRAPH_W_PX, GRAPH_H_PX), (8, 8, 18))
        return blank, (GRAPH_W_PX // 2, GRAPH_H_PX // 2)

    xs = list(range(n))
    ys = [d["cum"] for d in days_so_far]

    is_pos   = ys[-1] >= 0
    line_col = "#00E676" if is_pos else "#FF1744"

    # Zero reference
    ax.axhline(0, color="#252545", linewidth=1.5, linestyle="--", zorder=1)

    # FY boundary vertical lines — drawn behind everything
    if all_days:
        cur_fy = None
        for xi, d in enumerate(days_so_far):
            if d["fy"] != cur_fy:
                if cur_fy is not None and xi > 0:
                    ax.axvline(xi - 0.5, color="#3a3a60", linewidth=1.2,
                               linestyle=":", zorder=2, alpha=0.8)
                    ax.text(xi - 0.4, ax.get_ylim()[1] if ax.get_ylim()[1] != 1.0 else 0,
                            d["fy"], color="#5a5a90", fontsize=8, va="top",
                            rotation=90, alpha=0.7)
                cur_fy = d["fy"]

    # Fill above/below zero
    ax.fill_between(xs, ys, 0,
                    where=[y >= 0 for y in ys],
                    color="#00E676", alpha=0.13, zorder=3)
    ax.fill_between(xs, ys, 0,
                    where=[y < 0  for y in ys],
                    color="#FF1744", alpha=0.13, zorder=3)

    # Main line — no markers for many days (performance + clarity)
    ax.plot(xs, ys, color=line_col, linewidth=2.5, zorder=4,
            solid_capstyle="round", solid_joinstyle="round")

    # Small dots when few days
    if n <= 60:
        ax.scatter(xs, ys, color=line_col, s=18, zorder=5, alpha=0.55)

    # Highlighted last point
    ax.scatter([xs[-1]], [ys[-1]],
               color=line_col, s=220, zorder=6,
               edgecolors="white", linewidths=2.0)

    # Y-axis labels
    def fmt_y(v, _):
        a = abs(v)
        if a >= 100_000:
            return f"₹{v/100_000:.1f}L"
        if a >= 1_000:
            return f"₹{v/1_000:.0f}K"
        return f"₹{v:.0f}"

    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_y))
    ax.tick_params(colors="#666688", labelsize=11)
    for spine in ax.spines.values():
        spine.set_color("#1a1a30")

    # X-axis date labels (tight — no padding between days)
    if n > 1:
        step = max(1, n // 7)
        ticks = list(range(0, n, step))
        if (n - 1) not in ticks:
            ticks.append(n - 1)
        ax.set_xticks(ticks)
        ax.set_xticklabels(
            [days_so_far[i]["date"].strftime("%d %b") for i in ticks],
            rotation=30, ha="right", fontsize=10, color="#666688"
        )
    elif n == 1:
        ax.set_xticks([0])
        ax.set_xticklabels([days_so_far[0]["date"].strftime("%d %b")],
                           fontsize=10, color="#666688")

    # Tight x-range — zoom out naturally as n grows
    ax.set_xlim(-0.3, max(n - 0.7, 0.7))
    ax.margins(x=0)
    ax.grid(axis="y", color="#1a1a30", linewidth=0.8)

    # Deterministic layout so transform coords are stable
    fig.subplots_adjust(left=0.12, right=0.97, bottom=0.14, top=0.97)

    # Pixel coords of last point (for glow animation)
    try:
        dp = ax.transData.transform((xs[-1], ys[-1]))
        last_pt = (int(dp[0]), int(GRAPH_H_PX - dp[1]))
    except Exception:
        last_pt = (GRAPH_W_PX - 100, GRAPH_H_PX // 2)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, facecolor="#08080A")
    plt.close(fig)
    buf.seek(0)
    img = Image.open(buf).copy()
    buf.close()

    if img.size != (GRAPH_W_PX, GRAPH_H_PX):
        img = img.resize((GRAPH_W_PX, GRAPH_H_PX), Image.LANCZOS)

    return img.convert("RGB"), last_pt

# ── Symbol name cleaner ───────────────────────────────────────────────────────
def clean_symbol(sym: str) -> str:
    parts = sym.split()
    if not parts:
        return sym
    # "IO CE NIFTY 17Apr2025 23000" → "NIFTY 23000 CE 17Apr2025"
    if parts[0] == "IO" and len(parts) >= 3 and parts[1] in ("CE", "PE"):
        underlying, opt = parts[2], parts[1]
        date   = parts[3] if len(parts) > 3 else ""
        strike = parts[4] if len(parts) > 4 else ""
        tail   = parts[5:] if len(parts) > 5 else []
        return " ".join(filter(None, [underlying, strike, opt, date] + tail))
    # "CF NIFTY ..." → "NIFTY ..."
    if parts[0] == "CF":
        return " ".join(parts[1:])
    return sym

# ── Float symbol generator ─────────────────────────────────────────────────────
def get_floats(days: list, day_idx: int) -> list:
    """Return list of (symbol, pnl, x, y, alpha) for floating overlay."""
    # Fixed 5-day block: days 0-4 → block 0, days 5-9 → block 1, …
    block      = day_idx // 5
    block_start = block * 5
    block_end   = min(block_start + 5, len(days))
    rng  = random.Random(block * 7919 + 42)
    pool = []
    for d in days[block_start:block_end]:
        pool.extend(d["trades"])
    if not pool:
        return []

    graph_bot = GRAPH_Y + GRAPH_H_PX  # bottom of graph = 1280

    # ── Below-graph zones — row step = 85px to fit sf=35 + pf=30 without collision
    below = [
        (30,  graph_bot + 10,  490, 78),
        (560, graph_bot + 10,  490, 78),
        (30,  graph_bot + 95,  490, 78),
        (560, graph_bot + 95,  490, 78),
        (30,  graph_bot + 180, 490, 78),
        (560, graph_bot + 180, 490, 78),
        (30,  graph_bot + 265, 490, 78),
        (560, graph_bot + 265, 490, 78),
        (30,  graph_bot + 350, 490, 78),
        (560, graph_bot + 350, 490, 78),
        (30,  graph_bot + 435, 490, 78),
        (560, graph_bot + 435, 490, 78),
        (30,  graph_bot + 520, 490, 78),
        (560, graph_bot + 520, 490, 78),
    ]

    # ── Graph-overlay zones (lower alpha — ghost text over chart) ─────────────
    g0 = GRAPH_Y
    graph_overlays = [
        (30,   g0 + 60,  200, 180),   # left strip
        (850,  g0 + 60,  200, 180),   # right strip
        (30,   g0 + 280, 200, 180),
        (850,  g0 + 280, 200, 180),
        (30,   g0 + 500, 200, 180),
        (850,  g0 + 500, 200, 180),
        (30,   g0 + 680, 200, 140),
        (850,  g0 + 680, 200, 140),
        (250,  g0 + 20,  540, 40),    # top band of graph
        (250,  g0 + GRAPH_H_PX - 55, 540, 40),  # bottom band
    ]

    all_zones   = below + graph_overlays
    n           = min(len(all_zones), len(pool))
    chosen      = rng.sample(pool, n)

    result = []
    for i, (sym, pnl) in enumerate(chosen):
        zx, zy, zw, zh = all_zones[i]
        sx = rng.randint(zx, min(zx + max(zw - 230, 1), W - 230))
        sy = rng.randint(zy, zy + max(zh - 28, 1))
        alpha = rng.randint(68, 88) if i < len(below) else rng.randint(32, 52)
        result.append((sym, pnl, sx, sy, alpha))
    return result

# ── Intro title card ──────────────────────────────────────────────────────────
def render_intro(days: list, frame_num: int, total: int) -> Image.Image:
    """4-second intro: fade in (0.5s) → hold → fade out (0.5s)."""
    fade = int(total * 0.125)   # 0.5s each side

    if frame_num < fade:
        alpha_mult = ease_inout(frame_num / max(fade, 1))
    elif frame_num >= total - fade:
        alpha_mult = ease_inout((total - frame_num) / max(fade, 1))
    else:
        alpha_mult = 1.0

    # ── Compute trade stats ───────────────────────────────────────────────────
    all_pnls     = [pnl for d in days for _, pnl in d["trades"]]
    wins         = [p for p in all_pnls if p > 0]
    losses       = [p for p in all_pnls if p < 0]
    n_win        = len(wins)
    n_loss       = len(losses)
    avg_win      = sum(wins)   / n_win  if wins   else 0
    avg_loss     = sum(losses) / n_loss if losses else 0
    total_expense = sum(d.get("expense", 0) for d in days)

    final_cum   = days[-1]["cum"]
    cum_col     = GREEN if final_cum >= 0 else RED

    # Fonts
    f1       = fnt(72)
    f2       = fnt(45, bold=True)
    f3       = fnt(128, bold=True)
    f_lbl    = fnt(34)
    f_val    = fnt(52, bold=True)

    img      = Image.new("RGB", (W, H), BG)
    img_rgba = img.convert("RGBA")

    def draw_centered(lay, text, font, y, color):
        ld = ImageDraw.Draw(lay)
        r, g, b = color
        a = int(alpha_mult * 255)
        line_h = getattr(font, 'size', 45) + 8
        for i, line in enumerate(text.split("\n")):
            try:
                tw = int(ld.textlength(line, font=font))
            except Exception:
                tw = 500
            ld.text(((W - tw) // 2, y + i * line_h), line, font=font, fill=(r, g, b, a))

    def draw_at(lay, text, font, x, y, color, anchor="left"):
        ld = ImageDraw.Draw(lay)
        try:
            tw = int(ld.textlength(text, font=font))
        except Exception:
            tw = 300
        r, g, b = color
        a = int(alpha_mult * 255)
        ox = x - tw if anchor == "right" else x
        ld.text((ox, y), text, font=font, fill=(r, g, b, a))

    def divider(y, width=300):
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld  = ImageDraw.Draw(lay)
        ld.line([((W - width) // 2, y), ((W + width) // 2, y)],
                fill=(60, 60, 100, int(alpha_mult * 160)), width=1)
        return lay

    # ── Layout heights ────────────────────────────────────────────────────────
    n_title_lines = len(REEL_TITLE.split("\n"))
    h1  = 84
    h2  = 45 * n_title_lines + 8 * (n_title_lines - 1)   # font-45 lines + gaps
    h3  = 150
    gap = 40
    stats_lbl_h = 38
    stats_val_h = 60
    stats_gap   = 24
    # Total: h1+gap+h2+gap+h3 + gap*2 + divider + (lbl+val)*2 + stats_gap
    block_h = (h1 + gap + h2 + gap + h3 +
               gap * 2 +
               stats_lbl_h + stats_val_h + stats_gap +
               stats_lbl_h + stats_val_h)
    y = (H - block_h) // 2

    # Line 1: "Reality of Trading"
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_centered(lay, "Reality of Trading", f1, y, GRAY)
    img_rgba = Image.alpha_composite(img_rgba, lay)
    y += h1 + gap

    img_rgba = Image.alpha_composite(img_rgba, divider(y - 10, 320))

    # Line 2: REEL_TITLE
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_centered(lay, REEL_TITLE, f2, y, WHITE)
    img_rgba = Image.alpha_composite(img_rgba, lay)
    y += h2 + gap

    # Line 3: Final cumulative PNL
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_centered(lay, fmt_inr(final_cum), f3, y, cum_col)
    img_rgba = Image.alpha_composite(img_rgba, lay)
    y += h3 + gap * 2

    img_rgba = Image.alpha_composite(img_rgba, divider(y - 10, 900))

    # ── Stats: 2 columns × 2 rows ─────────────────────────────────────────────
    col_l = 120   # left column x
    col_r = W - 120  # right column x (right-aligned)

    # Row 1: Winning trades | Losing trades
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_at(lay, "Winning Trades", f_lbl, col_l, y, GRAY)
    draw_at(lay, "Losing Trades",  f_lbl, col_r, y, GRAY, anchor="right")
    img_rgba = Image.alpha_composite(img_rgba, lay)
    y += stats_lbl_h

    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_at(lay, str(n_win),  f_val, col_l, y, GREEN)
    draw_at(lay, str(n_loss), f_val, col_r, y, RED, anchor="right")
    img_rgba = Image.alpha_composite(img_rgba, lay)
    y += stats_val_h + stats_gap

    # Row 2: Avg win | Avg loss
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_at(lay, "Avg Win",  f_lbl, col_l, y, GRAY)
    draw_at(lay, "Avg Loss", f_lbl, col_r, y, GRAY, anchor="right")
    img_rgba = Image.alpha_composite(img_rgba, lay)
    y += stats_lbl_h

    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_at(lay, fmt_inr(avg_win),  f_val, col_l, y, GREEN)
    draw_at(lay, fmt_inr(avg_loss), f_val, col_r, y, RED, anchor="right")
    img_rgba = Image.alpha_composite(img_rgba, lay)
    y += stats_val_h + stats_gap

    img_rgba = Image.alpha_composite(img_rgba, divider(y - 10, 900))

    # Row 3: Expenses (centred — single value explaining the gap)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_centered(lay, "Brokerage & Taxes", f_lbl, y, GRAY)
    img_rgba = Image.alpha_composite(img_rgba, lay)
    y += stats_lbl_h

    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_centered(lay, f"−₹{total_expense:,.0f}", f_val, y, (180, 80, 80))
    img_rgba = Image.alpha_composite(img_rgba, lay)

    return img_rgba.convert("RGB")

# ── Frame composer ─────────────────────────────────────────────────────────────
def compose_frame(
    days: list,
    day_idx: int,
    frame_num: int,
    graph_img: Image.Image,
    last_pt: tuple[int, int],
    floats: list,
) -> Image.Image:

    t    = frame_num / max(FRAMES_PER_DAY - 1, 1)
    prog = ease_inout(t)

    prev_cum  = days[day_idx - 1]["cum"] if day_idx > 0 else 0.0
    curr_cum  = days[day_idx]["cum"]
    shown_cum = prev_cum + (curr_cum - prev_cum) * prog

    # ── Base background ───────────────────────────────────────────────────────
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Subtle top-to-bottom gradient vignette
    for yy in range(0, H, 3):
        lum = int(10 * (1 - yy / H))
        if lum > 0:
            draw.line([(0, yy), (W, yy)], fill=(lum, lum, lum + 3))

    # ── Graph ─────────────────────────────────────────────────────────────────
    img.paste(graph_img, (0, GRAPH_Y))

    # ── Glowing dot (animates in at last data point) ──────────────────────────
    gx = last_pt[0]
    gy = GRAPH_Y + last_pt[1]
    dot_alpha = int(255 * prog)
    dot_col   = GREEN if curr_cum >= 0 else RED

    glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    for r in range(24, 5, -4):
        a = int(dot_alpha * 0.28 * (1 - r / 26))
        gd.ellipse([gx - r, gy - r, gx + r, gy + r], fill=(*dot_col, a))
    gd.ellipse([gx - 7, gy - 7, gx + 7, gy + 7], fill=(*dot_col, dot_alpha))

    img_rgba = img.convert("RGBA")
    img_rgba = Image.alpha_composite(img_rgba, glow_layer)

    # ── Floating symbols ──────────────────────────────────────────────────────
    sym_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sym_layer)
    sf = fnt(35)
    pf = fnt(30)
    for sym, pnl, sx, sy, alpha in floats:
        short = clean_symbol(sym)[:22]
        col   = GREEN if pnl >= 0 else RED
        sd.text((sx, sy),      short,        font=sf, fill=(*col, alpha))
        sd.text((sx, sy + 42), fmt_inr(pnl), font=pf, fill=(200, 200, 210, max(alpha - 20, 15)))

    img_rgba = Image.alpha_composite(img_rgba, sym_layer)
    img = img_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

    # ── Title: REEL_TITLE (supports \n for two lines) ────────────────────────
    tf = fnt(27, bold=True)
    ty = 48
    for line in REEL_TITLE.split("\n"):
        try:
            tw = int(draw.textlength(line, font=tf))
        except Exception:
            tw = 600
        draw.text(((W - tw) // 2, ty), line, font=tf, fill=WHITE)
        ty += 31

    # ── Cumulative PNL (big animated number) ──────────────────────────────────
    cum_col = GREEN if shown_cum >= 0 else RED
    cum_str = fmt_inr(shown_cum)
    cf = fnt(92, bold=True)
    try:
        cw = int(draw.textlength(cum_str, font=cf))
    except Exception:
        cw = 600
    draw.text(((W - cw) // 2, 120), cum_str, font=cf, fill=cum_col)

    lf  = fnt(27)
    lbl = "Cumulative P&L"
    try:
        lw = int(draw.textlength(lbl, font=lf))
    except Exception:
        lw = 250
    draw.text(((W - lw) // 2, 228), lbl, font=lf, fill=GRAY)

    # ── Today PNL (left) + date (right) ──────────────────────────────────────
    sf3 = fnt(64, bold=True)
    today_ntpl = days[day_idx]["ntpl"]
    today_col  = GREEN if today_ntpl >= 0 else RED
    today_str  = fmt_inr(today_ntpl)
    draw.text((70, 265), today_str, font=sf3, fill=today_col)

    date_str = days[day_idx]["date"].strftime("%d %B %Y")
    df = fnt(56)
    try:
        dsw = int(draw.textlength(date_str, font=df))
    except Exception:
        dsw = 400
    draw.text((W - dsw - 70, 270), date_str, font=df, fill=(130, 130, 175))

    # ── Progress bar ──────────────────────────────────────────────────────────
    pb_x, pb_y, pb_w, pb_h = 60, 358, W - 120, 7
    draw.rectangle([pb_x, pb_y, pb_x + pb_w, pb_y + pb_h], fill=DIM)
    filled = int(pb_w * (day_idx + prog) / len(days))
    if filled > 1:
        draw.rectangle([pb_x, pb_y, pb_x + filled, pb_y + pb_h], fill=GOLD)

    # Divider
    draw.line([(60, 378), (W - 60, 378)], fill=(28, 28, 52), width=1)

    # (symbols below graph handled by floating layer)

    return img

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    fy_items = fetch()
    days     = prepare(fy_items)

    if LAST_N_DAYS is not None:
        days = days[-LAST_N_DAYS:]
        # Recompute cumulative from zero for the slice
        cum = 0.0
        for d in days:
            cum += d["ntpl"]
            d["cum"] = cum
        print(f"  Sliced to last {LAST_N_DAYS} days", flush=True)

    n = len(days)

    if n == 0:
        print("No PNL data found in any FY entry")
        return

    total_frames = n * FRAMES_PER_DAY
    duration_s   = total_frames / FPS

    print(f"  Total days  : {n}")
    print(f"  Span        : {days[0]['date'].strftime('%d %b %Y')} → {days[-1]['date'].strftime('%d %b %Y')}")
    print(f"  Final PNL   : {fmt_inr(days[-1]['cum'])}")
    print(f"  Total frames: {total_frames}  ({duration_s:.1f}s at {FPS}fps)")
    print(f"  Output      : {OUT}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-f",       "rawvideo",
        "-vcodec",  "rawvideo",
        "-s",       f"{W}x{H}",
        "-pix_fmt", "rgb24",
        "-r",       str(FPS),
        "-i",       "pipe:0",
        "-vcodec",  "libx264",
        "-pix_fmt", "yuv420p",
        "-preset",  "fast",
        "-crf",     "18",
        OUT,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    # ── 2-second intro title card ─────────────────────────────────────────────
    intro_total = FPS * 4   # 4 seconds
    for fn in range(intro_total):
        frm = render_intro(days, fn, intro_total)
        proc.stdin.write(frm.tobytes())

    frame_n = 0
    for i in range(n):
        # Pass all_days so graph can draw FY boundary markers
        graph_img, last_pt = render_graph(days[: i + 1], all_days=days)
        floats              = get_floats(days, i)

        for f in range(FRAMES_PER_DAY):
            frm = compose_frame(days, i, f, graph_img, last_pt, floats)
            proc.stdin.write(frm.tobytes())
            frame_n += 1

        pct = 100 * frame_n / total_frames
        print(f"\r  {pct:5.1f}%  day {i+1:3d}/{n}  {days[i]['fy']:<18}  cum={fmt_inr(days[i]['cum']):<18}",
              end="", flush=True)

    proc.stdin.close()
    proc.wait()
    print(f"\n\nVideo ready → {OUT}")

    # ── Mux audio ────────────────────────────────────────────────────────────
    if os.path.exists(AUDIO):
        out_audio = OUT.replace(".mp4", "_audio.mp4")
        # Get actual video duration for the fade-out point
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", OUT],
            capture_output=True, text=True
        )
        vid_dur = float(probe.stdout.strip())
        fade_start = max(0, vid_dur - 2.0)

        print(f"  Adding audio (fade-out at {fade_start:.1f}s)...", flush=True)
        subprocess.run([
            "ffmpeg", "-y",
            "-i", OUT,
            "-i", AUDIO,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-af", f"afade=t=out:st={fade_start:.2f}:d=2",
            "-shortest",
            out_audio,
        ], check=True)
        os.remove(OUT)   # remove silent version
        os.rename(out_audio, OUT)
        print(f"  Final (with audio) → {OUT}")
    else:
        print(f"  Audio file not found: {AUDIO}")

if __name__ == "__main__":
    main()
