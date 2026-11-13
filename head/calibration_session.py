"""手动标定会话：最新目标、低速插值、连接租约，以及独立的位置记录。

所有串口操作仍由 Bench 的同一把锁和连接完成；角度读回不是物理位置反馈。
"""
import copy
import json
import os
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from head.actuators import BY_NAME
from head.pose_library import PoseError, context_key, number, validate_angles


class PositionBook:
    def __init__(self, path, mode):
        self.path, self.mode = Path(path), mode
        self.data = self._read()

    def _read(self):
        if not self.path.exists():
            return {"schema_version": 1, "mode": self.mode, "records": []}
        try:
            data = json.loads(self.path.read_text())
            if data["schema_version"] != 1 or data["mode"] != self.mode or not isinstance(data["records"], list):
                raise ValueError("版本或模式不匹配")
            for record in data["records"]:
                validate_angles(record["angles"])
                observations(record["observations"])
                if (not isinstance(record["directions"], dict)
                        or any(n not in record["angles"] or not isinstance(v, str)
                               for n, v in record["directions"].items())):
                    raise ValueError("方向记录无效")
                for key in ("id", "name", "kind", "context", "saved_at"):
                    if not isinstance(record[key], str):
                        raise ValueError("无效记录")
            return data
        except (ValueError, KeyError, TypeError) as e:
            raise PoseError(f"位置记录无法读取 {self.path}：{e}") from e

    def export(self):
        return copy.deepcopy(self.data)

    def append(self, record):
        import fcntl
        updated = self.export()
        updated["records"].append(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if self._read() != self.data:
                raise PoseError("位置记录已被另一进程修改，请重启后再保存")
            temp = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", dir=self.path.parent, delete=False) as f:
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


def observations(value):
    if not isinstance(value, dict) or set(value) != {"reached", "buzz", "jitter", "heat", "text"}:
        raise PoseError("请记录到位、声音、抖动和发热情况")
    if any(value[k] not in ("yes", "no", "unknown") for k in ("reached", "buzz", "jitter", "heat")):
        raise PoseError("观察值无效")
    if not isinstance(value["text"], str) or len(value["text"]) > 2000:
        raise PoseError("备注最多 2000 字")
    return dict(value)


class CalibrationControls:
    CAL_TICK = 0.1
    CAL_LEASE = 5.0

    def _init_calibration(self, path):
        self.positions = PositionBook(path, self.mode)
        self.cal = None
        self.last_cal = None
        self.cal_epoch = 0
        self.cal_message = "选择电机，点击通电并手动调节后即可使用滑块"

    def _cal_session(self, token):
        if not self.cal or token != self.cal["token"] or self.stop.is_set():
            raise PoseError("标定会话已结束，请重新点击通电并手动调节")
        if time.monotonic() >= min(self.cal["lease"], self.cal["deadline"]):
            raise PoseError("标定会话已超时，等待卸力后重新开始")
        return self.cal

    def _cal_goal(self, angles):
        goal = validate_angles(angles)
        self._check_enabled(goal)
        self._check_ranges(goal)
        if any(BY_NAME[n].board not in self.links for n in goal):
            raise PoseError("所选电机的控制板未连接")
        return goal

    def _cal_release(self):
        errors = []
        for board in list(self.links):
            try:
                if self._ask(board, "X") != "OK":
                    errors.append(f"{board} 未确认卸力")
            except Exception as e:
                errors.append(str(e))
        self.powered.clear()
        self.held.clear()
        if errors:
            raise PoseError("；".join(errors) + "；请断开舵机 5V")

    def cal_begin(self, names, duration=15, epoch=None, manual=False):
        duration = number(duration, "90° 检查时长", 1, 30)
        if type(manual) is not bool:
            raise PoseError("manual 必须是布尔值")
        if not isinstance(names, list) or not names or len(names) != len(set(names)):
            raise PoseError("请选择一个、一对或一组电机")
        with self.lock:
            if epoch is not None and (type(epoch) is not int or epoch != self.cal_epoch):
                raise PoseError("控制状态已改变，已取消过期的通电请求")
            if self._busy() or self.powered or self.held:
                raise PoseError("请先全部卸力，再开始新的标定会话")
            # 先检查通道身份；手动模式不要求先经过 90°，也不套用中心补偿。
            selected = validate_angles({n: 90 for n in names})
            self._check_enabled(selected)
            # 所有通道与板子预检完成后才发送任何输出。
            boards = sorted({BY_NAME[n].board for n in selected})
            if any(board not in self.links for board in boards):
                raise PoseError("所选电机的控制板未连接")
            for board in boards:
                self._read(board)
            goal = self._cal_goal({n: self.angles[n] if manual else 90 for n in selected})
            try:
                self._cal_release()
                for board in boards:
                    part = [n for n in goal if BY_NAME[n].board == board]
                    if manual:
                        if self._ask(board, "V 10") != "OK":
                            raise PoseError(f"{board} 未接受速度限制")
                        line = "S " + " ".join(f"{n}={goal[n]:g}" for n in part)
                    else:
                        line = "O " + " ".join(part)
                    if self._ask(board, line) != "OK":
                        raise PoseError(f"{board} 未接受通电命令")
                    self.powered.update(part)
                    self._read(board)
                    self._record("cmd", board=board, cmd=line,
                                 reply="当前指令角度通电，手动调节" if manual else "90° 检查，实际到位待人工观察")
                now = time.monotonic()
                self.cal = {"token": uuid.uuid4().hex, "names": sorted(goal), "phase": "range" if manual else "center",
                            "goal": goal, "seq": -1, "speed": 5.0,
                            "lease": now + self.CAL_LEASE, "deadline": now + (900 if manual else duration)}
                self.cal_epoch += 1
                self.stop.clear()
                self.error = ""
                self.cal_message = ("手动调节中；可直接拖动滑块，观察结果另行记录" if manual
                                    else "90° 已发送；可转为手动调节，倒计时结束自动卸力")
                self.job = threading.Thread(target=self._cal_loop, args=(self.cal["token"],), daemon=True)
                self.job.start()
            except Exception:
                self._cal_release()
                self.cal = None
                raise

    def cal_touch(self, token):
        with self.lock:
            session = self._cal_session(token)
            session["lease"] = time.monotonic() + self.CAL_LEASE

    def cal_stop(self, token):
        # 关闭旧标签页时不能卸掉另一个页面后来开启的新会话。
        with self.lock:
            if not self.cal or token != self.cal["token"]:
                raise PoseError("此标定会话已结束")
            self.stop.set()
            self.cal_epoch += 1
            self._cal_release()

    def cal_target(self, token, seq, angles, speed=5):
        speed = number(speed, "探索速度", 5, 30)
        with self.lock:
            session = self._cal_session(token)
            if session["phase"] != "range":
                raise PoseError("当前是限时 90° 检查，请点击转为手动调节")
            if type(seq) is not int or seq <= session["seq"]:
                raise PoseError("已丢弃过期的滑块指令")
            goal = self._cal_goal(angles)
            if set(goal) != set(session["names"]):
                raise PoseError("目标通道必须与本次选择完全一致")
            session.update(goal=goal, seq=seq, speed=speed)
            session["lease"] = time.monotonic() + self.CAL_LEASE

    def _cal_loop(self, token):
        reason = "已全部卸力"
        try:
            while not self.stop.wait(self.CAL_TICK):
                with self.lock:
                    if not self.cal or self.cal["token"] != token or self.stop.is_set():
                        break
                    session = self.cal
                    now = time.monotonic()
                    if now >= session["lease"] or now >= session["deadline"]:
                        reason = "连接或观察计时结束，已自动卸力"
                        break
                    boards = sorted({BY_NAME[n].board for n in session["names"]})
                    for board in boards:
                        self._read(board)
                    if session["phase"] == "center":
                        continue
                    goal = self._cal_goal(session["goal"])
                    current = validate_angles({n: self.angles[n] for n in goal})
                    distance = max(abs(goal[n] - current[n]) for n in goal)
                    if distance < 0.05:
                        continue
                    # 一次最多 3°；按统一比例插值，保留下巴配对关系。
                    ratio = min(1, session["speed"] * self.CAL_TICK / distance)
                    step = self._cal_goal({n: round(current[n] + (v - current[n]) * ratio, 2)
                                           for n, v in goal.items()})
                    for board in boards:
                        if self.stop.is_set():
                            break
                        if self._ask(board, f"V {max(10, session['speed']):g}") != "OK":
                            raise PoseError(f"{board} 未接受速度限制")
                        line = "S " + " ".join(f"{n}={v:g}" for n, v in step.items() if BY_NAME[n].board == board)
                        if self._ask(board, line) != "OK":
                            raise PoseError(f"{board} 未接受位置命令")
                        self._record("cmd", board=board, cmd=line, reply="低速探索", speed=session["speed"])
        except Exception as e:
            self.error = str(e)
            reason = f"探索已中止：{e}"
        finally:
            with self.lock:
                if self.cal and self.cal["token"] == token:
                    self.last_cal = {"token": token, "names": list(self.cal["names"]),
                                     "angles": {n: self.angles[n] for n in self.cal["names"]},
                                     "ended_at": datetime.now(timezone.utc).isoformat()}
                try:
                    self._cal_release()
                except Exception as e:
                    self.error = str(e)
                    reason = self.error
                self.cal = None
                self.cal_epoch += 1
                self.cal_message = reason
                self._record("cal_session_end", reason=reason)

    def _cal_at_goal(self):
        return self.cal is not None and all(abs(self.angles[n] - v) <= 0.2 for n, v in self.cal["goal"].items())

    def _cal_capture(self, name, kind, observation, directions, previous=None):
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise PoseError("请填写位置名称，最多 80 字")
        if kind not in ("center", "position", "lower", "upper"):
            raise PoseError("记录类型无效")
        observation = observations(observation)
        source = previous or self.cal
        if (not isinstance(directions, dict) or set(directions) - set(source["names"])
                or any(not isinstance(v, str) or len(v) > 120 for v in directions.values())):
            raise PoseError("方向说明无效")
        if not previous:
            for board in {BY_NAME[n].board for n in self.cal["names"]}:
                self._read(board)
            if not self._cal_at_goal():
                raise PoseError("软件角度还未到达目标，请等待后再记录")
        angles = previous["angles"] if previous else {n: self.angles[n] for n in self.cal["names"]}
        record = {"id": uuid.uuid4().hex, "name": name.strip(), "kind": kind,
                  "angles": validate_angles(angles),
                  "observations": observation, "directions": directions,
                  "context": context_key(), "saved_at": datetime.now(timezone.utc).isoformat(),
                  "source": "last_controller_state" if previous else "controller_command_state",
                  "session": source["token"], "ended_at": previous["ended_at"] if previous else None}
        self.positions.append(record)
        self._record("cal_capture", record=record)

    def cal_capture(self, token, name, observation, directions=None, kind="position"):
        with self.lock:
            if not self.cal and self.last_cal and token == self.last_cal["token"]:
                self._cal_capture(name, kind, observation, directions or {}, previous=self.last_cal)
            else:
                self._cal_session(token)
                self._cal_capture(name, kind, observation, directions or {})

    def cal_range(self, token, observation=None):
        if observation is not None:
            observation = observations(observation)
        with self.lock:
            session = self._cal_session(token)
            if session["phase"] != "center":
                raise PoseError("当前已经进入范围探索")
            # 人工观察是记录，不是手动调节的解锁条件；兼容旧客户端附带记录。
            if observation is not None:
                title = "90° 检查 · " + "/".join(session["names"])
                self._cal_capture(title[:80], "center", observation, {})
            session["phase"] = "range"
            session["deadline"] = time.monotonic() + 900
            session["lease"] = time.monotonic() + self.CAL_LEASE
            self.cal_message = "手动调节中；按 Esc 随时卸力"

    def cal_restore(self, token, record_id, seq, speed=5):
        with self.lock:
            self._cal_session(token)
            record = next((r for r in self.positions.data["records"] if r["id"] == record_id), None)
            if not record or record["context"] != context_key():
                raise PoseError("记录不存在，或硬件/中心配置已改变")
            goal = dict(record["angles"])
        self.cal_target(token, seq, goal, speed)

    def calibration_state(self):
        session = None
        if self.cal:
            session = {k: copy.deepcopy(v) for k, v in self.cal.items() if k not in ("lease", "deadline")}
            session["remaining"] = round(max(0, self.cal["deadline"] - time.monotonic()), 1)
            session["at_goal"] = self._cal_at_goal()
        return {"session": session, "last_session": copy.deepcopy(self.last_cal),
                "epoch": self.cal_epoch, "message": self.cal_message,
                "records": copy.deepcopy(self.positions.data["records"][-100:])}
