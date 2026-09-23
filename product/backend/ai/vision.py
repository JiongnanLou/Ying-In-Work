from __future__ import annotations

import base64
import io
import math
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from PIL import Image, ImageStat

from .config_store import AIConfigStore, ConfigStoreError


ANALYSIS_LABELS = {
    "dark_circle": "眼周状态",
    "tongue": "舌象状态",
    "acne": "皮肤状态",
    "food": "饮食营养",
    "work": "工作状态",
    "emotion": "可见情绪与姿态",
}


class AnalysisError(RuntimeError):
    pass


def decode_data_url(data_url: str) -> tuple[str, bytes]:
    if not data_url.startswith("data:image/") or ";base64," not in data_url:
        raise AnalysisError("需要 JPEG/PNG 格式的 base64 图片")
    header, encoded = data_url.split(",", 1)
    try:
        raw = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise AnalysisError("图片数据损坏") from exc
    if len(raw) > 20 * 1024 * 1024:
        raise AnalysisError("单张图片不能超过 20MB")
    media_type = header[5:].split(";", 1)[0]
    return media_type, raw


def image_quality(data_url: str) -> dict[str, Any]:
    _, raw = decode_data_url(data_url)
    try:
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as exc:
        raise AnalysisError("无法读取图片") from exc
    original_width, original_height = image.size
    statistics_image = image.copy()
    statistics_image.thumbnail((512, 512))
    stat = ImageStat.Stat(statistics_image)
    brightness = round(sum(stat.mean) / 3, 1)
    contrast = round(sum(stat.stddev) / 3, 1)
    return {
        "width": original_width,
        "height": original_height,
        "megapixels": round((original_width * original_height) / 1_000_000, 2),
        "encoded_bytes": len(raw),
        "statistics_width": statistics_image.width,
        "statistics_height": statistics_image.height,
        "brightness": brightness,
        "contrast": contrast,
    }


@dataclass
class VisionAnalyzer:
    api_key: str | None = None
    model: str = "qwen3.8-max"
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    config_store: AIConfigStore | None = None

    @classmethod
    def from_environment(cls, config_path: Path | None = None) -> "VisionAnalyzer":
        store = AIConfigStore(config_path) if config_path else None
        environment_key = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        if environment_key:
            return cls(
                api_key=environment_key,
                model=os.getenv("QWEN_MODEL", "qwen3.8-max"),
                base_url=os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
                config_store=store,
            )
        if store:
            try:
                saved = store.load()
                if saved:
                    return cls(**saved, config_store=store)
            except ConfigStoreError as exc:
                print(f"[ai-config] {exc}")
        return cls(config_store=store)

    @property
    def provider(self) -> str:
        return "qwen" if self.api_key else "unconfigured"

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def public_config(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "has_api_key": bool(self.api_key),
            "persisted": bool(self.config_store and self.config_store.path.exists()),
            "key_storage": "Windows DPAPI（当前用户）" if self.config_store else "仅当前进程",
        }

    def configure(self, api_key: str, base_url: str, model: str) -> dict[str, Any]:
        api_key, base_url, model = api_key.strip(), base_url.strip().rstrip("/"), model.strip()
        parsed = urlparse(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise AnalysisError("API URL 必须是有效的 http/https 地址")
        if not api_key:
            raise AnalysisError("API Key 不能为空")
        if not model:
            raise AnalysisError("模型 ID 不能为空")
        self.api_key, self.base_url, self.model = api_key, base_url, model
        if self.config_store:
            try:
                self.config_store.save(api_key, base_url, model)
            except ConfigStoreError as exc:
                raise AnalysisError(str(exc)) from exc
        return self.public_config()

    def clear_config(self) -> None:
        if self.config_store:
            self.config_store.clear()
        self.api_key = None

    def test_connection(self) -> dict[str, Any]:
        if not self.configured:
            raise AnalysisError("请先填写并保存 Qwen API 配置")
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "只返回 JSON：{\"ok\":true}"}],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": 40,
        }
        body = self._request_chat(payload, timeout=30)
        content = body["choices"][0]["message"]["content"]
        return {"ok": True, "model": self.model, "reply": content[:200]}

    def analyze(self, kind: str, image_data: str | list[str]) -> dict[str, Any]:
        if kind not in ANALYSIS_LABELS:
            raise AnalysisError(f"不支持的分析类型：{kind}")
        if not self.configured:
            raise AnalysisError("Qwen 模型尚未配置，请先在右上角设置中填写 API Key、URL 和模型 ID")
        images = image_data if isinstance(image_data, list) else [image_data]
        if not 1 <= len(images) <= 5:
            raise AnalysisError("每次分析需要 1 至 5 张采集图像")
        qualities = [image_quality(str(image)) for image in images]
        result = (self._qwen_emotion(str(images[0])) if kind == 'emotion' and len(images) == 1
                  else self._qwen(kind, [str(image) for image in images], qualities))
        result["image_quality"] = {"frames": len(images), "samples": qualities}
        result["disclaimer"] = "结果仅用于个人健康趋势参考，不构成医学诊断或治疗建议。"
        return result

    def _qwen_emotion(self, image: str) -> dict[str, Any]:
        """Compact non-thinking response for the ten-second companion loop."""
        payload = {
            'model': self.model, 'enable_thinking': False,
            'messages': [
                {'role': 'system', 'content': '只观察近处主要人物的可见表情，不推断心理疾病或真实内心。'
                 '无人、多人无法确定主体或面部不清时 mood=unknown，confidence<=0.3。'
                 '只返回 JSON：mood(happy/calm/tired/low/unknown)、confidence(0到1)、summary(20字内的可见表情描述)。'},
                {'role': 'user', 'content': [{'type': 'text', 'text': '观察此刻的可见表情。'},
                                          {'type': 'image_url', 'image_url': {'url': image}}]}],
            'response_format': {'type': 'json_object'}, 'temperature': 0, 'max_tokens': 160,
        }
        body = self._request_chat(payload, timeout=30)
        try:
            result = json.loads(body['choices'][0]['message']['content'])
            confidence = float(result['confidence'])
            if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise ValueError('Invalid confidence')
            if result['mood'] not in ('happy','calm','tired','low','unknown'):
                raise ValueError('Invalid mood')
            return {'mood':result['mood'], 'confidence':confidence,
                    'summary':str(result['summary'])[:60], 'score':None,
                    'activity':'unknown', 'metrics':{}, 'suggestions':[]}
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AnalysisError('Qwen 表情结果格式无效，稍后会自动重试') from exc

    def _qwen(self, kind: str, images: list[str], qualities: list[dict[str, Any]]) -> dict[str, Any]:
        focus = {
            "dark_circle": "只判断眼下颜色深浅、范围、左右差异和浮肿趋势，并给出睡眠、用眼与复测建议。",
            "tongue": "只描述舌苔厚薄、覆盖、颜色与舌体可见趋势，并给出低风险生活建议。",
            "acne": "只描述痘痘的大致数量级、分布、红肿程度和新旧痕迹，并给出温和护理建议。",
            "food": "只列出主要食物、粗略份量、蛋白质/碳水/脂肪结构和最重要的饮食提醒。",
            "work": "只返回专注、使用手机、离座或无法判断，以及一句最必要的状态说明。",
            "emotion": "只根据可见表情和头部姿态判断开心、平静、疲劳、低落倾向或无法判断，并判断是否低头；不得推断心理疾病。",
        }[kind]
        instructions = (
            "你是非医疗用途的个人健康趋势图像分析器。只描述图像中可见内容，不诊断疾病，"
            "不确定时明确降低 confidence。健康类建议仅限低风险生活方式与就医提醒。"
            "work 类型只在 focused/phone/away/unknown 中选择；非 work 类型 activity 必须为 unknown。"
            "emotion 类型额外返回 mood(happy/calm/tired/low/unknown) 和 head_down(boolean)；其他类型 mood 为 unknown、head_down 为 false。"
            "food 类型需在 metrics 中尽量列出可见食物、粗略份量和宏量营养估算，并明确误差。"
            "回复必须极简并以健康状态为中心。summary 只写1至2句、最多80个中文字符；"
            "suggestions 只给2至3条最重要且能执行的建议，每条最多35个中文字符；metrics 最多6项。"
            "禁止描述拍摄场景、场地、背景、人物年龄性别、服装、舞台、倒计时、摄像头、图像数量或分辨率。"
            "不要复述任务，不要寒暄，不要写分析过程，不要在正文重复免责声明。"
            "只有当光照或遮挡确实导致无法判断时，才允许用一句话要求重新采集。"
            "只返回一个 JSON 对象，必须包含 summary(string)、score(0-100 number)、confidence(0-1 number)、"
            "activity(focused/phone/away/unknown)、mood(happy/calm/tired/low/unknown)、head_down(boolean)、"
            "metrics(object) 和 suggestions(string array)，不要 Markdown。"
        )
        source_description = f"这是用户主动采集的 {len(images)} 张图像；以实际上传尺寸为准。"
        prompt = (
            f"分析类型：{kind}（{ANALYSIS_LABELS[kind]}）。"
            f"本次只关注：{focus}"
            f"{source_description}"
            f"各帧原始上传画质指标：{json.dumps(qualities, ensure_ascii=False)}。"
            "其中 width/height 是实际上传原图分辨率；statistics_width/statistics_height 只表示后端计算亮度时使用的缩略副本，"
            "不得将缩略统计尺寸描述为输入图像分辨率。"
            "请结合全部帧判断，忽略眨眼、运动模糊等单帧偶发现象，并返回结构化结果。"
        )
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        content.extend({"type": "image_url", "image_url": {"url": image}} for image in images)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": instructions},
                {
                    "role": "user",
                    "content": content,
                }
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_tokens": 1200,
        }
        body = self._request_chat(payload, timeout=90)
        try:
            content = body["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            result = json.loads(content)
            self._validate_result(result)
            return result
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AnalysisError("Qwen 返回内容无法解析为约定的 JSON") from exc

    def _request_chat(self, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = json.load(response)
        except urllib.error.HTTPError as exc:
            detail = "请检查模型 ID、接口权限及账户状态"
            raise AnalysisError(f"Qwen API 返回 {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise AnalysisError(f"无法连接 Qwen API：{exc}") from exc
        return body

    @staticmethod
    def _validate_result(result: dict[str, Any]) -> None:
        required = {"summary", "score", "confidence", "activity", "metrics", "suggestions"}
        if not isinstance(result, dict) or not required.issubset(result):
            raise AnalysisError("Qwen 返回结果缺少必要字段")
        if result["activity"] not in ("focused", "phone", "away", "unknown"):
            result["activity"] = "unknown"
        if result.get("mood") not in ("happy", "calm", "tired", "low", "unknown"):
            result["mood"] = "unknown"
        result["head_down"] = bool(result.get("head_down", False))
        if not all(math.isfinite(float(result[k])) for k in ("score", "confidence")):
            raise AnalysisError("模型分数不是有效数字")
        result["score"] = max(0, min(100, float(result["score"])))
        result["confidence"] = max(0, min(1, float(result["confidence"])))
        if not isinstance(result["metrics"], dict) or not isinstance(result["suggestions"], list):
            raise AnalysisError("Qwen 返回字段类型不符合约定")
        summary = " ".join(str(result["summary"]).split()).strip()
        result["summary"] = summary[:120] + ("…" if len(summary) > 120 else "")
        unique_suggestions: list[str] = []
        for suggestion in result["suggestions"]:
            value = " ".join(str(suggestion).split()).strip()
            if value and value not in unique_suggestions:
                unique_suggestions.append(value[:60] + ("…" if len(value) > 60 else ""))
            if len(unique_suggestions) == 3:
                break
        result["suggestions"] = unique_suggestions
        result["metrics"] = dict(list(result["metrics"].items())[:6])
