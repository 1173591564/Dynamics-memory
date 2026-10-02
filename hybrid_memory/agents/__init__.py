"""抽取协议（P6 落地：agent/trio.py 拆分，源文件删除）。

agents 只做"把 agent 输出变成可校验的决定"：载荷组装 + 三角色校验 +
唯一 OpenCode 实现。不碰 store/（I1），不直接读写任务表。
"""
