"""持久化、重启与失效规则；只写 pytest 临时目录。"""
import json

import pytest

from head.actuators import CENTERS
from head.pose_library import PoseError, PoseLibrary


@pytest.fixture
def library(tmp_path):
    return PoseLibrary(tmp_path / "expressions.json", mode="sim")


def save(library, label, angles):
    return library.save(label, angles, label, "人工调试", library.data["revision"])


def test_restart_restores_poses_and_interpolates_raw_angles(library):
    save(library, "neutral", {"UD": 120, "TON": 90})
    save(library, "happy", {"UD": 130, "TON": 110})
    restarted = PoseLibrary(library.path, mode="sim")
    assert restarted.resolve("happy", 0.5) == {"UD": 125, "TON": 100}
    assert restarted.resolve("happy", 0) == restarted.resolve("neutral")
    assert restarted.summary()["revision"] == 2


def test_requires_neutral_and_exact_channel_set(library):
    with pytest.raises(PoseError, match="neutral"):
        save(library, "happy", {"TON": 100})
    save(library, "neutral", {"TON": 90, "LR": 90})
    with pytest.raises(PoseError, match="通电通道"):
        save(library, "happy", {"TON": 100})
    with pytest.raises(PoseError, match="未标定"):
        library.resolve("fear")


def test_neutral_change_invalidates_other_labels_until_resaved(library):
    save(library, "neutral", {"TON": 90})
    save(library, "happy", {"TON": 100})
    save(library, "neutral", {"TON": 90})
    assert library.resolve("happy") == {"TON": 100}
    save(library, "neutral", {"TON": 95})
    with pytest.raises(PoseError, match="neutral 已改变"):
        library.resolve("happy")
    save(library, "happy", {"TON": 100})
    assert library.resolve("happy", 0.5) == {"TON": 97.5}


def test_center_change_invalidates_saved_commands(library, monkeypatch):
    save(library, "neutral", {"UD": 120})
    monkeypatch.setitem(CENTERS, "UD", 121)
    with pytest.raises(PoseError, match="配置已改变"):
        library.resolve("neutral")


@pytest.mark.parametrize("angles", [{}, {"EXA": 90}, {"BOGUS": 90}, {"TON": -1},
                                    {"TON": float("nan")}, {"TON": float("inf")}, {"TON": True},
                                    {"JL": 90}, {"JL": 50, "JR": 120}])
def test_invalid_pose_never_writes_file(library, angles):
    with pytest.raises(PoseError):
        save(library, "neutral", angles)
    assert not library.path.exists()


def test_surprised_alias_and_invalid_intensity(library):
    save(library, "neutral", {"TON": 90})
    save(library, "surprised", {"TON": 95})
    assert "surprise" in library.data["poses"]
    assert library.resolve("surprised") == library.resolve("surprise")
    for intensity in (-0.1, 1.1, None, float("nan"), True):
        with pytest.raises(PoseError):
            library.resolve("surprise", intensity)


def test_failed_atomic_replace_preserves_previous_revision(library, monkeypatch):
    save(library, "neutral", {"TON": 90})
    original = library.path.read_bytes()
    def fail(*args):
        raise OSError("disk full")
    monkeypatch.setattr("head.pose_library.os.replace", fail)
    with pytest.raises(OSError):
        save(library, "happy", {"TON": 100})
    assert library.path.read_bytes() == original
    assert library.data["revision"] == 1
    assert not list(library.path.parent.glob("*.tmp"))


def test_stale_client_and_external_edit_are_not_overwritten(library):
    save(library, "neutral", {"TON": 90})
    other = PoseLibrary(library.path, mode="sim")
    save(library, "happy", {"TON": 100})
    with pytest.raises(PoseError, match="刷新"):
        library.save("sad", {"TON": 80}, "", "", 1)
    with pytest.raises(PoseError, match="其他进程"):
        save(other, "sad", {"TON": 80})
    assert "happy" in json.loads(library.path.read_text())["poses"]


def test_simulation_library_cannot_be_used_on_hardware(library):
    save(library, "neutral", {"TON": 90})
    with pytest.raises(PoseError, match="运行模式"):
        PoseLibrary(library.path, mode="hardware")


def test_corrupted_library_is_not_silently_discarded(library):
    library.path.write_text('{"schema_version": 1, "poses":')
    with pytest.raises(PoseError, match="无法读取"):
        PoseLibrary(library.path, mode="sim")
