"""人工标定的原始角度库。与归一化预设分开，不重复施加中心补偿。"""
import copy
import hashlib
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from head.actuators import BY_NAME, center

LABELS = ("neutral", "happy", "sad", "angry", "fear", "disgust", "surprise")
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "calibration" / "expressions.json"


class PoseError(ValueError):
    pass


def label_key(label):
    label = "surprise" if label == "surprised" else label
    if label not in LABELS:
        raise PoseError(f"未知情绪标签：{label}")
    return label


def number(value, name, lo, hi):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise PoseError(f"{name} 必须是有限数值")
    if not lo <= value <= hi:
        raise PoseError(f"{name} 需要在 {lo:g}–{hi:g} 之间")
    return float(value)


def validate_angles(angles):
    if not isinstance(angles, dict) or not angles:
        raise PoseError("姿态不能为空")
    out = {}
    for n, value in sorted(angles.items()):
        if n not in BY_NAME or n == "EXA":
            raise PoseError(f"不能驱动通道：{n}")
        a = BY_NAME[n]
        out[n] = number(value, n, min(a.a, a.b), max(a.a, a.b))
    jaws = {"JL", "JR"} & out.keys()
    if jaws and (len(jaws) != 2 or abs(out["JL"] + out["JR"] - 180) > 5):
        raise PoseError("下巴必须成对保存，JL + JR 与 180° 的偏差不能超过 5°")
    return out


def context_key():
    config = {n: [a.board, a.pin, a.a, a.b, center(n)] for n, a in sorted(BY_NAME.items())}
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def baseline_key(angles):
    return hashlib.sha256(json.dumps(angles, sort_keys=True).encode()).hexdigest()


class PoseLibrary:
    def __init__(self, path=DEFAULT_PATH, mode="hardware"):
        self.path, self.mode = Path(path), mode
        self.data = self._read()

    def _read(self):
        if not self.path.exists():
            return {"schema_version": 1, "revision": 0, "mode": self.mode, "poses": {}}
        try:
            data = json.loads(self.path.read_text())
            if (data["schema_version"] != 1 or data["mode"] != self.mode
                    or type(data["revision"]) is not int or data["revision"] < 0
                    or not isinstance(data["poses"], dict)):
                raise ValueError("版本、运行模式或结构不匹配")
            for label, pose in data["poses"].items():
                if label_key(label) != label:
                    raise ValueError("文件内标签必须使用 surprise")
                validate_angles(pose["angles"])
                if not all(isinstance(pose[k], str) for k in ("title", "text", "saved_at", "context", "baseline")):
                    raise ValueError("姿态元数据无效")
            return data
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            raise PoseError(f"表情库无法读取 {self.path}：{e}；请修复文件后重启") from e

    def export(self):
        return copy.deepcopy(self.data)

    def problem(self, label):
        pose, neutral = self.data["poses"].get(label), self.data["poses"].get("neutral")
        if pose is None:
            return "未标定"
        if neutral is None:
            return "请先保存 neutral"
        if pose["context"] != context_key() or neutral["context"] != context_key():
            return "中心或硬件配置已改变，请重新标定"
        if (pose["baseline"] != baseline_key(neutral["angles"])
                or set(pose["angles"]) != set(neutral["angles"])):
            return "neutral 已改变，请重新保存此表情"
        return ""

    def summary(self):
        return {"path": str(self.path), "revision": self.data["revision"],
                "labels": [{"label": label, "problem": self.problem(label),
                            "pose": copy.deepcopy(self.data["poses"].get(label))} for label in LABELS]}

    def save(self, label, angles, title, text, revision):
        label = label_key(label)
        angles = validate_angles(angles)
        if not isinstance(title, str) or not isinstance(text, str) or len(title) > 80 or len(text) > 2000:
            raise PoseError("名称最多 80 字，说明最多 2000 字")
        if type(revision) is not int or revision != self.data["revision"]:
            raise PoseError("表情库已更新，请刷新后再保存")
        if label != "neutral":
            if self.problem("neutral"):
                raise PoseError("请先保存有效的 neutral 基准")
            base = self.data["poses"]["neutral"]["angles"]
            if set(angles) != set(base):
                raise PoseError("通电通道必须与 neutral 完全一致；先重放 neutral 再调姿态")
        else:
            base = angles
        updated = self.export()
        updated["revision"] += 1
        updated["poses"][label] = {"title": title.strip() or label, "text": text.strip(),
                                   "angles": angles, "context": context_key(),
                                   "baseline": baseline_key(base),
                                   "saved_at": datetime.now(timezone.utc).isoformat()}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # 同一文件的多个进程不得用旧副本覆盖新标定；写失败保留原文件。
        import fcntl
        with self.path.with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if self._read() != self.data:
                raise PoseError("磁盘表情库已被其他进程修改，请重启后再保存")
            temp = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", dir=self.path.parent, delete=False, suffix=".tmp") as f:
                    temp = f.name
                    json.dump(updated, f, ensure_ascii=False, indent=2, allow_nan=False)
                    f.write("\n")
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp, self.path)
            finally:
                if temp and os.path.exists(temp):
                    os.unlink(temp)
        self.data = updated
        return copy.deepcopy(updated["poses"][label])

    def resolve(self, label, intensity=1.0):
        label = label_key(label)
        intensity = number(intensity, "强度", 0, 1)
        problem = self.problem(label)
        if problem:
            raise PoseError(f"{label}：{problem}")
        neutral = self.data["poses"]["neutral"]["angles"]
        pose = self.data["poses"][label]["angles"]
        return validate_angles({n: round(v + intensity * (pose[n] - v), 3) for n, v in neutral.items()})
