#!/usr/bin/env python3
"""Generate agent-bar's SVG icon sets into src/agent_bar/assets/.

Two themes are produced (same file names in each):
  assets/sym/    monochrome, GNOME-style symbolic look
  assets/color/  colored variant

Per theme: off, idle, done, work-1..3 (spinner frames), attention,
attention-2..attention-9, attention-plus, blank (pulse off-frame),
plus per-CLI menu dots (dot-kimi, dot-claude, dot-codex).
"""

from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "src" / "agent_bar" / "assets"

SYM_GRAY = "#c8c8c8"
DIM_GRAY = "#8a8a8a"
BLUE = "#3584e4"
GREEN = "#2ec27e"
ORANGE = "#e66100"

CLI_COLORS = {"kimi": "#4f7cff", "claude": "#d97757", "codex": "#10a37f",
              "grok": "#111111"}

SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 22 22">{}</svg>\n'


def off(color: str) -> str:
    return SVG.format(
        f'<circle cx="11" cy="11" r="8" fill="none" stroke="{color}" stroke-width="2"/>')


def idle(color: str) -> str:
    return SVG.format(f'<circle cx="11" cy="11" r="6.5" fill="{color}"/>')


def done(color: str, check: str) -> str:
    return SVG.format(
        f'<circle cx="11" cy="11" r="9" fill="{color}"/>'
        f'<path d="M6.5 11.5 L9.5 14.5 L15.5 7.5" fill="none" stroke="{check}"'
        f' stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>')


def work_frame(color: str, angle: int) -> str:
    # arc ~3/4 of the circle, rotated per frame => spinner
    return SVG.format(
        f'<circle cx="11" cy="11" r="8" fill="none" stroke="{color}"'
        f' stroke-width="2.6" stroke-linecap="round" stroke-dasharray="37 13"'
        f' transform="rotate({angle} 11 11)"/>')


def attention(glyph: str) -> str:
    size = 12 if len(glyph) == 1 else 10
    return SVG.format(
        f'<circle cx="11" cy="11" r="9" fill="{ORANGE}"/>'
        f'<text x="11" y="15.5" font-family="sans-serif" font-size="{size}"'
        f' font-weight="bold" fill="#ffffff" text-anchor="middle">{glyph}</text>')


def blank() -> str:
    return SVG.format(f'<circle cx="11" cy="11" r="9" fill="{ORANGE}" fill-opacity="0.25"/>')


def dot(color: str) -> str:
    return SVG.format(f'<circle cx="11" cy="11" r="7" fill="{color}"/>')


def generate(theme: str, base: str, working: str, done_color: str, done_check: str) -> None:
    d = OUT / theme
    d.mkdir(parents=True, exist_ok=True)
    files = {
        "agent-bar-off": off(DIM_GRAY),
        "agent-bar-idle": idle(base),
        "agent-bar-done": done(done_color, done_check),
        "agent-bar-work-1": work_frame(working, 0),
        "agent-bar-work-2": work_frame(working, 120),
        "agent-bar-work-3": work_frame(working, 240),
        "agent-bar-attention": attention("?"),
        "agent-bar-blank": blank(),
        **{f"agent-bar-attention-{n}": attention(str(n)) for n in range(2, 10)},
        "agent-bar-attention-plus": attention("+"),
        **{f"dot-{cli}": dot(c) for cli, c in CLI_COLORS.items()},
    }
    for name, svg in files.items():
        (d / f"{name}.svg").write_text(svg)
    print(f"{theme}: {len(files)} icons -> {d}")


if __name__ == "__main__":
    generate("sym", base=SYM_GRAY, working=SYM_GRAY,
             done_color=SYM_GRAY, done_check="#3b3b3b")
    generate("color", base="#9a9a9a", working=BLUE,
             done_color=GREEN, done_check="#ffffff")
