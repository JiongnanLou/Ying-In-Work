"""久坐检测核心类。

大脑模型（一段话看懂）：
    持续累加“用户在座”的时间；一旦检测到用户离场（起身走了），累加立刻清零。
    当“连续在座”时间攒满阈值（默认 60 分钟），就触发一次提醒，让用户起来活动。

    与“眼部疲劳检测”的区别：
    - 眼部疲劳：用“周期 + 周期内比例”容错，允许短暂回头/眨眼；
    - 久坐：更严格，要求**连续不中断**——只要离开座位，就从头计算，
      真正表达“连续坐着”。

对移植者的要求只有一个：定期（如每 0.2~1 秒）调用 ``update(presence, timestamp)``，
告诉它“此刻是否还在座位上”和“当前时间戳”。它返回 True 时，你就弹提醒。
"""

from __future__ import annotations

from .types import PresenceState


class SedentaryTracker:
    """按“连续在场时长”检测久坐，达阈值触发提醒。

    参数
    ----
    threshold_seconds : float
        连续在座达到该时长（秒）才提醒，默认 3600（即 60 分钟 = 1 小时）。
    """

    def __init__(self, threshold_seconds: float = 60.0 * 60.0) -> None:
        if threshold_seconds <= 0:
            raise ValueError("threshold_seconds 必须大于 0")
        self.threshold_seconds = float(threshold_seconds)
        self.accumulated_seconds = 0.0
        self.alerted = False
        self._last_timestamp: float | None = None

    # ------------------------------------------------------------------ 只读
    @property
    def progress_ratio(self) -> float:
        """当前久坐进度（0.0~1.0），用于进度条/百分比展示。"""
        return min(1.0, self.accumulated_seconds / self.threshold_seconds)

    # ------------------------------------------------------------------ 核心
    def update(self, presence, timestamp: float) -> bool:
        """喂入一次观测；若应当触发提醒则返回 True。

        参数
        ----
        presence : bool | str | PresenceState
            是否在场。接受 ``True`` / ``False``、``PresenceState.PRESENT`` /
            ``PresenceState.AWAY`` / ``PresenceState.UNKNOWN``，或字符串
            ``"present"`` / ``"away"`` / ``"unknown"``。非 PRESENT 一律按离场处理。
        timestamp : float
            本次观测的时间戳（秒）。用单调时钟（如 ``time.monotonic()``）最佳。

        返回
        ----
        bool
            True 表示刚刚跨过阈值、应当提醒一次；其余返回 False。
        """
        if self._last_timestamp is None:
            self._last_timestamp = timestamp
            return False

        delta = timestamp - self._last_timestamp
        self._last_timestamp = timestamp

        # 时间跳变（时钟回拨、信号源暂停导致的大间隔）不计入，避免误报。
        if delta < 0.0 or delta > 30.0:
            return False

        # 离场（起身）：立即清零，从头计算。
        if not self._is_present(presence):
            self.alerted = False
            self.accumulated_seconds = 0.0
            return False

        if self.alerted:
            return False

        self.accumulated_seconds += delta
        if self.accumulated_seconds >= self.threshold_seconds:
            self.alerted = True
            return True
        return False

    def reset(self) -> None:
        """重置本轮检测（用户选择忽略 / 已起身活动后调用）。"""
        self.accumulated_seconds = 0.0
        self.alerted = False
        self._last_timestamp = None

    # 兼容旧调用名。
    def dismiss(self) -> None:
        self.reset()

    # ------------------------------------------------------------------ 内部
    @staticmethod
    def _is_present(presence) -> bool:
        if presence is True:
            return True
        try:
            return presence == PresenceState.PRESENT
        except Exception:
            return False