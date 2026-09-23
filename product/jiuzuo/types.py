"""在场状态枚举。

用于表达「用户当前是否还在座位上 / 是否仍在使用电脑」。
- PRESENT：在场（检测到用户仍坐着 / 仍在使用）
- AWAY   ：离场（用户已经起身离开）
- UNKNOWN：无法判断（例如信号源尚未就绪）
"""

from enum import Enum


class PresenceState(str, Enum):
    PRESENT = "present"
    AWAY = "away"
    UNKNOWN = "unknown"