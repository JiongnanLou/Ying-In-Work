"""眼部疲劳检测核心模块 —— 自包含、零第三方依赖、易移植。

本包只做一件事：根据「是否正在盯着屏幕（在场）」这一串随时间变化的信号，
判断用户是否已经连续注视过久、需要休息。

移植时你只需替换「在场信号」的来源（人脸检测 / 键鼠活动 / 传感器……），
核心逻辑 ``EyeFatigueTracker`` 无需改动。
"""

from .tracker import EyeFatigueTracker
from .types import PresenceState

__all__ = ["EyeFatigueTracker", "PresenceState"]
__version__ = "1.0.0"