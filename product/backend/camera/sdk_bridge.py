from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any


class LinkCameraBridge:
    """Optional adapter for the native Link SDK helper.

    Browser getUserMedia owns the video stream in the prototype. The helper only
    sends UVC/XU controls through the provided SDK.
    """

    def __init__(self, project_root: Path) -> None:
        bridge_candidates = (
            project_root / "cpp" / "build-vs2022" / "Release" / "link_camera_bridge.exe",
            project_root / "cpp" / "build-msvc" / "Release" / "link_camera_bridge.exe",
            project_root / "cpp" / "build-vs2019" / "Release" / "link_camera_bridge.exe",
        )
        self.executable = next((path for path in bridge_candidates if path.exists()), bridge_candidates[0])
        self.sdk_test_executable = project_root.parent / "UVCCamera_win" / "x64" / "bin" / "UVCCameraTest.exe"
        self._cached_detection: tuple[float, dict[str, Any]] | None = None
        self._browser_confirmed_until = 0.0
        self._browser_device = ""

    def _run(self, *args: str) -> dict[str, Any]:
        if not self.executable.exists():
            return {"available": False, "mode": "browser-camera", "detail": "原生 SDK 桥接器尚未编译"}
        try:
            completed = subprocess.run(
                [str(self.executable), *args],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
            )
            output = completed.stdout.strip()
            result: dict[str, Any] = {}
            if output:
                # The vendor DLL writes diagnostic logs to stdout. The bridge's
                # machine-readable JSON is always the final JSON object line.
                for line in reversed(output.splitlines()):
                    candidate = line.strip()
                    if not candidate.startswith("{"):
                        continue
                    try:
                        result = json.loads(candidate)
                        break
                    except json.JSONDecodeError:
                        continue
                if not result:
                    raise json.JSONDecodeError("没有找到桥接器 JSON 输出", output, 0)
            return {"available": True, "exit_code": completed.returncode, **result}
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            return {"available": False, "mode": "browser-camera", "detail": str(exc)}

    def status(self) -> dict[str, Any]:
        if time.monotonic() < self._browser_confirmed_until:
            return {
                "available": True,
                "ok": True,
                "connected": True,
                "device": self._browser_device,
                "detection": "browser-exact-device",
            }
        native = self._run("status")
        if native.get("ok"):
            return {**native, "connected": True, "detection": "link-sdk"}
        detected = self._detect_link2_fallback()
        return {
            **native,
            "connected": detected["connected"],
            "device": detected.get("device"),
            "detection": detected["detection"],
        }

    def _run_bundled_sdk_test(self, commands: str, timeout: int = 8) -> subprocess.CompletedProcess[str] | None:
        if not self.sdk_test_executable.exists():
            return None
        try:
            return subprocess.run(
                [str(self.sdk_test_executable)],
                input=commands,
                check=False,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired):
            return None

    def _detect_link2_fallback(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._cached_detection and now - self._cached_detection[0] < 5:
            return self._cached_detection[1]
        sdk_result = self._run_bundled_sdk_test("0\n")
        if sdk_result:
            match = re.search(r"Succeed to open camera:\s*([^\r\n]+)", sdk_result.stdout, re.IGNORECASE)
            if match and "insta360link2" in re.sub(r"[^a-z0-9]", "", match.group(1).lower()):
                result = {
                    "connected": True,
                    "device": match.group(1).strip(),
                    "detection": "bundled-link-sdk",
                }
                self._cached_detection = (now, result)
                return result

        command = (
            "Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | "
            "Where-Object { $_.Class -in @('Camera','Image') } | "
            "Select-Object FriendlyName,InstanceId | ConvertTo-Json -Compress"
        )
        result: dict[str, Any] = {"connected": False, "detection": "windows-pnp"}
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                check=False,
                capture_output=True,
                text=True,
                timeout=6,
            )
            payload = json.loads(completed.stdout) if completed.stdout.strip() else []
            devices = payload if isinstance(payload, list) else [payload]
            for device in devices:
                name = str(device.get("FriendlyName", ""))
                normalized = re.sub(r"[^a-z0-9]", "", name.lower())
                if "insta360link2" in normalized:
                    result = {"connected": True, "device": name, "detection": "windows-pnp"}
                    break
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            result["detection"] = "unavailable"
        self._cached_detection = (now, result)
        return result

    def is_link2_connected(self) -> bool:
        return bool(self.status().get("connected"))

    def confirm_browser_link2(self, label: str) -> bool:
        if "insta360link2" not in re.sub(r"[^a-z0-9]", "", label.lower()):
            return False
        self._browser_device = label.strip()
        self._browser_confirmed_until = time.monotonic() + 60
        return True

    def apply_health_profile(self, kind: str) -> dict[str, Any]:
        return self._run("profile", kind)

    def set_privacy(self, enabled: bool) -> dict[str, Any]:
        return self._run("privacy", "on" if enabled else "off")

    def move_gimbal(self, pan: int, tilt: int) -> dict[str, Any]:
        """Move Link 2 to an absolute angle without opening a video stream."""
        # Official Link SDK absolute range (degrees): pan -145..145,
        # tilt -45..90. The native helper converts degrees to SDK units.
        pan = max(-145, min(145, int(pan)))
        tilt = max(-45, min(90, int(tilt)))
        native = self._run("gimbal", str(pan), str(tilt))
        if native.get("available"):
            return native

        # The bundled SDK demo accepts menu item 1104, then pan/tilt in degrees.
        # The browser stream is deliberately released before this fallback runs.
        result = self._run_bundled_sdk_test(f"1104\n{pan}\n{tilt}\n0\n")
        if result is None:
            return {"available": False, "ok": False, "detail": "没有可用的云台控制程序"}
        ok = "success" in result.stdout.lower()
        return {
            "available": True,
            "ok": ok,
            "mode": "bundled-link-sdk",
            "pan": pan,
            "tilt": tilt,
            "detail": "云台已移动" if ok else "SDK 未确认云台移动成功",
        }

    def react_to_mood(self, mood: str) -> dict[str, Any]:
        """Run a short Link 2 light-and-gimbal reaction for a visible mood."""
        if mood not in {"happy", "low", "tired"}:
            return {"available": True, "ok": False, "detail": "不支持的可见状态"}
        result = self._run("react", mood)
        if result.get("available"):
            return result
        return {**result, "ok": False, "detail": "原生 SDK 桥接器不支持状态互动"}

    def set_resident_features(self, enabled: bool) -> dict[str, Any]:
        """Enable official Link 2 person tracking and supported gestures."""
        native = self._run("features", "on" if enabled else "off")
        if native.get("available"):
            return native

        # Fallback configures single-person auto composition, normal speed and
        # Palm/L/V recognition through the vendor's interactive sample.
        commands = (
            "312\n0\n303\n2\n305\n1\n301\n1\n"
            "402\n1\n1\n402\n2\n1\n402\n3\n1\n401\n1\n0\n"
            if enabled
            else "401\n0\n301\n0\n0\n"
        )
        result = self._run_bundled_sdk_test(commands, timeout=15)
        if result is None:
            return {"available": False, "ok": False, "detail": "没有可用的SDK功能控制程序"}
        minimum_successes = 8 if enabled else 2
        ok = result.stdout.lower().count("success") >= minimum_successes
        return {
            "available": True,
            "ok": ok,
            "enabled": enabled,
            "mode": "bundled-link-sdk",
            "detail": "人物跟踪和手势已开启" if ok and enabled else "常驻功能配置未完全成功",
        }

    def keep_awake(self) -> dict[str, Any]:
        native = self._run("keepalive")
        if native.get("available"):
            return native
        # Existing SDK demo is a safe no-build fallback: option 804 disables
        # privacy mode, then option 0 exits. No video device is opened here.
        result = self._run_bundled_sdk_test("804\n0\n0\n")
        if result is None:
            return {"available": False, "ok": False, "detail": "没有可用的 SDK 保活程序"}
        ok = "success" in result.stdout.lower()
        return {
            "available": True,
            "ok": ok,
            "mode": "bundled-link-sdk",
            "detail": "已通过 SDK 关闭隐私模式" if ok else "SDK 保活命令未确认成功",
        }
