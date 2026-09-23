"""久坐提醒核心模块 —— 自包含、零第三方依赖、易移植。

本包只做一件事：根据「用户是否还在座位前（在场）」这一串随时间变化的信号，
判断用户是否已经连续久坐过久、需要起身活动。

移植时你只需替换「在场信号」的来源（人脸检测 / 键鼠活动 / 座椅压力传感器……），
核心逻辑 ``SedentaryTracker`` 无需改动。
"""

from .tracker import SedentaryTracker
from .types import PresenceState

__all__ = ["SedentaryTracker", "PresenceState"]
__version__ = "1.0.0"