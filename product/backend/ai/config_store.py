from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path


class ConfigStoreError(RuntimeError):
    pass


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _blob(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer


def _protect(secret: str) -> str:
    if os.name != "nt":
        raise ConfigStoreError("API Key 持久化目前仅支持 Windows DPAPI")
    source, source_buffer = _blob(secret.encode("utf-8"))
    entropy, entropy_buffer = _blob(b"inwork-health-ai-v1")
    output = _DataBlob()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(source), "InWork Qwen API Key", ctypes.byref(entropy),
        None, None, 0x1, ctypes.byref(output)
    )
    _ = (source_buffer, entropy_buffer)
    if not ok:
        raise ConfigStoreError("Windows DPAPI 无法加密 API Key")
    try:
        return base64.b64encode(ctypes.string_at(output.pbData, output.cbData)).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


def _unprotect(encoded: str) -> str:
    if os.name != "nt":
        raise ConfigStoreError("API Key 持久化目前仅支持 Windows DPAPI")
    source, source_buffer = _blob(base64.b64decode(encoded, validate=True))
    entropy, entropy_buffer = _blob(b"inwork-health-ai-v1")
    output = _DataBlob()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(source), None, ctypes.byref(entropy),
        None, None, 0x1, ctypes.byref(output)
    )
    _ = (source_buffer, entropy_buffer)
    if not ok:
        raise ConfigStoreError("当前 Windows 用户无法解密已保存的 API Key")
    try:
        return ctypes.string_at(output.pbData, output.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


class AIConfigStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, str] | None:
        if not self.path.exists():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return {
                "api_key": _unprotect(payload["api_key_dpapi"]),
                "base_url": str(payload["base_url"]),
                "model": str(payload["model"]),
            }
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise ConfigStoreError(f"无法读取 AI 配置：{exc}") from exc

    def save(self, api_key: str, base_url: str, model: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "encryption": "windows-dpapi-current-user",
            "api_key_dpapi": _protect(api_key),
            "base_url": base_url,
            "model": model,
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
