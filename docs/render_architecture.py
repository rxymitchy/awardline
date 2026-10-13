"""Draw the Awardline architecture diagram as a PNG for the submission form."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).with_name("architecture.png")
W, H = 2200, 1480
BG = "#F6F4EF"
INK = "#1C1917"
MUTED = "#57534E"
LINE = "#44403C"

FONT = "C:/Windows/Fonts/segoeui.ttf"
FONT_B = "C:/Windows/Fonts/segoeuib.ttf"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def wrap(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        current = ""
        for word in words:
            trial = word if not current else f"{current} {word}"
            if draw.textlength(trial, font=face) <= width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def box(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    title: str,
    body: str,
    fill: str,
    accent: str,
) -> None:
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=18, fill=fill, outline=accent, width=3)
    draw.rectangle((x0, y0, x0 + 10, y1), fill=accent)
    title_face = font(26, bold=True)
    body_face = font(20)
    draw.text((x0 + 28, y0 + 16), title, font=title_face, fill=INK)
    y = y0 + 58
    for line in wrap(draw, body, body_face, x1 - x0 - 48):
        draw.text((x0 + 28, y), line, font=body_face, fill=INK)
        y += 28


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int]) -> None:
    draw.line((start, end), fill=LINE, width=4)
    _head(draw, start, end)


def route(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]]) -> None:
    draw.line(points, fill=LINE, width=4)
    _head(draw, points[-2], points[-1])


def _head(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int]) -> None:
    ex, ey = end
    sx, sy = start
    if abs(ex - sx) >= abs(ey - sy):
        sign = 1 if ex > sx else -1
        head = [(ex, ey), (ex - 16 * sign, ey - 8), (ex - 16 * sign, ey + 8)]
    else:
        sign = 1 if ey > sy else -1
        head = [(ex, ey), (ex - 8, ey - 16 * sign), (ex + 8, ey - 16 * sign)]
    draw.polygon(head, fill=LINE)


def main() -> None:
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    draw.text((64, 36), "Awardline architecture", font=font(42, bold=True), fill=INK)
    draw.text(
        (64, 92),
        "One local agent. Two MCP servers. The officer approves before anything is filed.",
        font=font(22),
        fill=MUTED,
    )

    box(
        draw,
        (64, 170, 430, 360),
        "Human",
        "Officer brings one quote:\nbuyer, purchase, amount.",
        "#FFEDD5",
        "#C2410C",
    )
    box(
        draw,
        (520, 170, 980, 360),
        "Agent",
        "LangGraph loop.\nplan, then tools, then plan.\nStops at 8 steps.",
        "#DBEAFE",
        "#1D4ED8",
    )
    box(
        draw,
        (1070, 170, 1560, 360),
        "LLM",
        "Qwen 2.5 3B via Ollama.\nLocal chat API.\nChooses the next tool.",
        "#FEF3C7",
        "#B45309",
    )
    box(
        draw,
        (1650, 170, 2136, 360),
        "MCP client",
        "Stdio session inside\nthe tools node.\nCalls one tool, returns JSON.",
        "#CCFBF1",
        "#0F766E",
    )

    arrow(draw, (430, 265), (520, 265))
    arrow(draw, (980, 265), (1070, 265))
    arrow(draw, (1560, 265), (1650, 265))

    box(
        draw,
        (64, 470, 1040, 860),
        "MCP server we wrote  ·  Awardline",
        "stdio  ·  python -m awardline.server\n\n"
        "search_awards            reads the PPIP snapshot\n"
        "flag_price_outlier       writes runtime/flags\n"
        "draft_committee_note     writes runtime/drafts\n"
        "file_committee_note      files only after approval\n\n"
        "No MCP resources. Tools only.",
        "#E0E7FF",
        "#312E81",
    )
    box(
        draw,
        (1160, 470, 2136, 760),
        "MCP server we did not write",
        "@modelcontextprotocol/server-filesystem\n\n"
        "Tool: write_file\n"
        "Allowed directory: filings/ only\n"
        "Used because the allow-list is its job.",
        "#ECFCCB",
        "#3F6212",
    )
    box(
        draw,
        (1160, 800, 2136, 980),
        "Filed note",
        "filings/<note_id>.md\nThe committee folder. Written only through the filesystem server.",
        "#F5F5F4",
        "#44403C",
    )

    route(draw, [(1760, 360), (1760, 420), (552, 420), (552, 470)])
    arrow(draw, (1040, 700), (1160, 700))
    draw.text((1052, 664), "after approval", font=font(18), fill=MUTED)
    arrow(draw, (1648, 760), (1648, 800))

    box(
        draw,
        (64, 920, 430, 1140),
        "Data source",
        "data/awards.json\n4,956 PPIP awards.\nDownloaded once from\ntenders.go.ke.",
        "#F5F5F4",
        "#44403C",
    )
    box(
        draw,
        (470, 920, 1040, 1140),
        "Written by our tools",
        "runtime/flags\nruntime/drafts\nlogs/tool_calls.jsonl",
        "#F5F5F4",
        "#44403C",
    )
    box(
        draw,
        (64, 1190, 1040, 1400),
        "Human in the loop",
        "python -m awardline approve --officer \"Name\"\n"
        "Writes runtime/approvals. Actor is human.\n"
        "This command is not a tool the model can call.\n"
        "file_committee_note refuses until decision is approve.",
        "#FFE4E6",
        "#9F1239",
    )

    arrow(draw, (250, 860), (250, 920))
    arrow(draw, (750, 860), (750, 920))

    draw.text((1160, 1040), "Data flow", font=font(26, bold=True), fill=INK)
    steps = [
        "1. Officer states the quote.",
        "2. LangGraph asks Qwen for the next tool.",
        "3. The MCP client calls the Awardline server.",
        "4. Search reads the snapshot. Flag and draft write files.",
        "5. The JSON result returns to Qwen. Errors come back too.",
        "6. The model stops when the note exists. It does not award.",
        "7. A named officer approves.",
        "8. file_committee_note calls the filesystem server, which writes filings/.",
    ]
    y = 1088
    face = font(20)
    for step in steps:
        draw.text((1160, y), step, font=face, fill=INK)
        y += 36

    image.save(OUT, "PNG")
    print(OUT)


if __name__ == "__main__":
    main()
