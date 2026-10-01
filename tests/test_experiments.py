"""实验入口的本地协议检查；不读取凭据、不请求外部模型。"""
import importlib
import json
import sys

import pytest

from experiments.candgen_real import load_candidates


@pytest.mark.parametrize("name,extra", [
    ("qa_real", []), ("qa_continuity", []), ("pool_cov", []),
    ("rejudge_kp", ["--summaries", "unused.json"]),
])
def test_remote_evaluators_require_consent_before_any_io(monkeypatch, name, extra):
    module = importlib.import_module(f"experiments.{name}")

    def forbidden(*args, **kwargs):
        pytest.fail("must reject before reading credentials or data")

    monkeypatch.setattr(module, "load_dotenv_key", forbidden)
    monkeypatch.setattr(module, "load_interaction_units", forbidden)
    monkeypatch.setattr(sys, "argv", [name, *extra])
    with pytest.raises(SystemExit, match="--allow-remote is required"):
        module.main()


def test_cached_candidates_share_parser_and_keep_last_success(tmp_path):
    path = tmp_path / "candidates.jsonl"
    rows = [{"window_id": 0, "scene_name": "s", "candidates": [
        "legacy fact", {"text": "key sk-1234567890abcd", "priority": 100,
                        "source_unit_ids": [1, 2]}, {"no_text": True}]},
        {"window_id": 0, "error": "failed retry"},
        {"window_id": 1, "error": "failed window"}]
    path.write_text('\n'.join(json.dumps(r) for r in rows), encoding="utf-8")
    windows, redacted = load_candidates(path)
    assert set(windows) == {0} and redacted == 1
    assert windows[0] == [
        {"text": "legacy fact", "src": (), "salience": 0.5, "scene": "s"},
        {"text": "key [REDACTED]", "src": (1, 2), "salience": 1.0, "scene": "s"}]


def test_benchmark_cache_does_not_reuse_different_window_stride(tmp_path, monkeypatch):
    from experiments import run_bench
    from hybrid_memory.candgen.base import CandidateGeneration
    from hybrid_memory.datasets.bench import BenchInstance
    from hybrid_memory.datasets.real_chat import InteractionUnit

    class Generator:
        calls = []

        def generate(self, window, prev_scene):
            self.calls.append(window.start_unit_id)
            return CandidateGeneration(())

    monkeypatch.setattr(run_bench, "CG_DIR", tmp_path)
    units = tuple(InteractionUnit(i, i, i, "q", "a", 1) for i in range(6))
    inst = BenchInstance("sample", units, (), ())
    gen = Generator()
    run_bench._gen_or_load(inst, 2, 1, gen)
    assert gen.calls == [0, 1, 2, 3, 4]
    gen.calls.clear()
    run_bench._gen_or_load(inst, 2, 2, gen)
    assert gen.calls == [0, 2, 4]
    gen.calls.clear()
    run_bench._gen_or_load(inst, 2, 2, gen)
    assert not gen.calls


def test_real_replay_flushes_tail_without_future_retrieval_and_counts_only_injected(tmp_path, monkeypatch):
    import csv
    import numpy as np
    from experiments import run_real
    from hybrid_memory.datasets.real_chat import InteractionUnit

    class Embedder:
        last_prompt_tokens = 0

        def embed(self, texts, keys=None):
            return np.tile(np.array([1., 0.], dtype=np.float32), (len(texts), 1))

    units = [InteractionUnit(i, i, i, "q", "a", 1) for i in range(3)]
    monkeypatch.setattr(run_real, "load_interaction_units", lambda _: units)
    monkeypatch.setattr(run_real, "ZhipuEmbedder", lambda **_: Embedder())
    monkeypatch.setattr(run_real.P, "EMB_CACHE", tmp_path / "embedding.sqlite")
    monkeypatch.setattr(run_real.P, "RUNS", tmp_path)
    monkeypatch.setattr(run_real.P, "QA", tmp_path)
    cache = tmp_path / "candidates.jsonl"
    cache.write_text('\n'.join(json.dumps({"window_id": i, "candidates": [
        {"text": "fact", "source_unit_ids": [0]}]}) for i in (0, 999)))
    monkeypatch.setattr(sys, "argv", ["run_real", "--offline", "--candgen", str(cache),
                                      "--out-prefix", "test"])
    run_real.main()
    summary = json.loads((tmp_path / "test-summary.json").read_text())
    rows = list(csv.DictReader((tmp_path / "test-trajectory.csv").open()))
    mems = (tmp_path / "test-memories.jsonl").read_text().splitlines()
    assert summary["windows_injected"] == 1 and summary["candidates_total"] == 1
    assert len(mems) == 1 and json.loads(mems[0])["birth"] == 3
    assert len(rows) == 3 and all(int(r["n_selected"]) == 0 for r in rows)
