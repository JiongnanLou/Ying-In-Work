"""眼部疲劳检测核心类。

大脑模型（一段话看懂）：
    把时间切成一段段等长的“检测间隔”（默认 5 分钟）。每个间隔结束时看一眼：
    这段时间里用户「在场（盯着屏幕）」的比例够不够高？够 → 记 1 次“持续盯屏”；
    不够（说明中途离开过）→ 计数清零。当“持续盯屏”连续攒满 N 次（默认 10 次）
    也就是 5 分钟 × 10 = 50 分钟，就触发一次提醒。

    这样设计的两个好处：
      1. 用“间隔内比例”而不是“某一瞬间”，人短暂回头/眨眼不会误判成离场；
      2. 必须“连续”积满 N 次，中间真的走开了就从头来，真正贴合“连续盯屏”。

对移植者的要求只有一个：定期（如每 0.2~1 秒）调用 ``update(presence, timestamp)``，
告诉它“此刻是否在场”和“当前时间戳”。它返回 True 时，你就弹提醒。
"""

from __future__ import annotations

from .types import PresenceState


class EyeFatigueTracker:
    """按「检测间隔 × 连续次数」检测连续注视导致的眼部疲劳。

    参数
    ----
    interval_seconds : float
        每个检测周期的时长（秒），默认 300（即 5 分钟）。
    required_cycles : int
        需要连续多少个周期都被判为“在场”才提醒，默认 10。
        也即默认总时长 = 300 × 10 = 3000 秒 = 50 分钟。
    presence_ratio : float
        单个周期内「在场时长占比」达到该值才判为该周期“盯着屏幕”，默认 0.5。

    """

    def __init__(
        self,
        interval_seconds: float = 300.0,
        required_cycles: int = 10,
        presence_ratio: float = 0.5,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds 必须大于 0")
        if required_cycles <= 0:
            raise ValueError("required_cycles 必须大于 0")
        self.interval_seconds = float(interval_seconds)
        self.required_cycles = int(required_cycles)
        self.presence_ratio = float(presence_ratio)

        self.consecutive_cycles = 0        # 当前已连续积攒的“盯屏”周期数
        self.alerted = False               # 是否已触发提醒（等待用户处理后 reset）
        self._cycle_elapsed = 0.0          # 当前周期已累计的真实时间
        self._cycle_present = 0.0          # 当前周期内“在场”的累计时间
        self._last_timestamp: float | None = None

    # ------------------------------------------------------------------ 区间属性
    @property
    def threshold_seconds(self) -> float:
        """触发提醒的等效总时长（间隔 × 次数），用于展示。"""
        return self.interval_seconds * self.required_cycles

    @property
    def progress_ratio(self) -> float:
        """当前连续进度（0.0~1.0），用于进度条/百分比展示。"""
        return min(1.0, self.consecutive_cycles / self.required_cycles)

    # ------------------------------------------------------------------ 核心接口
    def update(self, presence, timestamp: float) -> bool:
        """喂入一次观测；若应当触发提醒则返回 True。

        参数
        ----
        presence : bool | str | PresenceState
            是否在场。接受 ``True`` / ``False``、``PresenceState.PRESENT`` /
            ``PresenceState.AWAY`` / ``PresenceState.UNKNOWN``，或字符串
            ``"present"`` / ``"away"`` / ``"unknown"``。非 PRESENT 一律按离场处理。
        timestamp : float
            本次观测的时间戳（秒）。用单调时钟（如 ``time.monotonic()``）最佳，
            避免系统改时间造成跳变。

        返回
        ----
        bool
            True 表示刚刚跨过阈值、应当提醒一次；其余情况返回 False。
        """
        if self._last_timestamp is None:
            self._last_timestamp = timestamp
            return False

        delta = timestamp - self._last_timestamp
        self._last_timestamp = timestamp

        # 时间跳变（时钟回拨、信号源暂停导致的大间隔）不计入，避免误判。
        if delta < 0.0 or delta > self.interval_seconds * 2.0:
            return False

        self._cycle_elapsed += delta
        if self._is_present(presence):
            self._cycle_present += delta

        # 周期还没满，继续等待。
        if self._cycle_elapsed < self.interval_seconds:
            return False

        # 一个周期结束：判定本周期是否“盯着屏幕”。
        ratio = self._cycle_present / self._cycle_elapsed if self._cycle_elapsed > 0 else 0.0
        if ratio >= self.presence_ratio:
            if not self.alerted:
                self.consecutive_cycles += 1
        else:
            self.consecutive_cycles = 0

        # 进入下一周期。
        self._cycle_elapsed = 0.0
        self._cycle_present = 0.0

        if not self.alerted and self.consecutive_cycles >= self.required_cycles:
            self.alerted = True
            return True
        return False

    def reset(self) -> None:
        """重置本轮检测（用户选择忽略 / 休息之后的回调里调用）。"""
        self.consecutive_cycles = 0
        self.alerted = False
        self._cycle_elapsed = 0.0
        self._cycle_present = 0.0
        self._last_timestamp = None

    # 兼容旧调用名。
    def dismiss(self) -> None:
        self.reset()

    # ------------------------------------------------------------------ 内部
    @staticmethod
    def _is_present(presence) -> bool:
        """把各种「在场」表达统一转成布尔。"""
        if presence is True:
            return True
        try:
            return presence == PresenceState.PRESENT
        except Exception:
            return False