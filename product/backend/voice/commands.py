from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Command:
    action: str
    kind: str | None = None
    label: str = ""


@dataclass(frozen=True)
class CommandRoute:
    """A declarative voice route.

    Add a route to DEFAULT_ROUTES, or pass an application-specific route list to
    parse_command, without changing parser control flow.
    """

    keywords: tuple[str, ...]
    action: str
    kind: str | None = None
    label: str = ""
    requires_wake_word: bool = True


WAKE_WORDS = ("inwork", "音沃克")

DEFAULT_ROUTES = (
    CommandRoute(("开启工作时间", "开始工作时间", "开始工作"), "work_start", label="开启工作时间", requires_wake_word=False),
    CommandRoute(("工作时间结束", "结束工作时间", "结束工作"), "work_end", label="工作时间结束", requires_wake_word=False),
    CommandRoute(("活动一下脖子", "活动脖子", "颈部间操", "颈椎操"), "neck_break", label="开始颈部间操"),
    CommandRoute(("黑眼圈", "眼圈"), "capture", "dark_circle", "检查黑眼圈"),
    CommandRoute(("舌苔", "舌头"), "capture", "tongue", "检查舌苔"),
    CommandRoute(("痘痘", "痤疮", "皮肤"), "capture", "acne", "检查痘痘"),
    CommandRoute(("用餐", "食物", "营养", "吃饭"), "capture", "food", "分析饮食"),
)


def normalize(text: str) -> str:
    value = text.lower().strip()
    value = re.sub(r"[，,。.!！?？\s]+", "", value)
    return value


def parse_command(text: str, routes: Iterable[CommandRoute] = DEFAULT_ROUTES) -> Command | None:
    value = normalize(text)
    has_wake_word = any(value.startswith(word) for word in WAKE_WORDS)
    for route in routes:
        if route.requires_wake_word and not has_wake_word:
            continue
        if any(keyword in value for keyword in route.keywords):
            return Command(route.action, kind=route.kind, label=route.label)
    return Command("unknown", label="未识别的 inwork 指令") if has_wake_word else None
