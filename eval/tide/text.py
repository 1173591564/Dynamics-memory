"""文本工具：token 计数（与被测系统约定的同一规则）、token 精确匹配、L1 话术模板。

模板同时被生成器（渲染）和健全性参照系统（解析）使用——健全性系统是
"理想抽取 + 已知缺陷"，它们的作用是验证基准本身，不是参赛者。
"""
from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]|[A-Za-z0-9_]+|[^\sA-Za-z0-9_]")


def approx_tokens(text: str) -> int:
    """CJK 单字 = 1，ASCII 词 = 1，其余非空白符号 = 1。"""
    return len(_TOKEN_RE.findall(text))


def truncate_lines(text: str, budget: int) -> tuple[str, int, bool]:
    """按整行截断到预算内。返回 (文本, 实际 token 数, 是否发生截断)。"""
    kept, used = [], 0
    lines = [ln for ln in text.split("\n") if ln.strip()]
    for ln in lines:
        cost = approx_tokens(ln) + (1 if kept else 0)
        if used + cost > budget:
            return "\n".join(kept), used, True
        kept.append(ln)
        used += cost
    return "\n".join(kept), used, False


def has_token(text: str, tok: str) -> bool:
    """值 token 形如 zorvex-4821：前后不能紧贴字母数字或连字符。"""
    return re.search(rf"(?<![A-Za-z0-9\-]){re.escape(tok)}(?![A-Za-z0-9\-])", text) is not None


# ---------------- L1 话术模板 ----------------

def scope_prefix(scope: str) -> str:
    return f"{scope} 模块的" if scope else ""


def say_set(subj: str, scope: str, val: str) -> tuple[str, str]:
    p = scope_prefix(scope)
    return f"{p}{subj}定为 {val}。", f"好的，已记录：{p}{subj}是 {val}。"


def say_update(subj: str, scope: str, val: str) -> tuple[str, str]:
    p = scope_prefix(scope)
    return f"{p}{subj}改成 {val} 了。", f"明白，{p}{subj}已改为 {val}。"


def say_retract(subj: str, scope: str) -> tuple[str, str]:
    p = scope_prefix(scope)
    return f"{p}{subj}那个设定作废了，先别用。", f"好的，{p}{subj}的设定已作废。"


def say_derive(up_subj: str, up_val: str, subj: str, val: str) -> tuple[str, str]:
    return (f"因为{up_subj}是 {up_val}，所以{subj}用 {val}。",
            f"收到，{subj}是 {val}（依赖{up_subj}）。")


def ask(subj: str, scope: str = "") -> str:
    return f"{scope_prefix(scope)}{subj}现在是什么？"


RE_SET = re.compile(r"^(?:(\S+) 模块的)?(.+?)定为 (\S+)。$")
RE_UPDATE = re.compile(r"^(?:(\S+) 模块的)?(.+?)改成 (\S+) 了。$")
RE_RETRACT = re.compile(r"^(?:(\S+) 模块的)?(.+?)那个设定作废了，先别用。$")
RE_DERIVE = re.compile(r"^因为(.+?)是 (\S+)，所以(.+?)用 (\S+)。$")
RE_ASK = re.compile(r"^(?:(\S+) 模块的)?(.+?)现在是什么？$")

FILLER = [
    ("帮我看下这个报错栈，是哪里空指针了", "看了一下，是入参没判空，已经补上判断。"),
    ("这段代码能再简化一下吗", "可以，把重复的分支合并了，逻辑不变。"),
    ("单测又挂了，看看原因", "是时区相关的断言不稳定，改成固定时区了。"),
    ("给这个函数补个注释", "好的，补了参数和返回值说明。"),
    ("这个 PR 描述帮我润色一下", "润色好了，突出了改动动机和影响范围。"),
    ("查下为什么页面白屏", "是某个组件渲染时抛了异常，加了错误边界。"),
    ("把这个类拆成两个文件", "拆好了，接口保持不变。"),
    ("这个正则写得对吗", "有个转义漏了，已经修正并加了用例。"),
    ("帮我想个更好的变量名", "建议用更具体的名字，已经替换。"),
    ("这个循环性能有问题吗", "有一次多余的拷贝，改成原地处理了。"),
    ("帮我写个 README 的安装章节", "写好了，包含依赖和常见问题。"),
    ("看看这个 SQL 能不能走索引", "条件里对列做了函数运算，改写后能走索引。"),
]
