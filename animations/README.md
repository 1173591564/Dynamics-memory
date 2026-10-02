# 鹈鹕骑车动画

一只戴头盔、系围巾的鹈鹕骑着小轮径折叠车的循环动画。**单个 HTML 文件，零外部依赖**，
双击 `pelican-bike.html` 就能在任何现代浏览器里播放。

![预览](pelican-bike-preview.png)

## 内容

| 文件 | 说明 |
| --- | --- |
| `pelican-bike.html` | 动画本体。内联 SVG + CSS 动画 + 一小段统计里程的 JS |
| `pelican-bike-preview.png` | 单帧预览（由快照脚本渲染，便于在 GitHub 上直接看到效果） |
| `../scripts/verify_pelican_bike.py` | 校验脚本：结构 / 几何 / 物理 / 越界，并用 IK 生成腿部关键帧 |
| `../scripts/snapshot_pelican_bike.py` | 无浏览器环境下的“定格截图”工具（resvg 渲染 PNG） |

## 交互

- **⏸ 暂停 / ▶ 继续**：冻结全部 CSS 动画（`animation-play-state`），里程也不再累加。
- **🐢 慢速 / 🚴 正常 / 🚀 飞驰**：只改根元素上的 `--dur`，所有动画时长都写成
  `calc(var(--dur) * k)`，因此整幅画面按同一比例加减速，不会出现“车轮快、背景慢”的错位。
- **里程 / 时速读数**：按“车轮纯滚动”换算 —— 车轮周长 ÷ 每转时长，单位换算到 km。
  默认档约 14 km/h（等同于真实骑行的速度感）。
- 系统开启“减少动态效果”时，整幅动画自动放慢到 1/6 速度。

## 动画是怎么做的

所有动画都是 CSS `@keyframes`，SVG 只负责画面：

- **车轮**：定位写在父级 `<g transform="translate(...)">`，内层 `.wheel` 用
  `transform-box: fill-box` 绕自身中心旋转。**注意** CSS 动画的 `transform` 会*覆盖*而非叠加
  元素的 `transform` 呈现属性，所以被动画操作的元素不能再自带 `transform` 属性——校验脚本里有专门的规则拦这个。
- **背景视差**：位移恒定 `-1200px`（正好一个 viewBox 宽），每个图层都自带一份
  `translate(1200 0)` 的副本，且图案周期（120）整除 1200，所以循环时完全无缝。
- **滚动速度**：以“车轮纯滚动不打滑”为基准——车轮每转 1.45s、周长 ≈ 326.7 单位，
  地面层走完 1200 单位就是 5.33s，其余图层按 1/3、1/10、1/16 等比例变慢。
  整幅画面因此始终自洽：**车速、踏频、背景速度互相匹配**。
- **踩踏**：腿是两连杆机构（髋 → 膝 → 踝）。脚本对曲柄整圈的 36 个相位做**逆向运动学**求解，
  生成 `@keyframes pedalThigh / pedalShin`，让脚掌始终踩在脚踏上；膝盖取“朝前”的那组解，
  符合骑车姿态。两腿相位差半圈，身体随之上下起伏（起伏也参与 IK 补偿，避免脚打滑）。

## 改动后如何自检

```bash
python3 scripts/verify_pelican_bike.py            # 校验并把 IK 关键帧回写到 HTML
python3 scripts/verify_pelican_bike.py --check    # 只校验，不写文件
```

校验内容：

1. HTML 标签配对、SVG 合法、id 唯一、`href/fill` 引用不悬空；
2. 图层顺序（影子 → 远侧腿 → 车架 → 身体 → 近侧腿 → 速度线）；
3. 几何自洽：CSS 的 `transform-origin` 必须等于从矩形里解析出来的髋/膝坐标，两侧腿绘制完全一致；
4. 踩踏 IK：把生成的关键帧重新前向回放一整圈，脚踝与脚踏的偏差必须 < 0.5 单位；
5. 滚动物理：地面层时长必须等于 `1200 / (车轮周长 / 每转时长)`，图案周期整除 1200；
6. 越界：脚掌不得穿出路面，静态图形不得越出 viewBox。

想肉眼看某一帧（无浏览器环境可用）：

```bash
python3 scripts/snapshot_pelican_bike.py                                   # 4 相位拼图
python3 scripts/snapshot_pelican_bike.py --phases 0.5 --crop "470 300 260 240" --scale 2
```

依赖：`pip install resvg-py pillow`。
