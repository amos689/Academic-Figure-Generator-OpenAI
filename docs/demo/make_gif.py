"""Build the bilingual README animation from the saved public generation record.

Run from the repository root:
    uv run --project backend --locked python docs/demo/make_gif.py

Only presentation timing is composed here. This script never calls an AI service.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "examples/showcase/mae"
WIDTH, HEIGHT = 1280, 860
BG, BAR, FG = "#181A1E", "#24272C", "#F1F3F5"
MUTED, BLUE, GREEN = "#B0B7C1", "#91BCFF", "#8FDCB4"
INK, RULE = "#232832", "#DDE2E8"

COPY = {
    "en": {
        "steps": ["Paper", "Style", "Prompt", "Figure"],
        "titles": [
            "Start with a published research paper.",
            "Set the visual direction.",
            "Turn the source into a detailed drawing prompt.",
            "Render the reviewed prompt.",
        ],
        "result": "From the MAE paper to a pastel method figure",
        "file": "PAPER PDF  /  METHOD SUMMARY",
        "source_note": "Section 3: Approach  /  PDF pages 3-4  /  full section included",
        "labels": [
            "Style",
            "Profile",
            "Text model",
            "Reasoning",
            "Figure type",
            "Palette",
        ],
        "values": ["Pastel", "Quality", "", "", "Overall framework", "ML TopConf Deep"],
        "palette": "Blue features  /  coral masks  /  green reconstruction",
        "source_detail": "Visible-only encoder. Mask tokens added afterward.",
        "prompt_excerpt": "DRAWING PROMPT  /  EXCERPT",
        "prompt_note": (
            "{chars:,} characters  /  revision {revision}  /  "
            "{nodes} nodes + {edges} edges in FigureSpec"
        ),
        "prompt_done": "Prompt generated in {seconds:.2f} s",
        "image_done": "PNG generated in {seconds:.2f} s",
        "refine": "Refine the reference image.",
        "refine_done": "Image refinement completed in {seconds:.2f} s",
        "render_note": "Pastel  /  16:9  /  4K  /  maximum quality",
        "result_meta": "{width} x {height} PNG  /  Pastel  /  quality: {quality}",
    },
    "zh-CN": {
        "steps": ["真实论文", "风格设置", "绘图提示词", "生成成品"],
        "titles": [
            "从一篇已发表的论文开始。",
            "确定配图的视觉方向。",
            "将原文转化为详细的绘图提示词。",
            "根据审阅后的提示词生成图片。",
        ],
        "result": "从 MAE 论文到 Pastel 方法配图",
        "file": "论文 PDF  /  方法概要",
        "source_note": "第 3 节 Approach  /  PDF 第 3-4 页  /  完整读取该章节",
        "labels": ["配图风格", "生成档位", "文本模型", "推理强度", "图类型", "配色"],
        "values": ["Pastel", "Quality", "", "", "整体框架图", "ML TopConf Deep"],
        "palette": "蓝色特征  /  珊瑚色遮挡标记  /  绿色重建",
        "source_detail": "编码器只看可见块；遮挡标记在编码之后加入。",
        "prompt_excerpt": "英文绘图提示词  /  节选",
        "prompt_note": (
            "{chars:,} 个字符  /  修订 {revision}  /  FigureSpec 含 {nodes} 个节点、{edges} 条连接"
        ),
        "prompt_done": "提示词生成耗时 {seconds:.2f} 秒",
        "image_done": "PNG 生成耗时 {seconds:.2f} 秒",
        "refine": "使用参考图精修图像。",
        "refine_done": "图片精修耗时 {seconds:.2f} 秒",
        "render_note": "Pastel  /  16:9  /  4K  /  最高画质",
        "result_meta": "{width} x {height} PNG  /  Pastel  /  画质：{quality}",
    },
}


def find_font(override: str | None, candidates: list[str]) -> str:
    for name in [override, *candidates]:
        if name and Path(name).is_file():
            return name
    raise SystemExit("Font unavailable. Supply --font, --mono-font or --zh-font.")


def wrap(text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines = []
    for paragraph in text.splitlines():
        line = ""
        for word in paragraph.split(" "):
            candidate = f"{line} {word}" if line else word
            if line and font.getlength(candidate) > width:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
    return lines


class Demo:
    def __init__(self, lang: str, font: str, mono: str, record: dict) -> None:
        self.words = COPY[lang]
        self.record = record
        self.heading = ImageFont.truetype(font, 32)
        self.body = ImageFont.truetype(font, 24)
        self.small = ImageFont.truetype(font, 20)
        self.code = ImageFont.truetype(mono, 23)
        self.code_small = ImageFont.truetype(mono, 19)
        self.logo = Image.open(ROOT / "logo.png").convert("RGBA")
        self.logo.thumbnail((28, 28), Image.Resampling.LANCZOS)
        self.figure = Image.open(CASE / record["selected_image"]).convert("RGB")
        self.figure.thumbnail((1248, 702), Image.Resampling.LANCZOS)
        self.frames: list[Image.Image] = []
        self.durations: list[int] = []

    def text(
        self,
        image: Image.Image,
        xy: tuple[int, int],
        text: str,
        font: ImageFont.FreeTypeFont | None = None,
        fill: str = FG,
    ) -> None:
        font = font or self.body
        x, y = xy
        if x + font.getlength(text) > WIDTH - 24:
            raise ValueError(f"Text overflows the canvas: {text}")
        ImageDraw.Draw(image).text((x, y), text, font=font, fill=fill)

    def paragraph(
        self,
        image: Image.Image,
        text: str,
        y: int,
        *,
        font: ImageFont.FreeTypeFont | None = None,
        fill: str = FG,
        max_lines: int = 12,
    ) -> int:
        font = font or self.code
        lines = wrap(text, font, WIDTH - 112)
        if len(lines) > max_lines:
            raise ValueError("Text exceeds the reserved animation frame.")
        for line in lines:
            self.text(image, (56, y), line, font, fill)
            y += 37
        return y

    def base(self, stage: int, *, result: bool = False) -> Image.Image:
        image = Image.new("RGB", (WIDTH, HEIGHT), "white" if result else BG)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, WIDTH, 46), fill="#F4F6F8" if result else BAR)
        image.paste(self.logo, (20, 9), self.logo)
        self.text(
            image,
            (60, 10),
            "Academic Figure Generator",
            self.small,
            INK if result else FG,
        )
        self.text(
            image,
            (1048, 12),
            "MAE | CVPR 2022",
            self.code_small,
            "#66717F" if result else MUTED,
        )
        if result:
            self.text(image, (28, 64), self.words["result"], self.body, INK)
        else:
            self.text(image, (56, 82), f"0{stage + 1}", self.heading, BLUE)
            self.text(image, (126, 82), self.words["titles"][stage], self.heading)
        for index, label in enumerate(self.words["steps"]):
            x = 28 + index * 312
            active = index <= stage
            color = "#2E8969" if result else GREEN
            draw.rectangle((x, 806, x + 284, 809), fill=color if active else "#42464F")
            self.text(
                image,
                (x, 821),
                f"{index + 1:02d}  {label}",
                self.small,
                INK if result else FG if active else MUTED,
            )
        return image

    def add(self, image: Image.Image, ms: int) -> None:
        self.frames.append(image)
        self.durations.append(ms)

    def output_frame(self) -> Image.Image:
        image = self.base(3, result=True)
        image.paste(
            self.figure,
            ((WIDTH - self.figure.width) // 2, 101 + (702 - self.figure.height) // 2),
        )
        return image

    def source_frames(self, source: str) -> None:
        method = source.split("\nMethod\n", 1)[1].split("\n\n", 1)[0]
        excerpt = ". ".join(method.split(". ")[:5]) + "."
        base = self.base(0)
        self.text(base, (56, 170), self.words["file"], self.small, MUTED)
        self.text(base, (56, 207), self.record["source"]["filename"], self.code, BLUE)
        self.text(
            base, (56, 275), "Masked autoencoders | He et al., CVPR 2022", self.heading
        )
        for end in range(36, len(excerpt) + 36, 36):
            frame = base.copy()
            self.paragraph(frame, excerpt[:end], 338, max_lines=9)
            self.add(frame, 80)
        frame = self.frames[-1].copy()
        self.text(frame, (56, 658), self.words["source_detail"], self.body, GREEN)
        self.text(frame, (56, 721), self.words["source_note"], self.small, MUTED)
        self.add(frame, 2400)

    def style_frames(self) -> None:
        frame = self.base(1)
        prompt = self.record["prompt_generation"]
        values = list(self.words["values"])
        values[2], values[3] = prompt["model"], prompt["reasoning_effort"]
        for index, (label, value) in enumerate(
            zip(self.words["labels"], values, strict=True)
        ):
            y = 174 + index * 68
            self.text(frame, (56, y), label, self.body, MUTED)
            self.text(frame, (326, y), value, self.body, FG)
            self.add(frame.copy(), 210)
        draw = ImageDraw.Draw(frame)
        palette = self.record["image_generation"]["palette"]
        for index, key in enumerate(["primary", "secondary", "tertiary"]):
            x = 56 + index * 72
            draw.rounded_rectangle((x, 636, x + 52, 688), radius=6, fill=palette[key])
        self.text(frame, (296, 647), self.words["palette"], self.body)
        self.add(frame, 2600)

    def prompt_frames(self, prompt: str) -> None:
        pm = self.record["prompt_generation"]
        frame = self.base(2)
        self.text(frame, (56, 161), "client.responses.create(", self.code, BLUE)
        self.text(
            frame,
            (80, 204),
            f'model="{pm["model"]}", reasoning={{"effort": "{pm["reasoning_effort"]}"}}',
            self.code,
        )
        self.text(
            frame,
            (80, 246),
            'text={"format": {"type": "json_schema", ...}}, ...)',
            self.code,
            MUTED,
        )
        self.text(frame, (56, 321), self.words["prompt_excerpt"], self.small, GREEN)
        excerpt = prompt.split("=== OVERALL COMPOSITION ===\n", 1)[1].split("\n\n", 1)[
            0
        ]
        for end in range(56, len(excerpt) + 56, 56):
            shown = frame.copy()
            self.paragraph(shown, excerpt[:end], 365, font=self.code, max_lines=8)
            self.add(shown, 90)
        frame = self.frames[-1].copy()
        self.text(
            frame,
            (56, 691),
            self.words["prompt_note"].format(
                chars=pm["characters"],
                revision=pm["revision"],
                nodes=pm["nodes"],
                edges=pm["edges"],
            ),
            self.small,
            GREEN,
        )
        self.text(
            frame,
            (56, 742),
            self.words["prompt_done"].format(seconds=pm["duration_ms"] / 1000),
            self.small,
            MUTED,
        )
        self.add(frame, 3300)

    def render_frames(self) -> None:
        data = self.record["image_generation"]
        frame = self.base(3)
        self.text(frame, (56, 161), self.words["render_note"], self.body, GREEN)
        lines = [
            "client.images.generate(",
            f'    model="{data["model"]}",',
            "    prompt=final_prompt,",
            f'    size="{data["width"]}x{data["height"]}",',
            f'    quality="{data["quality"]}",',
            '    output_format="png",',
            "    n=1,",
            ")",
        ]
        for index, line in enumerate(lines):
            self.text(
                frame,
                (56, 236 + 44 * index),
                line,
                self.code,
                BLUE if index == 0 else FG,
            )
            self.add(frame.copy(), 110)
        self.add(frame.copy(), 800)
        self.text(
            frame,
            (56, 658),
            self.words["image_done"].format(seconds=data["duration_ms"] / 1000),
            self.body,
            GREEN,
        )
        self.text(
            frame,
            (56, 713),
            self.words["result_meta"].format(**data),
            self.small,
            MUTED,
        )
        self.add(frame, 2200)

    def refinement_frame(self, data: dict) -> None:
        frame = self.base(3)
        self.text(frame, (56, 161), self.words["refine"], self.body, GREEN)
        lines = [
            "client.images.edit(",
            f'    model="{data["model"]}",',
            f'    image=open("{data["reference_file"]}", "rb"),',
            "    prompt=edit_prompt,",
            f'    size="{data["width"]}x{data["height"]}",',
            f'    quality="{data["quality"]}",',
            '    output_format="png", n=1,',
            ")",
        ]
        if data["mask_used"]:
            lines[3] = '    prompt=edit_prompt, mask=open("connector-mask.png", "rb"),'
        for index, line in enumerate(lines):
            self.text(
                frame,
                (56, 236 + 44 * index),
                line,
                self.code,
                BLUE if not index else FG,
            )
        self.text(
            frame,
            (56, 658),
            self.words["refine_done"].format(seconds=data["duration_ms"] / 1000),
            self.body,
            GREEN,
        )
        self.add(frame, 2400)

    def build(self, output: Path, source: str, prompt: str) -> None:
        self.add(self.output_frame(), 1200)
        self.source_frames(source)
        self.style_frames()
        self.prompt_frames(prompt)
        self.render_frames()
        self.refinement_frame(self.record["image_refinement"])
        self.refinement_frame(self.record["image_correction"])
        final = self.output_frame()
        self.add(final, 10500)

        # One shared palette prevents color flicker between adjacent frames.
        palette_source = Image.new("RGB", (WIDTH, HEIGHT * 2))
        palette_source.paste(final)
        palette_source.paste(self.base(3), (0, HEIGHT))
        palette = palette_source.quantize(colors=240, method=Image.Quantize.MEDIANCUT)
        reserved = [BG, BAR, FG, MUTED, BLUE, GREEN, INK, RULE, "#FFFFFF"]
        reserved.extend(
            self.record["image_generation"]["palette"][key]
            for key in ["primary", "secondary", "tertiary"]
        )
        colors = palette.getpalette()[:720]
        colors.extend(
            channel for color in reserved for channel in ImageColor.getrgb(color)
        )
        palette.putpalette(colors + [0] * (768 - len(colors)))
        frames = [
            frame.quantize(palette=palette, dither=Image.Dither.NONE)
            for frame in self.frames
        ]
        temporary = output.with_suffix(".tmp.gif")
        frames[0].save(
            temporary,
            save_all=True,
            append_images=frames[1:],
            duration=self.durations,
            loop=0,
            optimize=True,
            disposal=1,
        )
        temporary.replace(output)
        print(
            f"{output.relative_to(ROOT)}: {len(frames)} frames, "
            f"{sum(self.durations) / 1000:.2f} s, {output.stat().st_size / 1024:.0f} KiB"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lang", choices=["en", "zh-CN", "all"], default="all")
    parser.add_argument("--font")
    parser.add_argument("--mono-font")
    parser.add_argument("--zh-font")
    args = parser.parse_args()
    sans = find_font(
        args.font,
        [
            "/System/Library/Fonts/Avenir Next.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
        ],
    )
    mono = find_font(
        args.mono_font,
        [
            "/System/Library/Fonts/Menlo.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "C:/Windows/Fonts/consola.ttf",
        ],
    )
    langs = ["en", "zh-CN"] if args.lang == "all" else [args.lang]
    record = json.loads((CASE / "manifest.json").read_text(encoding="utf-8"))
    source = (CASE / record["source"]["summary_file"]).read_text(encoding="utf-8")
    prompt = (CASE / record["prompt_generation"]["file"]).read_text(encoding="utf-8")
    for lang in langs:
        font = (
            sans
            if lang == "en"
            else find_font(
                args.zh_font,
                [
                    "/System/Library/Fonts/Hiragino Sans GB.ttc",
                    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                    "C:/Windows/Fonts/msyh.ttc",
                ],
            )
        )
        Demo(lang, font, mono, record).build(
            Path(__file__).with_name("demo.gif" if lang == "en" else "demo.zh-CN.gif"),
            source,
            prompt,
        )


if __name__ == "__main__":
    main()
