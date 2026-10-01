"""用 mock 智谱端点启动**原版** sidecar（hybrid_memory.server.main）。

仓库把 https://open.bigmodel.cn 写死在 llm.py / embed/zhipu.py 里、没有
base URL 配置项，所以这里在进程内把这两个 URL 改写到本地 mock。
除此之外不改任何项目代码。

用法：MOCK_BASE=http://127.0.0.1:18080 ZAI_API_KEY=mock \
      python run_sidecar_offline.py --project /tmp/proj --port 17872 [--no-agent]
（需在仓库根目录下运行或把仓库加进 PYTHONPATH）
"""
import os
import sys
import urllib.request

MOCK = os.environ.get("MOCK_BASE", "http://127.0.0.1:18080")
REAL = "https://open.bigmodel.cn"

import hybrid_memory.llm as llm  # noqa: E402
from hybrid_memory.embed import zhipu  # noqa: E402

_OrigRequest = urllib.request.Request


def _Request(url, *a, **kw):
    if isinstance(url, str) and url.startswith(REAL):
        url = MOCK + url[len(REAL):]
    return _OrigRequest(url, *a, **kw)


llm.Request = _Request
zhipu.Request = _Request
zhipu.ZhipuEmbedder.ENDPOINT = MOCK + "/api/paas/v4/embeddings"

from hybrid_memory import server  # noqa: E402

if __name__ == "__main__":
    server.main()
