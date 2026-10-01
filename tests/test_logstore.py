"""L0 日志层测试：实体抽取、混合检索、因果上界、回展预算、持久化。全程无网络。"""

import numpy as np
import pytest


from hybrid_memory.logstore import LogStore, entities_in


def _fill(store, scene="接入"):
    store.add_unit(0, 0, user_text="proxy 的 handler.ts 里 hermes 是什么类型？",
                   assistant_text="header-only：_headerOnlyAgents 硬编码包含 hermes。",
                   scene=scene, ts=1_700_000_000)
    store.add_unit(1, 1, user_text="PR #42 合了吗",
                   assistant_text="合了，commit a1b2c3d4e5 已进 main。",
                   scene=scene, ts=1_700_000_000 + 8 * 86400)
    store.add_unit(2, 2, user_text="不对，hermes 后来移出 _headerOnlyAgents 了",
                   assistant_text="收到，改为 form agent，见 handler.ts。",
                   scene="修复", ts=1_700_000_000 + 9 * 86400)


# ---------------------------------------------------------------- 实体
def test_entities_in_picks_hard_identifiers_only():
    ents = dict(entities_in(
        "看 src/proxy/handler.ts 和 PR #42，commit a1b2c3d4e5，模型 deepseek-v4-flash，"
        "普通词 the and 不算"))
    assert ents.get("src/proxy/handler.ts") == "path"
    assert ents.get("#42") == "pr"
    assert ents.get("a1b2c3d4e5") == "hash"
    assert "deepseek-v4-flash" in ents
    assert "the" not in ents and "and" not in ents


def test_add_unit_reports_new_entities_once():
    s = LogStore(None)
    first = s.add_unit(0, 0, user_text="handler.ts 改了", assistant_text="是")
    assert "handler.ts" in first["new_entities"]
    second = s.add_unit(1, 1, user_text="handler.ts 又改了", assistant_text="是")
    assert "handler.ts" in second["entities"]
    assert "handler.ts" not in second["new_entities"]   # 第二次不再是新实体


# ---------------------------------------------------------------- 检索
def test_search_lexical_returns_snippets_not_full_text():
    s = LogStore(None)
    _fill(s)
    hits = s.search("_headerOnlyAgents")
    assert {h["unit_id"] for h in hits} == {0, 2}
    for h in hits:
        assert set(h) >= {"unit_id", "t", "scene", "snippet", "score"}
        assert "user_text" not in h and "assistant_text" not in h


def test_search_cjk_query_works_with_trigram():
    s = LogStore(None)
    _fill(s)
    assert [h["unit_id"] for h in s.search("硬编码包含")] == [0]


def test_search_before_is_strict_and_scene_filters():
    s = LogStore(None)
    _fill(s)
    assert {h["unit_id"] for h in s.search("hermes", before=2)} == {0}
    assert {h["unit_id"] for h in s.search("hermes", before=3)} == {0, 2}
    assert [h["unit_id"] for h in s.search("hermes", scene="修复")] == [2]
    assert s.search("hermes", before=0) == []


def test_search_vector_path_fuses_with_lexical():
    class Emb:
        def embed(self, texts, keys=None):
            # 只有含 "form agent" 的文本靠近查询向量
            return np.array([[1.0, 0.0] if "form agent" in t else [0.0, 1.0]
                             for t in texts], dtype=np.float32)
    s = LogStore(None, embedder=Emb())
    _fill(s)
    hits = s.search("form agent 是什么", k=3)   # 词法命中 unit 2，向量也命中 unit 2
    assert hits and hits[0]["unit_id"] == 2


def test_embedder_failure_does_not_block_write():
    class Boom:
        def embed(self, texts, keys=None):
            raise RuntimeError("no network")
    s = LogStore(None, embedder=Boom())
    s.add_unit(0, 0, user_text="handler.ts", assistant_text="x")
    assert s.count() == 1 and s.n_embed_fail == 1
    assert s.search("handler.ts")[0]["unit_id"] == 0    # 词法路仍可用


# ---------------------------------------------------------------- 时间线 / 统计
def test_timeline_and_mention_counts_respect_before():
    s = LogStore(None)
    _fill(s)
    tl = s.timeline("hermes")
    assert [h["unit_id"] for h in tl] == [0, 2]
    assert [h["unit_id"] for h in s.timeline("HERMES", before=1)] == [0]  # 大小写不敏感
    # hermes 是普通小写词，不是硬实体：时间线走 FTS 回退，mentions 里没有
    assert s.mention_counts(["_headerOnlyAgents", "#42", "hermes"], before=3) == {
        "_headerOnlyAgents": 2, "#42": 1, "hermes": 0}
    assert s.mention_counts(["_headerOnlyAgents"], before=1) == {"_headerOnlyAgents": 1}


def test_stats_group_by_scene_entity_week():
    s = LogStore(None)
    _fill(s)
    by_scene = s.stats("scene")
    assert {r["scene"]: r["units"] for r in by_scene} == {"接入": 2, "修复": 1}
    by_ent = s.stats("entity", limit=3)
    assert by_ent[0]["entity"] in {"handler.ts", "_headeronlyagents"}
    assert by_ent[0]["mentions"] == 2
    by_week = s.stats("week", before=3)
    assert sum(r["units"] for r in by_week) == 3
    assert len(by_week) == 2                    # 第 0 单元与后两个隔了 8 天
    for rows in (by_scene, by_ent, by_week):    # 聚合视图永不带原文
        assert all("user_text" not in r for r in rows)
    with pytest.raises(ValueError):
        s.stats("user")


# ---------------------------------------------------------------- 回展
def test_window_truncates_by_budget_and_reports_missing_omitted():
    s = LogStore(None)
    _fill(s)
    long_reply = "很长的回答。" * 200
    s.add_unit(3, 3, user_text="讲讲方案", assistant_text=long_reply)
    win = s.window([3], max_chars=100)
    assert len(win["units"]) == 1 and win["units"][0]["truncated"]
    assert win["chars"] <= 100 and win["truncated"]
    win = s.window([0, 99, 2], max_chars=10_000, before=2)
    assert [u["unit_id"] for u in win["units"]] == [0]
    assert 99 in win["missing"] and 2 in win["missing"]   # 越界的当不存在
    win = s.window([0, 1, 2], max_chars=60)
    assert win["omitted"]                                # 预算用完后面的整个略过


def test_exists_and_count_with_before():
    s = LogStore(None)
    _fill(s)
    assert s.exists([0, 1, 2, 7]) == {0: 0, 1: 1, 2: 2}
    assert s.exists([0, 1, 2], before=2) == {0: 0, 1: 1}
    assert s.count() == 3 and s.count(before=1) == 1


# ---------------------------------------------------------------- 持久化
def test_persists_to_sqlite_file_and_reopens(tmp_path):
    p = tmp_path / "log.sqlite"
    s = LogStore(p)
    _fill(s)
    s.close()
    s2 = LogStore(p)
    assert s2.count() == 3
    assert s2.get(1)["assistant_text"].startswith("合了")
    assert [h["unit_id"] for h in s2.timeline("#42")] == [1]


# ---------------------------------------------------------------- 证据不可覆盖 / 在线分配
@pytest.mark.parametrize("change", [
    {"user_text": "new_module.py"}, {"assistant_text": "changed"},
    {"t": 9}, {"scene": "other"}, {"assistant_turns": 2}, {"ts": 456.0},
])
def test_duplicate_id_with_different_evidence_is_rejected(change):
    s = LogStore()
    original = dict(t=3, user_text="old_module.py", assistant_text="original",
                    scene="project", assistant_turns=1, ts=123.0)
    try:
        s.add_unit(7, **original)
        with pytest.raises(ValueError, match="unit 7"):
            s.add_unit(7, **(original | change))
        assert s.get(7) == {"id": 7, **original}
        assert s.count() == 1
        assert s.timeline("old_module.py")[0]["snippet"].startswith("old_module.py")
        assert not s.search("new_module.py")
        s._conn.execute("INSERT INTO units_fts(units_fts, rank) VALUES ('integrity-check', 1)")
    finally:
        s.close()


def test_exact_reimport_preserves_timestamp_indexes_and_embedding():
    class Emb:
        calls = 0

        def embed(self, texts, keys=None):
            self.calls += 1
            return np.array([[1.0, 0.0]], dtype=np.float32)

    emb = Emb()
    s = LogStore(embedder=emb)
    try:
        args = dict(user_text="handler.ts", assistant_text="original", scene="s")
        s.add_unit(0, 2, **args)
        before = s.get(0)
        again = s.add_unit(0, 2, **args)  # 未显式给 ts：重试不生成新的落盘时间
        assert s.get(0) == before
        assert again["new_entities"] == []
        assert emb.calls == 1
        assert s.mention_counts(["handler.ts"]) == {"handler.ts": 1}
        s._conn.execute("INSERT INTO units_fts(units_fts, rank) VALUES ('integrity-check', 1)")
    finally:
        s.close()


def test_append_allocates_above_database_and_snapshot_floors(tmp_path):
    s = LogStore(tmp_path / "log.sqlite")
    try:
        assert s.next_position() == (0, 0)
        s.add_unit(7, 42, user_text="old", assistant_text="evidence")
        assert s.next_position() == (8, 43)
        first = s.append_unit(0, user_text="new", assistant_text="a")
        assert (first["unit_id"], first["t"]) == (8, 43)
        second = s.append_unit(100, min_unit_id=20, user_text="newer", assistant_text="b")
        assert (second["unit_id"], second["t"]) == (20, 100)
        assert s.next_position() == (21, 101)
        assert s.get(7)["user_text"] == "old"
    finally:
        s.close()


def test_parallel_connections_allocate_distinct_ids_and_times(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import threading

    stores = [LogStore(tmp_path / "log.sqlite") for _ in range(4)]
    barrier = threading.Barrier(len(stores))

    def write(i):
        barrier.wait(timeout=5)
        return [stores[i].append_unit(0, user_text=f"writer-{i}-{j}",
                                      assistant_text="answer") for j in range(5)]

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = [r for batch in pool.map(write, range(4)) for r in batch]
        assert sorted(r["unit_id"] for r in rows) == list(range(20))
        assert sorted(r["t"] for r in rows) == list(range(20))
        assert stores[0].count() == 20
        assert len({stores[0].get(i)["user_text"] for i in range(20)}) == 20
    finally:
        for s in stores:
            s.close()


def test_failed_index_write_rolls_back_unit_and_allocation():
    import sqlite3

    s = LogStore()
    try:
        s._conn.execute("CREATE TRIGGER fail_mentions BEFORE INSERT ON mentions "
                        "BEGIN SELECT RAISE(ABORT, 'index failed'); END")
        with pytest.raises(sqlite3.IntegrityError, match="index failed"):
            s.append_unit(0, user_text="handler.ts", assistant_text="a")
        assert s.count() == 0
        s._conn.execute("DROP TRIGGER fail_mentions")
        row = s.append_unit(0, user_text="handler.ts", assistant_text="a")
        assert (row["unit_id"], row["t"]) == (0, 0)
        assert s.search("handler.ts")[0]["unit_id"] == 0
    finally:
        s.close()
