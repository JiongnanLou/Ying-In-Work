"""DirectShow capture by the device name, never by a potentially shifted index."""
import subprocess
import threading

import cv2
import numpy as np


class NamedCapture:
    def __init__(self, exe, name, size):
        self.condition = threading.Condition()
        self.release_lock = threading.Lock()
        self.frame = None
        self.sequence = self.consumed = 0
        self.closed = False
        self.error = ''
        self.process = subprocess.Popen([
            str(exe), '-hide_banner', '-loglevel', 'error', '-nostdin',
            '-f', 'dshow', '-rtbufsize', '8M', '-video_size', f'{size[0]}x{size[1]}',
            '-framerate', '15' if size[0]>=3840 else '30', '-i', 'video='+name,
            '-an', '-threads', '1', '-vf', 'fps=15', '-c:v', 'mjpeg', '-q:v', '4',
            '-f', 'image2pipe', 'pipe:1'], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.errors = threading.Thread(target=self._errors, daemon=True)
        self.reader.start(); self.errors.start()
        with self.condition:
            self.condition.wait_for(lambda:self.frame is not None or self.closed, timeout=8)

    def _errors(self):
        for line in self.process.stderr:
            self.error = line.decode('utf-8', errors='replace').strip()[-400:]

    def _read(self):
        pending = bytearray()
        try:
            while not self.closed:
                chunk = self.process.stdout.read1(65536)
                if not chunk: break
                pending.extend(chunk)
                while True:
                    start = pending.find(b'\xff\xd8')
                    end = pending.find(b'\xff\xd9', max(0,start))
                    if start<0 or end<0: break
                    raw = bytes(pending[start:end+2]); del pending[:end+2]
                    frame = cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
                    if frame is not None:
                        with self.condition:
                            self.frame = frame
                            self.sequence += 1
                            self.condition.notify_all()
                if len(pending)>16*1024*1024: raise RuntimeError('Invalid camera stream')
        finally:
            with self.condition:
                self.closed = True
                self.condition.notify_all()

    def isOpened(self):
        return self.frame is not None and not self.closed

    def set(self, *_):
        pass  # Capture format was negotiated with the named device on startup.

    def read(self):
        with self.condition:
            self.condition.wait_for(lambda:self.sequence>self.consumed or self.closed, timeout=2)
            if self.closed or self.sequence==self.consumed: return False,None
            self.consumed = self.sequence
            return True,self.frame

    def release(self):
        with self.release_lock:
            with self.condition:
                self.closed = True
                self.condition.notify_all()
            if self.process.poll() is None:
                self.process.terminate()
                try: self.process.wait(timeout=3)
                except subprocess.TimeoutExpired: self.process.kill();self.process.wait(timeout=2)
            if threading.current_thread() is not self.reader: self.reader.join(timeout=2)
