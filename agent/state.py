"""情绪状态的时序平滑。

单句结果会抖：同一句话连说三次可能 happy/sad/happy。直接按句换表情会显得
神经质。这里做两件事：
- 概率 EMA，压掉单句噪声；
- 标签滞回，新标签要连续赢两次或明显领先才切过去。

矛盾场景不走平滑：它是 demo 的记忆点，必须立刻响应，所以 conflict 直接透传。
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from perception.types import FusionResult, LABEL7, normalize_probs


class EmotionStateTracker:
    def __init__(self, alpha: float = 0.35, switch_margin: float = 0.08,
                 confirm_events: int = 2):
        self.alpha = alpha
        self.switch_margin = switch_margin
        self.confirm_events = confirm_events
        self.ema: dict[str, float] | None = None
        self.label: str | None = None
        self._pending: str | None = None
        self._pending_n = 0

    def reset(self):
        self.ema = None
        self.label = None
        self._pending, self._pending_n = None, 0

    def update(self, fusion: FusionResult) -> FusionResult:
        if fusion.conflict:
            self.ema = dict(fusion.probs)
            self.label = fusion.label
            self._pending, self._pending_n = None, 0
            return fusion

        p = {k: float(fusion.probs.get(k, 0.0)) for k in LABEL7}
        if self.ema is None:
            self.ema = p
        else:
            # 高置信度的新证据要能快速推翻旧状态，否则连续说三种情绪时表情会卡住
            a = max(self.alpha, 0.75) if max(p.values()) >= 0.6 else self.alpha
            self.ema = {k: a * p[k] + (1 - a) * self.ema[k] for k in LABEL7}

        new = max(self.ema, key=self.ema.get)
        if self.label is None:
            self.label = new
        elif new != self.label:
            lead = self.ema[new] - self.ema.get(self.label, 0.0)
            if lead >= self.switch_margin:
                self.label = new
                self._pending, self._pending_n = None, 0
            else:
                if new == self._pending:
                    self._pending_n += 1
                else:
                    self._pending, self._pending_n = new, 1
                if self._pending_n >= self.confirm_events:
                    self.label = new
                    self._pending, self._pending_n = None, 0

        probs = normalize_probs(self.ema)
        conf = float(probs[self.label]) * (0.9 ** len(fusion.missing))
        return replace(fusion, probs=probs, label=self.label, confidence=conf)

    @property
    def smoothed(self) -> np.ndarray:
        if self.ema is None:
            return np.full(len(LABEL7), 1.0 / len(LABEL7))
        return np.array([self.ema[k] for k in LABEL7])
