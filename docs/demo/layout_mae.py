"""Reflow the saved MAE artwork onto a wider canvas, with exact connector ports.

Run from the repository root:
    uv run --project backend --locked python docs/demo/layout_mae.py

The photographic patches come from the saved Image API outputs. Operators,
labels, grids, and connections are laid out locally; no API call is made.
"""

from __future__ import annotations

import argparse
import math
from itertools import pairwise
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "examples/showcase/mae"
SIZE = (4800, 1920)
VISIBLE = (3, 6, 12, 13)
INK, LINE = "#142E50", "#48647E"
BLUE, BLUE_EDGE = "#E5EFFC", "#70A3E6"
CORAL, CORAL_EDGE = "#FFF0E7", "#EC9878"
GREEN, GREEN_EDGE = "#EAF6EF", "#80BA96"
CY = 800
PORTS = {
    "input": (80, 497, 618, 1103),
    "sampling": (686, 690, 986, 910),
    "visible": (1054, 497, 1592, 1103),
    "projection": (1920, 700, 2230, 900),
    "encoder": (2300, 460, 2490, 1140),
    "merge": (2810, 725, 3060, 875),
    "mask": (2880, 401, 2990, 501),
    "tokens": (3150, 601, 3470, 999),
    "decoder": (3640, 640, 3820, 960),
    "head": (3890, 700, 4100, 900),
    "prediction": (4190, 497, 4728, 1103),
}
DIRECT_EDGES = (
    ("input", "sampling"),
    ("sampling", "visible"),
    ("projection", "encoder"),
    ("merge", "tokens"),
    ("tokens", "decoder"),
    ("decoder", "head"),
    ("head", "prediction"),
)


def fonts(override: str | None = None) -> tuple[str, int, int]:
    candidates = [
        override,
        "/System/Library/Fonts/Avenir Next.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate, 5 if Path(candidate).name == "Avenir Next.ttc" else 0, 0
    raise ValueError("Supply --font with a TrueType/OpenType sans-serif font.")


def patches(image: Image.Image, xs: list[int], ys: list[int]) -> list[Image.Image]:
    return [
        image.crop((xs[col] + 4, ys[row] + 4, xs[col + 1] - 4, ys[row + 1] - 4))
        for row in range(4)
        for col in range(4)
    ]


class Layout:
    def __init__(self, font: str | None = None):
        self.image = Image.new("RGB", SIZE, "white")
        self.draw = ImageDraw.Draw(self.image)
        self.font_path, self.regular, self.bold = fonts(font)
        self.text_bounds: list[tuple[int, int, int, int]] = []
        self.connector_segments = []

    def text(self, xy, text, size=34, *, bold=False, anchor="mm", fill=INK):
        font = ImageFont.truetype(
            self.font_path, size, index=self.bold if bold else self.regular
        )
        lines = text.split("\n")
        y = xy[1] - (len(lines) - 1) * size * 0.64
        for line in lines:
            box = self.draw.textbbox((xy[0], y), line, font=font, anchor=anchor)
            if box[0] < 0 or box[1] < 0 or box[2] > SIZE[0] or box[3] > SIZE[1]:
                raise ValueError(f"Text outside canvas: {line}")
            self.text_bounds.append(box)
            self.draw.text((xy[0], y), line, font=font, anchor=anchor, fill=fill)
            y += size * 1.28

    def arrow(self, points, *, dashed=False):
        # The final vertex is the destination port, not an offset near the node.
        for a, b in pairwise(points):
            self.connector_segments.append((a, b))
            length = math.dist(a, b)
            if dashed:
                for offset in range(0, math.ceil(length), 24):
                    start, end = offset / length, min(offset + 13, length) / length
                    self.draw.line(
                        [
                            tuple(a[i] + (b[i] - a[i]) * t for i in (0, 1))
                            for t in (start, end)
                        ],
                        fill=LINE,
                        width=5,
                    )
            else:
                self.draw.line([a, b], fill=LINE, width=5)
        a, b = points[-2:]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length
        self.draw.polygon(
            [
                b,
                (b[0] - ux * 23 + uy * 12, b[1] - uy * 23 - ux * 12),
                (b[0] - ux * 23 - uy * 12, b[1] - uy * 23 + ux * 12),
            ],
            fill=LINE,
        )

    def line(self, points):
        self.connector_segments.extend(pairwise(points))
        self.draw.line(points, fill=LINE, width=5)

    def validate_clearance(self):
        for a, b in self.connector_segments:
            left, right = sorted((a[0], b[0]))
            top, bottom = sorted((a[1], b[1]))
            for x0, y0, x1, y1 in self.text_bounds:
                if (
                    x0 < right + 11
                    and x1 > left - 11
                    and y0 < bottom + 11
                    and y1 > top - 11
                ):
                    raise ValueError(
                        f"Text {(x0, y0, x1, y1)} is too close to a connector {a, b}."
                    )

    def box(self, bounds, text, *, fill=BLUE, outline=BLUE_EDGE, size=34, padding=12):
        center = ((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2)
        lines = text.split("\n")
        while size >= 24:
            font = ImageFont.truetype(self.font_path, size, index=self.regular)
            first_y = center[1] - (len(lines) - 1) * size * 0.64
            boxes = [
                self.draw.textbbox(
                    (center[0], first_y + i * size * 1.28), line, font=font, anchor="mm"
                )
                for i, line in enumerate(lines)
            ]
            if all(
                b[0] >= bounds[0] + padding
                and b[2] <= bounds[2] - padding
                and b[1] >= bounds[1] + padding
                and b[3] <= bounds[3] - padding
                for b in boxes
            ):
                break
            size -= 1
        else:
            raise ValueError(f"Text exceeds its operator: {text}")
        self.draw.rounded_rectangle(
            bounds, radius=12, fill=fill, outline=outline, width=3
        )
        self.text(center, text, size)

    def indexed_label(self, xy, label, index):
        main = ImageFont.truetype(self.font_path, 34, index=self.bold)
        sub = ImageFont.truetype(self.font_path, 23, index=self.bold)
        x = xy[0] - (main.getlength(label) + sub.getlength(index)) / 2
        self.text((x, xy[1]), label, 34, bold=True, anchor="lm")
        self.text(
            (x + main.getlength(label), xy[1] + 11), index, 23, bold=True, anchor="lm"
        )

    def patch(self, picture, bounds, index=None):
        x, y, right, bottom = bounds
        crop = picture.resize((right - x, bottom - y), Image.Resampling.LANCZOS)
        self.image.paste(crop, (x, y))
        self.draw.rectangle(bounds, outline="#BCD0E1", width=3)
        if index is not None:
            # Redraw the generated patch indices at consistent positions, including missing labels.
            self.draw.rectangle((x + 5, y + 5, x + 58, y + 57), fill="white")
            self.text((x + 29, y + 30), str(index), 32)

    def grid(self, pictures, bounds, *, visible=None):
        x, y, right, bottom = bounds
        for index, picture in enumerate(pictures, 1):
            row, col = divmod(index - 1, 4)
            cell = (
                round(x + (right - x) * col / 4),
                round(y + (bottom - y) * row / 4),
                round(x + (right - x) * (col + 1) / 4),
                round(y + (bottom - y) * (row + 1) / 4),
            )
            if visible is None or index in visible:
                self.patch(picture, cell, index)
            else:
                self.draw.rectangle(cell, fill="white", outline="#BCD0E1", width=3)
                self.text((cell[0] + 29, cell[1] + 30), str(index), 32)

    def build(self, refined: Image.Image, corrected: Image.Image) -> Image.Image:
        if refined.size != (3840, 2160) or corrected.size != (3840, 2160):
            raise ValueError(
                "This composition requires the recorded 3840 x 2160 source artwork."
            )
        original = patches(
            corrected, [41, 173, 308, 445, 579], [519, 661, 813, 983, 1125]
        )
        predicted = patches(
            refined, [3298, 3427, 3560, 3690, 3818], [520, 663, 815, 984, 1125]
        )
        self.text(
            (80, 95),
            "Masked Autoencoders Are Scalable Vision Learners",
            76,
            bold=True,
            anchor="lm",
        )
        self.text(
            (80, 197),
            "Asymmetric MAE pre-training computation (Section 3)",
            44,
            anchor="lm",
            fill=LINE,
        )
        self.text((4720, 100), "He et al. | CVPR 2022", 34, anchor="rm", fill=LINE)

        self.grid(original, PORTS["input"])
        self.grid(original, PORTS["visible"], visible=VISIBLE)
        self.grid(predicted, PORTS["prediction"])
        self.text((349, 419), "Input image x\n4 x 4 schematic grid", 38, bold=True)
        self.text((1323, 445), "Visible patches (4 of 16)", 42, bold=True)
        self.text((4459, 445), "Schematic prediction", 42, bold=True)
        self.box(
            PORTS["sampling"],
            "Uniform random\nsampling\nwithout\nreplacement",
            size=30,
            padding=24,
        )
        self.text((836, 640), "75% masking", 37, bold=True)
        self.box(
            PORTS["projection"],
            "Linear projection\n+ encoder\npositions",
            size=31,
            padding=24,
        )
        self.text((1781, 395), "Gather visible\npatches", 37, bold=True)
        self.text((2635, 413), "Encoded visible\nfeatures", 37, bold=True)
        self.box(PORTS["merge"], "Append M\nInverse shuffle", size=34)
        self.text((2935, 315), "Shared learned\nmask vector", 37, bold=True)
        self.box(PORTS["mask"], "M", fill=CORAL, outline=CORAL_EDGE, size=48)
        self.arrow([(2935, 501), (2935, 725)])
        self.text((2965, 593), "Repeat x12", 27, anchor="lm", fill=LINE)

        self.draw.polygon(
            [(2300, 460), (2490, 535), (2490, 1065), (2300, 1140)],
            fill="#C7DEF8",
            outline=BLUE_EDGE,
            width=4,
        )
        self.text((2395, CY), "ViT\nencoder", 40, bold=True)
        self.draw.polygon(
            [(3640, 640), (3820, 710), (3820, 890), (3640, 960)],
            fill="#D9EFE2",
            outline=GREEN_EDGE,
            width=4,
        )
        self.text((3730, CY), "Small\ndecoder", 30, bold=True)
        self.box(PORTS["head"], "Linear to\npatch pixels\n+ reshape", size=32)

        self.line([(1660, 548), (1660, 1052)])
        self.line([(1890, 548), (1890, 1052)])
        self.line([(2748, 548), (2748, 1052)])
        self.line([(1592, CY), (1660, CY)])
        for index, y in zip(VISIBLE, (548, 716, 884, 1052), strict=True):
            self.patch(original[index - 1], (1715, y - 76, 1848, y + 76), index)
            self.arrow([(1660, y), (1715, y)])
            self.line([(1848, y), (1890, y)])
            self.arrow([(2490, y), (2585, y)])
            self.box((2585, y - 55, 2685, y + 55), "z" + str(index), size=40)
            self.line([(2685, y), (2748, y)])
        self.arrow([(1890, CY), (PORTS["projection"][0], CY)])
        self.arrow([(2748, CY), (2810, CY)])

        self.text((3310, 513), "Full decoder input\n16 tokens", 37, bold=True)
        for index in range(1, 17):
            row, col = divmod(index - 1, 4)
            x, y = 3150 + col * 82, 601 + row * 102
            visible = index in VISIBLE
            self.box(
                (x, y, x + 74, y + 92),
                "z" + str(index) if visible else "M",
                fill=BLUE if visible else CORAL,
                outline=BLUE_EDGE if visible else CORAL_EDGE,
                size=30,
                padding=10,
            )
        self.text((3565, 707), "+ decoder\npositions\n(all tokens)", 28, fill=LINE)
        for source, target in DIRECT_EDGES:
            self.arrow([(PORTS[source][2], CY), (PORTS[target][0], CY)])

        loss = (2606, 1380, 4728, 1840)
        self.draw.rounded_rectangle(
            loss, radius=20, fill="#F2FAF5", outline="#BCDCC9", width=3
        )
        self.text(
            (2650, 1435), "Masked-pixel reconstruction loss", 40, bold=True, anchor="lm"
        )
        self.text(
            (3400, 1435), "Computed only on masked patches", 32, anchor="lm", fill=LINE
        )
        self.indexed_label((2780, 1510), "Target x", "10")
        self.indexed_label((3070, 1510), "Prediction \u0177", "10")
        self.patch(original[9], (2670, 1550, 2890, 1800))
        self.patch(predicted[9], (2960, 1550, 3180, 1800))
        self.draw.rounded_rectangle(
            (3330, 1570, 4022, 1784),
            radius=20,
            fill="#F2FAF5",
            outline="#68B78A",
            width=5,
        )
        formula = refined.crop((2560, 1720, 3170, 1886))
        self.image.paste(formula, (3371, 1594))
        self.arrow([(3205, 1677), (3330, 1677)])
        self.arrow([(4022, 1677), (4120, 1677)])
        self.text((4420, 1677), "All 12 masked patches;\nno visible-patch loss", 37)
        self.arrow([(349, 1103), (349, 1685), (2606, 1685)])
        self.text((420, 1630), "Original target x", 37, anchor="lm", fill=LINE)
        self.arrow([(836, 910), (836, 1280), (2880, 1280), (2880, 1380)], dashed=True)
        self.text((885, 1240), "Masked indices \u03a9", 36, anchor="lm", fill=LINE)
        self.arrow([(4459, 1103), (4459, 1380)])
        self.validate_clearance()
        return self.image


def render(case: Path = CASE, font: str | None = None) -> Image.Image:
    with (
        Image.open(case / "refined.png") as refined,
        Image.open(case / "repair-base.png") as corrected,
    ):
        return Layout(font).build(refined.convert("RGB"), corrected.convert("RGB"))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--font")
    parser.add_argument("--output", type=Path, default=CASE / "figure.png")
    args = parser.parse_args()
    render(font=args.font).save(args.output)
    print(f"Saved {args.output.name}: {SIZE[0]} x {SIZE[1]}")


if __name__ == "__main__":
    main()
