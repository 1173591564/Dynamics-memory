"""生命周期（P4 从 server.py 原样迁入）：启动恢复/健康门/存盘/单元恢复线程。

build_service 与 snapshot_status 未落地（§2.7 愿望）：现状无独立等价物，
组装仍在门面 __init__，快照状态仍是内联三行；行为保留，见提交信息。
"""
from __future__ import annotations

import os
import sys
import threading

from ..store.tasks import CheckpointConflict


def recover_or_init(svc) -> None:
    """启动恢复（原 __init__ 后半）：durable checkpoint 优先，state.pkl 次之，
    损坏隔离后空启动；L0 下界对齐；信号出口接到任务库。"""
    try:
        revision, checkpoint = svc.tasks.checkpoint()
    except Exception as exc:
        svc.tasks.close()
        svc.log.close()
        raise RuntimeError("durable checkpoint 无法读取；请恢复配套备份") from exc
    if checkpoint is not None:
        try:
            svc._load(checkpoint)
            svc._checkpoint_revision = revision
            svc._snapshot_status = "loaded"
            svc._state_bytes = len(checkpoint)   # N49：预算闸重启即生效
        except Exception as exc:
            svc.tasks.close()
            svc.log.close()
            raise RuntimeError("durable checkpoint 损坏；拒绝用旧 state.pkl 空启动，请恢复配套备份") from exc
    elif svc.state_path and svc.state_path.exists():
        try:
            svc._load()
            svc._snapshot_status = "loaded"
            svc._state_bytes = svc.state_path.stat().st_size  # N49：近似水位
        except Exception as exc:  # noqa: BLE001
            # 损坏/恶意 state 不能让 sidecar 启动即死（桥会整体瘫痪）：
            # 隔离坏文件后空启动，损失状态好过丢记忆服务。
            # 隔离标记在本进程内保持，随后的 save 不能把它洗成干净加载。
            svc._snapshot_quarantined = True
            svc._snapshot_status = "quarantined"
            corrupt = svc.state_path.with_suffix(".corrupt")
            try:
                os.replace(svc.state_path, corrupt)
            except OSError:
                pass
            print(f"[memory-sidecar] state.pkl 损坏已隔离为 "
                  f"{corrupt.name}（{exc}）——空启动",
                  file=sys.stderr, flush=True)
    elif corrupt_file_exists(svc):
        # 上次隔离后没有留下可加载快照。重启不能把丢失显示成合法空目录。
        svc._snapshot_quarantined = True
        svc._snapshot_status = "quarantined"
    # L0 每轮提交，快照只在 save/退出时更新：正常旧快照、缺快照或坏
    # 快照都可能落后于日志。快照提供下界，绝不能让已提交证据复用 id/t。
    next_id, next_t = svc.log.next_position()
    svc._unit_id = max(svc._unit_id, next_id)
    svc._t = max(svc._t, next_t)
    svc.engine._next_id = max(svc.engine._next_id, svc.tasks.memory_next_id())
    svc.engine.signals.on_emit = svc._journal_signal


def ensure_healthy(svc) -> None:
    if svc._checkpoint_fault:
        raise CheckpointConflict("checkpoint 状态不确定或已被其他实例推进；请重启服务")


def corrupt_file_exists(svc) -> bool:
    return bool(svc.state_path and svc.state_path.with_suffix(".corrupt").exists())


def save(svc) -> dict:
    if svc.state_path is None:
        return {"saved": False, "reason": "no state_dir"}
    with svc._lock:
        state = svc._dump_state()
        if svc._checkpoint_revision or svc.tasks.checkpoint()[0]:
            revision = svc._checkpoint_revision
            try:
                svc._checkpoint_revision = svc.tasks.save_checkpoint(state, revision)
            except BaseException:
                svc._check_checkpoint_error(revision)
                raise
        tmp = svc.state_path.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            f.write(state)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, svc.state_path)
        if not svc._snapshot_quarantined:
            svc._snapshot_status = "loaded"
    return {"saved": True, "mems": len(svc.engine.mems)}


def start_unit_recovery(svc) -> None:
    if svc._unit_thread is not None and svc._unit_thread.is_alive():
        return
    svc._unit_stop.clear()

    def loop():
        while not svc._unit_stop.is_set():
            for process in (svc.process_pending_units, svc.process_semantic_tasks):
                if svc._checkpoint_fault:
                    break  # 只可重启加载权威 checkpoint
                try:
                    process()
                except Exception as exc:  # noqa: BLE001  持久待办下一轮重试
                    print(f"[memory-sidecar] 恢复失败: {type(exc).__name__}: {exc}",
                          file=sys.stderr, flush=True)
            if svc._checkpoint_fault:
                break
            svc._unit_wake.wait(2)
            svc._unit_wake.clear()

    svc._unit_thread = threading.Thread(target=loop, name="memory-unit", daemon=True)
    svc._unit_thread.start()


def stop_unit_recovery(svc, timeout: float = 5.0) -> None:
    svc._unit_stop.set()
    svc._unit_wake.set()
    if svc._unit_thread is not None:
        svc._unit_thread.join(timeout)
