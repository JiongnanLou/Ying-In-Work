"""在场状态枚举。

用于表达「用户当前是否在屏幕前 / 是否盯着屏幕」。
- PRESENT：在场（检测到用户，近似“正在看屏幕”）
- AWAY   ：离场
- UNKNOWN：无法判断（例如信号源尚未就绪）
"""

from enum import Enum


class PresenceState(str, Enum):
    PRESENT = "present"
    AWAY = "away"
    UNKNOWN = "unknown"