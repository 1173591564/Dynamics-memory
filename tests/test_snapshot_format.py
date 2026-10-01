"""Pool 快照的跨枚举编码兼容；拒绝将旧 getattr 编码变成通用反射入口。"""
import io
import pickle

import pytest

from hybrid_memory.core.types import Pool
from hybrid_memory.server import _RestrictedUnpickler


class _ByName:
    def __init__(self, cls, name):
        self.cls, self.name = cls, name

    def __reduce__(self):
        return getattr, (self.cls, self.name)


class _ByValue:
    def __init__(self, value):
        self.value = value

    def __reduce__(self):
        return Pool, (self.value,)


@pytest.mark.parametrize("protocol", [2, 4, 5])
@pytest.mark.parametrize("member", list(Pool))
def test_pool_writes_stable_value_encoding(protocol, member):
    data = pickle.dumps(member, protocol=protocol)
    assert b"getattr" not in data
    assert _RestrictedUnpickler(io.BytesIO(data)).load() is member


@pytest.mark.parametrize("member", list(Pool))
def test_legacy_pool_name_and_value_encodings_are_readable(member):
    for value in (_ByName(Pool, member.name), _ByValue(member.value)):
        data = pickle.dumps(value, protocol=4)
        assert _RestrictedUnpickler(io.BytesIO(data)).load() is member


@pytest.mark.parametrize("cls,name", [
    (Pool, "__class__"), (Pool, "__members__"), (Pool, "NOT_A_POOL"),
    (str, "__mro__"), (object, "__subclasses__"),
])
def test_legacy_getattr_adapter_rejects_non_pool_member_access(cls, name):
    data = pickle.dumps(_ByName(cls, name), protocol=4)
    with pytest.raises(pickle.UnpicklingError):
        _RestrictedUnpickler(io.BytesIO(data)).load()
