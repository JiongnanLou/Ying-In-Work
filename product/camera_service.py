"""One video owner: prefer Link 2, fall back to other local cameras."""
import base64
import re
import queue
import subprocess
import threading
import time
from pathlib import Path

import cv2
from cv2_enumerate_cameras import enumerate_cameras
from named_capture import NamedCapture


def is_link2(name):
    return re.sub(r"[^a-z0-9]", "", name.lower()) == "insta360link2"


class NativeCamera:
    def __init__(self, root):
        self.exe = Path(root) / "native/link_camera_bridge.exe"
        self.sdk = Path(root) / "native/UVCCameraTest.exe"
        self.lock = threading.Lock()

    @staticmethod
    def parse_sdk(output):
        def values(pattern):
            match = re.search(pattern, output)
            return tuple(map(int, match.groups())) if match else None
        mode = values(r'mode: (\d+) status: (\d+)')
        pose = values(r'pan\(degree\):(-?\d+) tilt\(degree\):(-?\d+)')
        stream = values(r'stream_open: (\d+)')
        size = values(r'play res: (\d+)x(\d+)@(\d+)')
        style = values(r'style: (\d+)')
        speed = values(r'track speed: (\d+)')
        objects = re.findall(r'x:([-\d.e+]+) y:([-\d.e+]+) w:([-\d.e+]+) h:([-\d.e+]+)', output)
        return {'ok': 'Succeed to open camera: Insta360 Link 2' in output.splitlines() and
                       re.search(r'\bfailed\b',output) is None,
                'mode': mode[0] if mode else None, 'mode_status': mode[1] if mode else None,
                'pan': pose[0] if pose else None, 'tilt': pose[1] if pose else None,
                'stream_open': bool(stream[0]) if stream else None,
                'stream_size': list(size) if size else None,
                'composition': style[0] if style else None,
                'track_speed': speed[0] if speed else None,
                'objects': [list(map(float,r)) for r in objects]}

    def _sdk_run(self, args):
        command = args[0]
        if command == 'tracking':
            enabled = args[1]=='on'
            # Keep the firmware AI master enabled, but disable gesture triggers individually.
            commands = [804,0,312,0,303,1,305,1,401,1,402,1,0,402,2,0,402,3,0,301,1,302,304,306] if enabled else [401,0,301,0,302]
        elif command == 'telemetry': commands = [205,206,302,304,306,1103,308]
        else: return {'ok':False,'error':'未知 SDK 操作'}
        process = subprocess.Popen([str(self.sdk)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding='gbk', errors='replace',
                                   creationflags=subprocess.CREATE_NO_WINDOW, cwd=str(self.sdk.parent))
        greeting = queue.Queue()
        threading.Thread(target=lambda:greeting.put(process.stdout.readline()), daemon=True).start()
        try:
            first = greeting.get(timeout=4)
            # The vendor console selects its first device. Do not send mutations to another model.
            if first.strip() != 'Succeed to open camera: Insta360 Link 2':
                return {'ok':False,'error':'SDK 选中的设备不是 Link 2，已拒绝云台操作'}
            output,_ = process.communicate('\n'.join(map(str,commands+[0]))+'\n',timeout=8)
            data = self.parse_sdk(first+output)
            if command == 'telemetry':
                # Object-list queries can be unsupported without a target; pose/stream remain valid.
                data['ok'] = data['pan'] is not None and data['mode'] is not None and data['stream_open'] is not None
            data['ok'] = data['ok'] and process.returncode==0
        finally:
            if process.poll() is None:
                process.kill();process.wait(timeout=3)
        if command == 'tracking':
            # Firmware briefly reports mode 255 while applying the command.
            # Read back after it settles instead of rejecting a successful transition.
            deadline = time.monotonic()+2
            while data['ok'] and time.monotonic()<deadline:
                confirmed = data['mode']==int(enabled)
                if enabled: confirmed = confirmed and data['composition']==1 and data['track_speed']==1
                if confirmed: break
                time.sleep(.15)
                data = self._sdk_run(('telemetry',))
            data['ok'] = data['ok'] and data['mode']==int(enabled)
            if enabled: data['ok'] = data['ok'] and data['composition']==1 and data['track_speed']==1
        if not data['ok']: data['error'] = '设备未确认云台/追踪配置，请检查连接或其他相机控制软件'
        return data

    def run(self, *args):
        import json
        with self.lock:
            try:
                if args and args[0] in ('tracking','telemetry'):
                    return self._sdk_run(args)
                result = subprocess.run([str(self.exe), *map(str, args)], capture_output=True,
                                        encoding="utf-8", errors="replace", timeout=16,
                                        creationflags=subprocess.CREATE_NO_WINDOW,
                                        cwd=str(self.exe.parent))
                for line in reversed(result.stdout.splitlines()):
                    if line.strip().startswith("{"):
                        data = json.loads(line)
                        data["ok"] = bool(data.get("ok") and result.returncode == 0)
                        return data
                return {"ok": False, "error": "相机控制组件没有返回有效结果"}
            except Exception as exc:
                return {"ok": False, "error": f"相机控制不可用：{type(exc).__name__}"}


class CameraService:
    def __init__(self):
        self.lock = threading.RLock()
        self.lifecycle = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None
        self.frame = None
        self.jpeg = None
        self.frame_at = 0
        self.device = ""
        self.error = ""
        self.running = False
        self.resolution = [0, 0]
        self.requested = (1280, 720)
        self.link2 = False
        self.generation = 0
        self.connecting = False
        self.notice = ""
        self.capture = None

    def open_capture(self, device):
        if device['link2']:
            return NamedCapture(Path(__file__).parent/'native/ffmpeg.exe', device['name'], self.requested)
        return cv2.VideoCapture(device['index'], cv2.CAP_DSHOW)

    def devices(self):
        return [{"index": c.index, "name": c.name, "supported": True,
                 "link2": is_link2(c.name)}
                for c in enumerate_cameras(cv2.CAP_DSHOW)]

    def candidates(self):
        return sorted(self.devices(), key=lambda d: not d['link2'])

    def start(self, width=1280, height=720):
        with self.lifecycle:
            if self.thread and self.thread.is_alive():
                if self.stop_event.is_set():
                    raise ValueError("相机正在释放，请稍后重试")
                return self.status()
            self.device = ""
            if not self.candidates():
                raise ValueError("未发现可用摄像头，请连接相机或检查 Windows 摄像头权限")
            self.requested = (width, height)
            self.stop_event.clear()
            self.error = ""
            self.connecting = True
            self.thread = threading.Thread(target=self._capture, daemon=True)
            self.thread.start()
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if self.running:
                return self.status()
            if self.error and not self.connecting:
                raise ValueError(self.error)
            time.sleep(.08)
        self.stop()
        raise ValueError("相机取流超时，请关闭其他占用摄像头的软件后重试")

    def _capture(self):
        ever_started = False
        try:
            while not self.stop_event.is_set():
                self.connecting = True
                failures = []
                for device in self.candidates():
                    if self.stop_event.is_set(): break
                    try:
                        self._stream(device)
                    except Exception as exc:
                        failures.append(str(exc))
                    ever_started = ever_started or self.generation > 0
                    if self.stop_event.is_set(): break
                if self.stop_event.is_set(): break
                self.error = '；'.join(failures) or '未发现摄像头，正在等待重新连接'
                # After a disconnect, reconnect automatically; initial failure is actionable.
                if not ever_started: break
                self.stop_event.wait(3)
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.connecting = False

    def _stream(self, device):
        cap = None
        try:
            cap = self.open_capture(device)
            self.capture = cap
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.requested[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.requested[1])
            cap.set(cv2.CAP_PROP_FPS, 15)
            if not cap.isOpened():
                raise RuntimeError(device['name'] + " 无法打开，可能被占用或未授权")
            failures = 0
            first = True
            while not self.stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    failures += 1
                    if failures > 8:
                        raise RuntimeError(device['name'] + " 画面中断，正在尝试其他摄像头")
                    self.stop_event.wait(.1)
                    continue
                failures = 0
                h, w = frame.shape[:2]
                preview = cv2.resize(frame, (1280, round(h * 1280 / w)))
                _, encoded = cv2.imencode(".jpg", preview, [cv2.IMWRITE_JPEG_QUALITY, 82])
                with self.lock:
                    if first:
                        self.device, self.link2 = device['name'], device['link2']
                        self.generation += 1
                        self.notice = '' if self.link2 else '已使用本机摄像头；原生人像追踪和云台联动不可用。'
                        first = False
                    self.frame, self.jpeg = frame, encoded.tobytes()
                    self.frame_at = time.monotonic()
                    self.resolution = [w, h]
                    self.running = True
                    self.connecting = False
                    self.error = ''
                self.stop_event.wait(.035)
        finally:
            if cap is not None:
                cap.release()
            self.capture = None
            with self.lock:
                self.running = False
                self.frame = self.jpeg = None

    def stop(self):
        with self.lifecycle:
            self.stop_event.set()
            if isinstance(self.capture, NamedCapture): self.capture.release()
            if self.thread and self.thread is not threading.current_thread():
                self.thread.join(timeout=6)
            with self.lock:
                self.running = False
                self.frame = self.jpeg = None

    def snapshot(self):
        with self.lock:
            if not self.running or self.frame is None or time.monotonic() - self.frame_at > 3:
                raise ValueError("相机没有新鲜画面，请先开始陪伴")
            return self.frame.copy()

    def data_url(self, max_width=None):
        frame = self.snapshot()
        if max_width and frame.shape[1] > max_width:
            h,w = frame.shape[:2]
            frame = cv2.resize(frame, (max_width, round(h*max_width/w)))
        _, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii")

    def status(self):
        with self.lock:
            hardware = bool(self.running and self.link2)
            return {"running": self.running, "device": self.device, "error": self.error,
                    "resolution": self.resolution, "requested": list(self.requested),
                    "link2": self.link2, "generation": self.generation,
                    "connecting": self.connecting, "notice": self.notice,
                    "capabilities": {"gimbal": hardware, "tracking": hardware}}
