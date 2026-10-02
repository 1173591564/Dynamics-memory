#!/usr/bin/env python3
"""把 animations/pelican-bike.html 在指定相位“定格”成静态图，用于肉眼检查姿态。

浏览器跑不起来时，这是唯一能看到画面的办法：脚本按当前相位把 CSS 动画转换成
显式的 transform 属性（车轮旋转、腿部 IK 关键帧、身体起伏、背景视差位移），
再用 resvg 渲染成 PNG。

    python3 scripts/snapshot_pelican_bike.py                          # 4 相位拼图
    python3 scripts/snapshot_pelican_bike.py --grid 2 4 --scale 0.45
    python3 scripts/snapshot_pelican_bike.py --phases 0.5 --crop 380 300 420 300
    python3 scripts/snapshot_pelican_bike.py --anim /tmp/frames 8      # 导出 8 帧

依赖：pip install resvg-py pillow
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_pelican_bike import Markup, Leg, bob, N_KEY  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
HTML_PATH = REPO / "animations" / "pelican-bike.html"
BASE_DUR = 1.45          # 一个踩踏周期的秒数（--dur = 1s 时）

# 各视差层的时长（秒），与 HTML 里的 calc(var(--dur) * k) 对应
PARALLAX = {
    "gravel": 5.33, "roadMarks": 5.33, "grassTufts": 16.0,
    "hillsNear": 53.3, "hillsBack": 85.3, "birds": 34.0, "speedLines": 3.55,
}
CLOUDS = (("cloud1", 40.0, 0.0), ("cloud2", 58.0, 22.0), ("cloud3", 48.0, 35.0))


def smoothstep(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def env(f: float) -> float:
    """0→1→0 的往复包络，对应 0%/50%/100% 的关键帧。"""
    return smoothstep(2 * f) if f <= 0.5 else smoothstep(2 * (1 - f))


def keyframe_value(vals: list[float], f: float) -> float:
    pos = f * N_KEY
    lo = int(pos) % N_KEY
    hi = (lo + 1) % len(vals)
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - int(pos))


def parse_keyframes(css: str) -> dict[str, list[float]]:
    out = {}
    for name in ("pedalThigh", "pedalShin"):
        body = re.search(rf"@keyframes {name} \{{(.*?)\n  \}}", css, flags=re.S).group(1)
        out[name] = [float(v) for v in re.findall(r"rotate\((-?[\d.]+)deg\)", body)]
    return out


def set_attr(tag: str, attr: str, value: str) -> str:
    """在标签里写入/覆盖属性。"""
    if re.search(rf'\s{attr}="', tag):
        return re.sub(rf'{attr}="[^"]*"', f'{attr}="{value}"', tag, count=1)
    return tag[:-2] + f' {attr}="{value}"/>' if tag.endswith("/>") else tag[:-1] + f' {attr}="{value}">'


def group_span(svg: str, gid: str) -> tuple[int, int]:
    """返回 <g id="gid">…</g> 的字符区间（含首尾）。"""
    start = svg.index(f'<g id="{gid}"')
    depth = 0
    for tok in re.finditer(r"<g\b|</g>", svg[start:]):
        depth += 1 if tok.group(0) == "<g" else -1
        if depth == 0:
            return start, start + tok.end()
    raise AssertionError(f"#{gid} 标签不闭合")


def pose(src: str, f: float, with_background: bool = True) -> str:
    m = Markup(src)
    geo = m.parse()
    kf = parse_keyframes(m.css)
    svg = m.svg

    # 0) CSS 变量落地（resvg 不认 var()），并剥掉 <style>（动画已展开成属性）
    root = re.search(r":root\s*\{(.*?)\}", m.css, flags=re.S).group(1)
    for name, val in re.findall(r"(--[\w-]+):\s*([^;]+);", root):
        svg = svg.replace(f"var({name})", val.strip())
    svg = re.sub(r"<style>.*?</style>", "", svg, flags=re.S)

    def add_transform(pattern: str, value: str) -> None:
        nonlocal svg
        mt = re.search(pattern, svg)
        if not mt:
            raise AssertionError(f"定位不到元素: {pattern}")
        tag = re.sub(r'\sstyle="[^"]*transform-[^"]*"', "", mt.group(0))
        svg = svg[:mt.start()] + set_attr(tag, "transform", value) + svg[mt.end():]

    # 1) 车轮：在各自的 translate 之后按本地原点旋转
    for cx, cy in geo["wheel_centers"]:
        add_transform(rf'<g transform="translate\({cx:g} {cy:g}\)">\s*<g class="wheel">',
                      f"translate({cx:g} {cy:g})")   # 先去掉内层，避免误伤
    # 内层 .wheel 只做原地旋转（fill-box 中心 = 车轮中心）
    svg = re.sub(r'<g class="wheel">',
                 f'<g class="wheel" transform="rotate({360 * f:.3f})">', svg)
    add_transform(r'<g id="crank"[^>]*>',
                  f"rotate({360 * f:.3f} {geo['bb'][0]:g} {geo['bb'][1]:g})")

    # 2) 双腿：远侧相位差半圈
    for gid, lf in (("legNear", f), ("legFar", (f + 0.5) % 1.0)):
        i, j = group_span(svg, gid)
        chunk = svg[i:j]
        th = keyframe_value(kf["pedalThigh"], lf)
        sh = keyframe_value(kf["pedalShin"], lf)
        for pat, deg, (ox, oy) in (
            (r'<g class="thigh">', th, geo["hip"]),
            (r'<g class="shin">', sh, geo["knee"]),
        ):
            chunk = re.sub(pat, lambda mt, d=deg, o=(ox, oy):
                           set_attr(mt.group(0), "transform", f"rotate({d:.3f} {o[0]:g} {o[1]:g})"),
                           chunk, count=1)
        svg = svg[:i] + chunk + svg[j:]

    # 3) 身体与腿一起起伏
    dy = bob(f)
    for gid in ("rider", "legFar", "legNear"):
        add_transform(rf'<g id="{gid}"[^>]*>', f"translate(0 {dy:.2f})")

    # 4) 翅膀 / 围巾 / 影子
    add_transform(r'<g id="wing"[^>]*>', f"rotate({8 - 20 * env(f):.2f} 604 250)")
    add_transform(r'<g id="scarfA">', f"rotate({-7 + 16 * env(f):.2f} 632 236)")
    add_transform(r'<g id="scarfB">', f"rotate({8 - 17 * env(f):.2f} 634 226)")
    sx = 1 - 0.08 * env(f)
    add_transform(r'<ellipse id="shadow"[^>]*>',
                  f"translate(604 516) scale({sx:.3f} 1) translate(-604 -516)")

    # 5) 视差层
    if with_background:
        for gid, dur in PARALLAX.items():
            pat = rf'<g [^>]*id="{gid}"[^>]*>'
            if not re.search(pat, svg):
                raise AssertionError(f"找不到视差层 #{gid}")
            add_transform(pat, f"translate({-1200.0 * (f * BASE_DUR) / dur:.1f} 0)")
        for gid, dur, delay in CLOUDS:
            add_transform(rf'<g id="{gid}"[^>]*>',
                          f"translate({-1200.0 * (((f * BASE_DUR + delay) / dur) % 1.0):.1f} 0)")

    # 6) resvg 兼容：use 引用改用 xlink:href
    svg = svg.replace("<svg id=", '<svg xmlns:xlink="http://www.w3.org/1999/xlink" id=')
    svg = re.sub(r'\shref="#', ' xlink:href="#', svg)
    return svg


def render(svg: str, out: Path, scale: float = 1.0, crop: tuple | None = None) -> None:
    import resvg_py
    w, h, ox, oy = 1200, 620, 0, 0
    if crop:
        ox, oy, w, h = crop
    # 先整幅渲染，再按比例裁剪（resvg-py 没有直接的裁剪参数）
    png = resvg_py.svg_to_bytes(svg_string=svg, width=1200, background="#ffffff")
    out.write_bytes(png)
    if crop:
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(png))
        k = im.width / 1200.0
        box = (int(ox * k), int(oy * k), int((ox + w) * k), int((oy + h) * k))
        im = im.crop(box)
        if scale != 1.0:
            im = im.resize((int(im.width * scale), int(im.height * scale)))
        im.save(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phases", default="0,0.25,0.5,0.75")
    ap.add_argument("--grid", default="2 2")
    ap.add_argument("--out", default=str(REPO / "animations" / "pelican-bike-sheet.png"))
    ap.add_argument("--scale", type=float, default=0.5, help="输出缩放（拼图用）")
    ap.add_argument("--crop", default="", help="裁剪区域 'x y w h'（SVG 坐标）")
    ap.add_argument("--anim", default="", help="导出连续帧到该目录")
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--no-bg", action="store_true", help="隐藏背景视差层（只看主体）")
    args = ap.parse_args()

    src = HTML_PATH.read_text(encoding="utf-8")
    crop = tuple(float(v) for v in args.crop.split()) if args.crop else None
    tmp = Path(args.out).parent / "_phases"
    tmp.mkdir(parents=True, exist_ok=True)

    # 导出连续帧
    if args.anim:
        outdir = Path(args.anim)
        outdir.mkdir(parents=True, exist_ok=True)
        for i in range(args.frames):
            f = i / args.frames
            p = outdir / f"frame_{i:02d}.png"
            render(pose(src, f, not args.no_bg), p, 1.0, crop)
            print(f"相位 {f:.3f} → {p}")
        return 0

    phases = [float(p) for p in args.phases.split(",")]
    files = []
    for p in phases:
        svg = pose(src, p, not args.no_bg)
        f = tmp / f"phase_{p:.3f}.svg"
        f.write_text(svg, encoding="utf-8")
        png = tmp / f"phase_{p:.3f}.png"
        render(svg, png, args.scale, crop)
        files.append(png)
        print(f"相位 {p:.3f} → {png}")

    try:
        from PIL import Image
    except ImportError:
        print("未安装 pillow，跳过拼图")
        return 0

    cols, rows = (int(v) for v in args.grid.split())
    imgs = [Image.open(f).convert("RGB") for f in files]
    w = max(i.width for i in imgs)
    h = max(i.height for i in imgs)
    sheet = Image.new("RGB", (cols * w + (cols - 1) * 8, rows * h + (rows - 1) * 8), "#20313b")
    for i, im in enumerate(imgs[: cols * rows]):
        sheet.paste(im, ((i % cols) * (w + 8), (i // cols) * (h + 8)))
    sheet.save(args.out)
    print(f"拼图 → {args.out}  ({sheet.width}×{sheet.height})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
