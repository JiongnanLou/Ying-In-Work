"""眼部米字操（Eye MiZiCao）—— 云台眼部放松动作序列生成器。

零依赖、纯 Python 标准库（仅用到 math 与 dataclasses）。

把「引导用户做眼部放松操」抽象为一系列标准化的云台（PTZ）**目标位置 + 停留时长**。
本模块不绑定任何相机 / 云台品牌，只负责「算出动作序列」这一件事。
将它移植到你的项目只需两步：

    1. 按你的设备改一下顶部的「方向映射」与「机械限位」常量（已集中标注）；
    2. 遍历动作序列，把每个步骤下发给你的云台控制接口。

设计原理详见同目录 README.md。
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Point:
    """云台绝对位置，单位：度（°）。"""

    pan: float    # 水平旋转角度（左 / 右）
    tilt: float   # 垂直俯仰角度（上 / 下）


@dataclass(frozen=True, slots=True)
class Step:
    """一个动作步骤：把云台移动到 point，并停留 hold_seconds 秒。"""

    point: Point
    hold_seconds: float


# =====================================================================
#  下面这些常量是「移植时需要你按自己的设备调整」的部分，已集中在这里。
# =====================================================================

# 每个方向的目标幅度（度）。米字的八个方向 + 转圈都基于它。
AMPLITUDE_DEGREES = 60.0

# 机械 / 安全限位（度）。动作会被钳制在该范围内，避免云台撞击机械限位。
# 注意：云台的「向下」物理范围常小于「向上」，因此向下的实际幅度会被自动压缩。
PAN_MIN, PAN_MAX = -140.0, 140.0     # pan（左右）允许范围
TILT_MIN, TILT_MAX = -40.0, 85.0     # tilt（上下）允许范围

# 方向符号：如果在你设备上「pan 增大 = 向左」，把 PAN_SIGN 改成 -1.0；
#           如果「tilt 增大 = 向下」，把 TILT_SIGN 改成 -1.0。
PAN_SIGN = +1.0     # +1.0：pan 增大 = 向右
TILT_SIGN = +1.0    # +1.0：tilt 增大 = 向上

# 转圈（第五步）参数
CIRCLE_PAN_RADIUS = 50.0        # 转圈的水平半径（度）
CIRCLE_TILT_RADIUS = 40.0       # 转圈的垂直半径（度）
CIRCLE_POINTS_PER_TURN = 16     # 每圈采样点数（越大越圆滑，下发也越密）
CIRCLE_HOLD_SECONDS = 0.18      # 转圈时每个采样点的停留（秒），越小转得越快

# 直线方向 / 回正动作的停留时长（秒）
HOLD_SECONDS = 1.0

# 顺时针、逆时针各转几圈
TURNS = 3

# 回正 / 中心位置（通常让云台正对用户）
CENTER = Point(0.0, 0.0)

# =====================================================================
#  下面的逻辑通常无需修改。
# =====================================================================


def _clamp(point: Point) -> Point:
    """把位置钳制到机械限位范围内。"""
    return Point(
        max(PAN_MIN, min(PAN_MAX, point.pan)),
        max(TILT_MIN, min(TILT_MAX, point.tilt)),
    )


def _move(dx: float, dy: float) -> Point:
    """根据米字方向向量 (dx, dy) 计算目标位置。

    dx ∈ {-1, 0, +1} 表示左 / 中 / 右，
    dy ∈ {-1, 0, +1} 表示下 / 中 / 上。
    组合出八个方向，再施加幅度与方向符号，最后钳制到限位内。
    """
    return _clamp(
        Point(
            PAN_SIGN * dx * AMPLITUDE_DEGREES,
            TILT_SIGN * dy * AMPLITUDE_DEGREES,
        )
    )


def _circle(*, clockwise: bool) -> list[Point]:
    """生成一段圆形轨迹。

    pan 与 tilt 相位相差 90°（一个用 cos、一个用 sin），云台前端划出一个圆。
    clockwise=True 时反向。返回整段（TURNS 圈）的采样点列表。
    """
    total_points = TURNS * CIRCLE_POINTS_PER_TURN
    points: list[Point] = []
    for index in range(total_points + 1):
        angle = 2.0 * math.pi * index / CIRCLE_POINTS_PER_TURN
        pan = CIRCLE_PAN_RADIUS * math.cos(angle)
        tilt = CIRCLE_TILT_RADIUS * math.sin(angle)
        if clockwise:
            tilt = -tilt
        points.append(_clamp(Point(pan, tilt)))
    return points


def eye_mizicao_sequence() -> list[Step]:
    """生成一次完整的「眼部米字操」动作序列。

    流程（对应米字的八个方向 + 转圈，最后回正）：

        第一步  上 → 下，重复 TURNS 次；
        第二步  左 → 回正 → 右 → 回正，重复 TURNS 次；
        第三步  左上 → 右下，重复 TURNS 次；
        第四步  右上 → 左下，重复 TURNS 次；
        第五步  顺时针转 TURNS 圈，再逆时针转 TURNS 圈；
        收尾    回正对准用户。

    返回 list[Step]。调用方可顺序遍历，逐条下发到自己的云台 SDK。
    """
    up = _move(0, +1)
    down = _move(0, -1)
    left = _move(-1, 0)
    right = _move(+1, 0)
    upper_left = _move(-1, +1)
    lower_right = _move(+1, -1)
    upper_right = _move(+1, +1)
    lower_left = _move(-1, -1)

    steps: list[Step] = []

    # 第一步：上、下
    for _ in range(TURNS):
        steps.append(Step(up, HOLD_SECONDS))
        steps.append(Step(down, HOLD_SECONDS))

    # 第二步：左、回正、右、回正
    for _ in range(TURNS):
        steps.append(Step(left, HOLD_SECONDS))
        steps.append(Step(CENTER, HOLD_SECONDS))
        steps.append(Step(right, HOLD_SECONDS))
        steps.append(Step(CENTER, HOLD_SECONDS))

    # 第三步：左上、右下
    for _ in range(TURNS):
        steps.append(Step(upper_left, HOLD_SECONDS))
        steps.append(Step(lower_right, HOLD_SECONDS))

    # 第四步：右上、左下
    for _ in range(TURNS):
        steps.append(Step(upper_right, HOLD_SECONDS))
        steps.append(Step(lower_left, HOLD_SECONDS))

    # 第五步：顺时针、逆时针各转圈
    for point in _circle(clockwise=True):
        steps.append(Step(point, CIRCLE_HOLD_SECONDS))
    for point in _circle(clockwise=False):
        steps.append(Step(point, CIRCLE_HOLD_SECONDS))

    # 收尾：回正
    steps.append(Step(CENTER, HOLD_SECONDS))

    return steps