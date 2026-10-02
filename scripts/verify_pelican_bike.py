#!/usr/bin/env python3
"""校验（并生成）animations/pelican-bike.html 的动画数据。

没有浏览器可用，所以这里用几何/物理断言来判断动画是否自洽：

A. 结构        HTML 标签配对、SVG 合法 XML、id 唯一、引用不悬空、图层顺序。
B. 模型一致性  从 HTML/CSS 里解析出车轮、中轴、曲柄、髋/膝坐标与腿长，
              断言 CSS 的 transform-origin 就是解析出来的髋/膝，
              两侧腿的绘制几何完全相同。
C. 踩踏 IK    按曲柄相位反解 thigh/shin 关键帧（含身体起伏补偿），
              再把关键帧前向回放一整个周期，断言脚踝始终贴合脚踏。
D. 滚动物理    车轮"纯滚动不打滑"：地面层时长必须等于
              1200 / (车轮周长 / 车轮每转时长)；图案周期必须整除 1200；
              所有动画时长都写成 calc(var(--dur) * k)，保证单旋钮调速。
E. 越界        脚掌最低点不得穿出路面，静态主体不得越出 viewBox。

用法：
    python3 scripts/verify_pelican_bike.py            # 校验 + 回写关键帧
    python3 scripts/verify_pelican_bike.py --check    # 只校验，不改文件
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HTML_PATH = REPO / "animations" / "pelican-bike.html"

VIEW_W, VIEW_H = 1200.0, 620.0
ROAD_Y = 516.0            # 路面顶沿
REV = 1.45                # 期望的车轮/曲柄每转秒数（--dur = 1s 时），与 CSS 互相印证
N_KEY = 36                # 关键帧数量（每 10% 一个）
BOB_AMP = 4.0             # 身体起伏幅度（单位）
BOB_PERIOD_REVS = 0.5     # 起伏周期 = 0.5 转 / 次
MIN_TOL = 0.5             # 脚踝贴合容差（单位）


# ----------------------------------------------------------------- 解析
class Markup:
    """从 HTML/CSS 里抠出全部几何常量。"""

    def __init__(self, src: str) -> None:
        self.src = src
        self.css = src[src.index("<style>"): src.index("</style>")]
        self.svg = src[src.index("<svg"): src.index("</svg>") + 6]

    # -- CSS --
    def css_rule(self, selector: str) -> str:
        m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", self.css)
        if not m:
            raise AssertionError(f"CSS 里找不到规则 {selector}")
        return m.group(1)

    def origin(self, selector: str) -> tuple[float, float]:
        """原点优先取 CSS 规则，其次取该元素的内联 style（如 #crank）。"""
        m = re.search(r"transform-origin:\s*(-?[\d.]+)px\s+(-?[\d.]+)px", self.css_rule(selector))
        if not m and selector.startswith("#"):
            m = re.search(rf'id="{selector[1:]}"[^>]*style="[^"]*transform-origin:\s*'
                          r"(-?[\d.]+)px\s+(-?[\d.]+)px", self.svg)
        if not m:
            raise AssertionError(f"{selector} 缺少 px 形式的 transform-origin")
        return float(m.group(1)), float(m.group(2))

    def dur_mult(self, selector: str) -> float:
        m = re.search(r"animation-duration:\s*calc\(var\(--dur\)\s*\*\s*([\d.]+)\)",
                      self.css_rule(selector))
        if not m:
            raise AssertionError(f"{selector} 的 animation-duration 不是 calc(var(--dur) * k)")
        return float(m.group(1))

    def anim_dur_mult(self, selector_part: str) -> float:
        m = re.search(re.escape(selector_part) +
                      r"[^{]*\{[^}]*animation:\s*\w+\s+calc\(var\(--dur\)\s*\*\s*([\d.]+)\)", self.css)
        if not m:
            raise AssertionError(f"找不到 {selector_part} 的 animation 时长")
        return float(m.group(1))

    # -- SVG --
    def group(self, gid: str) -> str:
        m = re.search(rf'<g id="{gid}"[^>]*>', self.svg)
        if not m:
            raise AssertionError(f"找不到 <g id=\"{gid}\">")
        # 取到配对的 </g>：按 <g / </g> 计数
        i, depth = m.start(), 0
        for tok in re.finditer(r"<g\b|</g>", self.svg[m.start():]):
            depth += 1 if tok.group(0) == "<g" else -1
            if depth == 0:
                i = m.start() + tok.end()
                break
        return self.svg[m.start(): i]

    def group_in(self, chunk: str, cls: str) -> str:
        """取 chunk 内第一个 class 匹配的 <g>…</g>（含首尾）。"""
        m = re.search(rf'<g class="{cls}">', chunk)
        if not m:
            raise AssertionError(f"找不到 <g class=\"{cls}\">")
        depth = 0
        for tok in re.finditer(r"<g\b|</g>", chunk[m.start():]):
            depth += 1 if tok.group(0) == "<g" else -1
            if depth == 0:
                return chunk[m.start(): m.start() + tok.end()]
        raise AssertionError(f"<g class=\"{cls}\"> 不闭合")

    def rects(self, chunk: str, cls: str | None = None) -> list[dict]:
        pat = r'<rect\b([^>]*)/>' if cls is None else rf'<rect\b([^>]*class="{cls}"[^>]*)/>'
        out = []
        for m in re.finditer(pat, chunk):
            attrs = {k: float(v) for k, v in re.findall(r'([a-zA-Z-]+)="(-?[\d.]+)"', m.group(1))}
            out.append(attrs)
        return out

    def parse(self) -> dict:
        d: dict = {}

        # 车轮：<g class="wheel" transform="translate(x y)"> ... <circle r="R" .../>
        wheels = re.findall(
            r'<g transform="translate\((-?[\d.]+) (-?[\d.]+)\)">\s*<g class="wheel">(.*?)</g>\s*</g>',
            self.svg, flags=re.S)
        if len(wheels) != 2:
            raise AssertionError(f"期望 2 个车轮，解析到 {len(wheels)} 个")
        wr = set()
        centers = []
        for x, y, body in wheels:
            m = re.search(r'<circle r="([\d.]+)"[^>]*stroke-width="([\d.]+)"', body)
            wr.add((float(m.group(1)), float(m.group(2))))
            centers.append((float(x), float(y)))
        if len(wr) != 1:
            raise AssertionError(f"两个车轮的半径/线宽不一致: {wr}")
        d["wheel_center"] = centers[0]
        d["wheel_centers"] = centers
        d["wheel_r"], d["tire"] = wr.pop()

        # 中轴：曲柄的 transform-origin；曲柄半径：脚踏中心到中轴距离
        d["bb"] = self.origin("#crank")
        crank = self.group("crank")
        pedals = [r for r in self.rects(crank) if abs(r["width"] - 40) < 0.01]
        if len(pedals) != 2:
            raise AssertionError(f"期望 2 个脚踏，解析到 {len(pedals)} 个")
        radii = [math.dist((r["x"] + r["width"] / 2, r["y"] + r["height"] / 2), d["bb"])
                 for r in pedals]
        if max(radii) - min(radii) > 0.01:
            raise AssertionError(f"两个脚踏到中轴的距离不一致: {radii}")
        d["crank_r"] = radii[0]

        # 腿：髋 = .thigh 原点，膝 = .shin 原点；腿长取绘制矩形高度
        d["hip"] = self.origin(".thigh")
        d["knee"] = self.origin(".shin")
        legs = {}
        for lid in ("legNear", "legFar"):
            g = self.group(lid)
            thigh_g = self.group_in(g, "thigh")
            shin_g = self.group_in(thigh_g, "shin")        # 小腿必须嵌在大腿里
            th = self.rects(thigh_g.replace(shin_g, ""))   # 只取大腿自己的矩形
            sh = self.rects(shin_g)
            if len(th) != 1 or len(sh) != 1:
                raise AssertionError(f"#{lid} 大腿/小腿各应恰好 1 个矩形")
            legs[lid] = (th[0], sh[0])
        if legs["legNear"] != legs["legFar"]:
            raise AssertionError("近侧腿与远侧腿的绘制几何必须完全一致（靠配色和相位区分）")
        d["thigh_rect"], d["shin_rect"] = legs["legNear"]
        d["thigh_len"] = d["thigh_rect"]["height"]
        d["shin_len"] = d["shin_rect"]["height"]

        # 脚掌多边形（小腿组内的 path）
        m = re.search(r'<g class="shin">.*?<path d="([^"]+)"', self.group("legNear"), flags=re.S)
        nums = [float(v) for v in re.findall(r"-?[\d.]+", m.group(1))]
        d["foot"] = list(zip(nums[0::2], nums[1::2]))

        d["road_y"] = ROAD_Y
        return d


# ----------------------------------------------------------------- 数学
def bob(f: float) -> float:
    """身体起伏（相对髋关节的位移，线性三角波，周期 0.5 转）。"""
    u = (f / BOB_PERIOD_REVS) % 1.0
    return -BOB_AMP * (2 * u if u < 0.5 else 2 * (1 - u))


def rot(deg: float, p, c):
    t = math.radians(deg)
    cs, sn = math.cos(t), math.sin(t)
    dx, dy = p[0] - c[0], p[1] - c[1]
    return (c[0] + dx * cs - dy * sn, c[1] + dx * sn + dy * cs)


def unwrap(vals: list[float]) -> list[float]:
    out = list(vals)
    for i in range(1, len(out)):
        while out[i] - out[i - 1] > 180:
            out[i] -= 360
        while out[i] - out[i - 1] < -180:
            out[i] += 360
    return out


class Leg:
    def __init__(self, geo: dict) -> None:
        self.hip = geo["hip"]
        self.bb = geo["bb"]
        self.crank = geo["crank_r"]
        self.a = geo["thigh_len"]      # 大腿
        self.b = geo["shin_len"]       # 小腿
        self.foot = geo["foot"]        # 脚掌多边形顶点（基准姿态下的绝对坐标）

    def pedal(self, f: float):
        ang = math.radians(360.0 * f)
        return (self.bb[0] + self.crank * math.sin(ang), self.bb[1] + self.crank * math.cos(ang))

    def hip_at(self, f: float):
        return (self.hip[0], self.hip[1] + bob(f))

    def ik(self, f: float):
        """返回该相位下的 (大腿旋转, 小腿旋转)，膝盖朝前。"""
        hip = self.hip_at(f)
        foot = self.pedal(f)
        dx, dy = foot[0] - hip[0], foot[1] - hip[1]
        d = math.hypot(dx, dy)
        if not (abs(self.a - self.b) < d < self.a + self.b):
            raise AssertionError(f"相位 {f:.2f}: 髋到脚踏距离 {d:.1f} 超出腿长范围")
        phi = math.atan2(dy, dx)
        al = math.acos((self.a ** 2 + d ** 2 - self.b ** 2) / (2 * self.a * d))
        knee_dir = phi - al                       # 膝在髋前方（人类骑车姿态）
        knee = (hip[0] + self.a * math.cos(knee_dir), hip[1] + self.a * math.sin(knee_dir))
        thigh_deg = math.degrees(knee_dir) - 90.0   # 相对“竖直向下”基准姿态
        world = math.degrees(math.atan2(foot[1] - knee[1], foot[0] - knee[0])) - 90.0
        # 小腿是大腿的子节点，CSS 的旋转会叠加，所以要减掉大腿自身转角
        return thigh_deg, world - thigh_deg

    def fk(self, f: float, thigh_deg: float, shin_deg: float):
        """按浏览器的方式重放两次旋转，返回 (髋, 膝, 踝, 脚掌顶点)。"""
        hip = self.hip_at(f)
        knee0 = (hip[0], hip[1] + self.a)
        ankle0 = (hip[0], hip[1] + self.a + self.b)
        knee = rot(thigh_deg, knee0, hip)
        ankle = rot(thigh_deg, rot(shin_deg, ankle0, knee0), hip)
        foot = [rot(thigh_deg, rot(shin_deg, p, knee0), hip) for p in self.foot]
        return hip, knee, ankle, foot


# ----------------------------------------------------------------- 生成
def css_keyframes(thigh: list[float], shin: list[float]) -> str:
    lines = ["  /* IK-GENERATED-START  由校验脚本重写，勿手改 */"]
    for name, vals in (("pedalThigh", thigh), ("pedalShin", shin)):
        lines.append(f"  @keyframes {name} {{")
        lines += [f"    {round(i * 100 / N_KEY)}%{{transform:rotate({v:.2f}deg)}}"
                  for i, v in enumerate(vals)]
        lines.append("  }")
    lines.append("  /* IK-GENERATED-END */")
    return "\n".join(lines)


def replay(leg: Leg, thigh: list[float], shin: list[float], steps: int = 720):
    """线性插值回放关键帧，返回 (最大脚踝偏差, 最低脚掌 y, 膝弯角范围)。"""
    worst, lowest, kmax, kmin = 0.0, -1e9, -1e9, 1e9
    for i in range(steps):
        f = i / steps
        pos = f * N_KEY
        lo = min(int(pos), N_KEY - 1)
        hi = lo + 1
        t = pos - int(pos)
        th = thigh[lo] + (thigh[hi] - thigh[lo]) * t
        sh = shin[lo] + (shin[hi] - shin[lo]) * t
        hip, knee, ankle, foot = leg.fk(f, th, sh)
        worst = max(worst, math.dist(ankle, leg.pedal(f)))
        lowest = max(lowest, max(p[1] for p in foot))
        knee_dir = math.degrees(math.atan2(knee[1] - hip[1], knee[0] - hip[0]))
        shin_dir = math.degrees(math.atan2(ankle[1] - knee[1], ankle[0] - knee[0]))
        bend = (shin_dir - knee_dir + 540) % 360 - 180          # 膝盖伸展角
        flexion = 180 - abs(bend)                                # 屈膝量
        kmax, kmin = max(kmax, flexion), min(kmin, flexion)
    return worst, lowest, kmin, kmax


# ----------------------------------------------------------------- 结构
class Tags(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack:
            self.errors.append(f"line {self.getpos()[0]}: 多余的 </{tag}>")
            return
        got, line = self.stack.pop()
        if got != tag:
            self.errors.append(f"line {self.getpos()[0]}: </{tag}> 闭合了 <{got}>（开于 line {line}）")


def check_structure(m: Markup) -> list[str]:
    problems: list[str] = []
    bal = Tags()
    bal.feed(m.src)
    bal.close()
    problems += bal.errors + [f"line {ln}: <{t}> 未闭合" for t, ln in bal.stack]

    try:
        root = ET.fromstring(m.svg)
    except ET.ParseError as exc:
        return problems + [f"SVG 不是合法 XML: {exc}"]

    ids = [el.get("id") for el in root.iter() if el.get("id")]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        problems.append(f"重复的 id: {dupes}")
    known = set(ids)
    for el in root.iter():
        for attr in ("href", "fill", "stroke"):
            v = el.get(attr) or ""
            ref = None
            if attr == "href" and v.startswith("#"):
                ref = v[1:]
            elif v.startswith("url(#") and v.endswith(")"):
                ref = v[5:-1]
            if ref and ref not in known:
                problems.append(f"<{el.tag}> 引用了不存在的 {attr}=\"{v}\"")

    order = [i for i in ids if i in ("shadow", "legFar", "bike", "rider", "legNear", "speedLines")]
    if order != ["shadow", "legFar", "bike", "rider", "legNear", "speedLines"]:
        problems.append(f"图层顺序错误（远侧腿须在车架前、近侧腿须在身体后）: {order}")

    # 视差层必须自带 +1200 的副本，才能无缝循环
    for gid in ("birds", "hillsBack", "hillsNear", "grassTufts", "roadMarks", "gravel", "speedLines"):
        if f'id="{gid}"' not in m.svg:
            problems.append(f"缺少滚动层 #{gid}")
    if "translate(1200 0)" not in m.svg:
        problems.append("缺少 translate(1200 0) 的副本，视差层无法无缝")

    # 图案周期必须整除位移 1200
    for pid in ("dashPat", "gravelPat"):
        w = re.search(rf'<pattern id="{pid}" width="([\d.]+)"', m.svg)
        if not w:
            problems.append(f"缺少 <pattern id=\"{pid}\">")
        elif 1200 % float(w.group(1)) != 0:
            problems.append(f"#{pid} 周期 {w.group(1)} 不能整除 1200，循环时会跳变")

    css_nc = re.sub(r"/\*.*?\*/", "", m.css, flags=re.S)

    # 关键不变量：CSS 动画里的 transform 会覆盖元素的 transform 呈现属性（不是叠加）。
    # 因此凡是“动 transform”的动画命中的元素，都不能再自带 transform 属性。
    animated_tf = {
        name for name, body in
        re.findall(r"@keyframes (\w+) \{((?:[^{}]|\{[^}]*\})*)\}", css_nc)
        if "transform" in body
    }
    targets: list[tuple[str, str]] = []
    for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", css_nc):
        anims = re.findall(r"animation:\s*([\w-]+)", body)          # 简写
        anims += re.findall(r"animation-name:\s*([\w-]+)", body)   # 展开式
        if not any(a in animated_tf for a in anims):
            continue
        for one in sel.split(","):
            one = one.strip()
            if re.fullmatch(r"\.[\w-]+", one):
                targets.append(("class", one[1:]))
            elif re.fullmatch(r"#[\w-]+", one):
                targets.append(("id", one[1:]))
    for kind, key in targets:
        for mt in re.finditer(rf'<[a-z]+ [^>]*{kind}="{re.escape(key)}"[^>]*>', m.svg):
            if re.search(r'\stransform="', mt.group(0)):
                problems.append(
                    f"{kind}={key} 既有 transform 呈现属性又被动画操作 transform，"
                    f"会被覆盖而不是叠加: {mt.group(0)[:90]}")
    if not targets:
        problems.append("没有解析到任何“动 transform”的动画选择器，规则形同虚设")

    # 两侧腿必须共享同一个起伏动画（否则髋部与身体会脱节）
    for gid in ("legFar", "legNear"):
        if f'id="{gid}" class="legs"' not in m.svg and f'class="legs" id="{gid}"' not in m.svg:
            problems.append(f"#{gid} 缺少 class=\"legs\"，不会跟随身体起伏")

    # 每个会动的元素都必须有 calc(var(--dur) * k) 的时长，保证单个速度旋钮统一调速
    for cls in ("scroll", "cloud"):
        tagged = re.findall(r'<g ([^>]*)>', m.svg)
        for attrs in tagged:
            if f'class="{cls}"' not in attrs:
                continue
            gid = re.search(r'id="([^"]+)"', attrs)
            if not gid:
                continue
            gid = gid.group(1)
            try:
                m.dur_mult(f"#{gid}")
            except AssertionError as exc:
                problems.append(f"#{gid}: {exc}")
    for selector, body in re.findall(r"([^{}]+)\{([^}]*)\}", css_nc):
        if selector.strip() in (".scroll", ".cloud"):
            continue                      # 基础规则，时长由各自 id 规则提供
        for decl in re.findall(r"animation(?:-duration)?:[^;]*", body):
            if "var(--dur)" not in decl:
                problems.append(f"{selector.strip()} 的时长未参数化: {decl.strip()}")
    return problems


# ----------------------------------------------------------------- 主流程
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验，不回写关键帧")
    args = ap.parse_args()

    src = HTML_PATH.read_text(encoding="utf-8")
    m = Markup(src)
    failures = check_structure(m)

    geo = m.parse()
    leg = Leg(geo)

    # --- 模型自洽：CSS 原点必须落在绘制矩形的关节位置上 ---
    tr, sr = geo["thigh_rect"], geo["shin_rect"]
    if abs(tr["x"] + tr["width"] / 2 - geo["hip"][0]) > 0.01 or abs(tr["y"] - geo["hip"][1]) > 0.01:
        failures.append("大腿矩形上端必须正好在髋关节上")
    if abs(tr["y"] + tr["height"] - geo["knee"][1]) > 0.01:
        failures.append("大腿矩形下端不在膝关节 y 上")
    if abs(sr["y"] - geo["knee"][1]) > 0.01:
        failures.append("小腿矩形上端不在膝关节 y 上")
    if abs(sr["x"] + sr["width"] / 2 - geo["knee"][0]) > 0.01:
        failures.append("小腿矩形的水平中心不在膝关节 x 上")
    if geo["hip"][1] > geo["knee"][1] or geo["knee"][1] > geo["bb"][1]:
        failures.append("髋、膝、中轴的垂直次序不对")

    # --- 腿长可达性：曲柄整圈都必须够得着，且两端都留有余量 ---
    dists = [math.dist(leg.hip_at(f / 360), leg.pedal(f / 360)) for f in range(360)]
    reach, shorten = geo["thigh_len"] + geo["shin_len"], abs(geo["thigh_len"] - geo["shin_len"])
    if max(dists) > reach - 4:
        failures.append(f"踩到下死点时腿几乎锁死（{max(dists):.1f} vs 腿长 {reach:.1f}）")
    if min(dists) < shorten + 4:
        failures.append(f"踩到上死点时腿过度折叠（{min(dists):.1f}）")

    # --- 求解并回放 ---
    thigh = unwrap([leg.ik(i / N_KEY)[0] for i in range(N_KEY + 1)])
    shin = unwrap([leg.ik(i / N_KEY)[1] for i in range(N_KEY + 1)])
    worst, lowest, kmin, kmax = replay(leg, thigh, shin)

    # --- 滚动不打滑 ---
    circ = 2 * math.pi * geo["wheel_r"]
    wheel_mult = m.anim_dur_mult(".wheel")
    crank_mult = m.anim_dur_mult("#crank")
    if abs(wheel_mult - crank_mult) > 1e-9:
        failures.append(f"车轮({wheel_mult}) 与曲柄({crank_mult}) 的周期不一致")
    if abs(wheel_mult - REV) > 1e-9:
        failures.append(f"车轮周期 {wheel_mult} 与常量 {REV} 不符")
    ground_mult = 1200.0 / (circ / wheel_mult)          # 走完 1200 单位所需秒数
    for layer in ("#gravel", "#roadMarks"):
        got = m.dur_mult(layer)
        if abs(got - ground_mult) > 0.03:
            failures.append(f"{layer} 时长 {got} 与地面速度不符（应为 {ground_mult:.2f}）")

    # --- 越界 ---
    if lowest > geo["road_y"] - 2:
        failures.append(f"脚掌最低点 {lowest:.1f} 穿出路面（{geo['road_y']}）")
    static = re.sub(r"<defs>.*?</defs>", "", m.svg, flags=re.S)
    static = re.sub(r'<g id="(?:birds|hillsBack|hillsNear|grassTufts|roadMarks|gravel|speedLines)".*?</g>\s*',
                    "", static, flags=re.S)
    xs = [float(v) for v in re.findall(r'\b(?:cx|x|x1|x2)="(-?[\d.]+)"', static)]
    if xs and (min(xs) < -10 or max(xs) > VIEW_W + 10):
        failures.append(f"静态图形越出 viewBox: x ∈ [{min(xs)}, {max(xs)}]")

    # --- 报告 ---
    kmh = (circ / 60.0) / wheel_mult * 3.6
    print(f"几何  车轮中心 {geo['wheel_centers']}  r={geo['wheel_r']}  周长 {circ:.1f} 单位")
    print(f"      中轴 {geo['bb']}  曲柄半径 {geo['crank_r']:.1f}  髋 {geo['hip']}  膝 {geo['knee']}")
    print(f"      大腿 {geo['thigh_len']:.0f} + 小腿 {geo['shin_len']:.0f} = {reach:.0f}；"
          f"髋到脚踏 {min(dists):.1f} … {max(dists):.1f}")
    print(f"关键帧 thigh {min(thigh):+.1f}° … {max(thigh):+.1f}°   shin {min(shin):+.1f}° … {max(shin):+.1f}°")
    print(f"IK 复核 脚踝最大偏差 {worst:.4f} 单位（容差 {MIN_TOL}）；"
          f"膝角 {kmin:.0f}° … {kmax:.0f}°（180° = 完全伸直）")
    print(f"滚动  车轮 {wheel_mult}s/转 → 地面层 {ground_mult:.2f}s/1200 单位 → {kmh:.1f} km/h")
    print(f"越界  脚掌最低点 y={lowest:.1f}，路面 y={geo['road_y']:.0f}")

    if worst > MIN_TOL:
        failures.append(f"脚踝偏离脚踏 {worst:.3f} 单位")
    if not (50.0 < kmin and kmax < 165.0):
        failures.append(f"屈膝范围不自然（伸直=180°）: {kmin:.0f}° … {kmax:.0f}°")
    if kmax < 115.0:
        failures.append(f"踩到下死点时腿没有展开（最大 {kmax:.0f}°）")

    if not args.check:
        new = re.sub(r"  /\* IK-GENERATED-START.*?IK-GENERATED-END \*/",
                     lambda _m: css_keyframes(thigh, shin), src, count=1, flags=re.S)
        if new != src:
            HTML_PATH.write_text(new, encoding="utf-8")
            print("已回写 IK 关键帧 →", HTML_PATH.relative_to(REPO))
        else:
            print("IK 关键帧已是最新")

    if failures:
        print("\n校验失败:")
        for f in failures:
            print("  ✗", f)
        return 1
    print("\n校验通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
