"""Local camera-only RPS. Opponent commits before the capture countdown."""
import secrets
import threading
import time
from pathlib import Path

import cv2

HANDS = {"Closed_Fist": "rock", "Open_Palm": "paper", "Victory": "scissors"}
NAMES = {"rock": "石头", "paper": "布", "scissors": "剪刀"}


def outcome(user, cpu):
    if user not in NAMES or cpu not in NAMES:
        raise ValueError("无效手势")
    return "draw" if user == cpu else "win" if (user, cpu) in (
        ("rock", "scissors"), ("scissors", "paper"), ("paper", "rock")) else "lose"


def classify(result):
    # Ambiguous/multiple hands never award a point.
    if len(result.gestures) != 1 or not result.gestures[0]:
        return None, 0.0
    category = result.gestures[0][0]
    hand = HANDS.get(category.category_name)
    return (hand, float(category.score)) if hand and category.score >= .55 else (None, 0.0)


class StableHand:
    def __init__(self):
        self.hand, self.since, self.count = None, 0, 0

    def update(self, hand, now):
        if not hand or hand != self.hand:
            self.hand, self.since, self.count = hand, now, 0
        self.count += 1
        return bool(hand and self.count >= 3 and now - self.since >= .45)


class GestureGame:
    def __init__(self, service):
        self.service = service
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.thread = None
        self.recognizer = None
        self.last_timestamp = 0
        self.state = {"state": "idle", "userWins": 0, "cpuWins": 0, "round": 0, "finished": False}

    def status(self):
        with self.lock:
            return dict(self.state)

    def update(self, **values):
        with self.lock:
            self.state.update(values)

    def start(self):
        self.service.camera.snapshot()
        if not self.service.acquire_operation():
            raise ValueError("请先结束当前采集或活动")
        with self.lock:
            if self.state['finished']:
                self.service.operations.release()
                raise ValueError("本场已结束，请点击重新开始")
            self.cancel.clear()
            self.state.update(state="loading", detected=None, cpu=None, user=None,
                              outcome=None, error=None, countdown=3)
            self.thread = threading.Thread(target=self._round, daemon=True)
            self.thread.start()
            return dict(self.state)

    def _load(self):
        if self.recognizer is not None:
            return
        import mediapipe as mp
        from mediapipe.tasks.python import vision
        model = Path(self.service.root) / 'assets/gesture_recognizer.task'
        options = vision.GestureRecognizerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
            running_mode=vision.RunningMode.VIDEO, num_hands=2,
            min_hand_detection_confidence=.6, min_hand_presence_confidence=.6)
        self.recognizer = vision.GestureRecognizer.create_from_options(options)

    def recognize(self, frame):
        import mediapipe as mp
        self._load()
        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(cv2.resize(frame, (640, round(height * 640 / width))), cv2.COLOR_BGR2RGB)
        timestamp = max(self.last_timestamp + 1, int(time.monotonic() * 1000))
        self.last_timestamp = timestamp
        return classify(self.recognizer.recognize_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp))

    def _round(self):
        cpu = secrets.choice(tuple(NAMES))
        try:
            self._load()
            for remaining in (3, 2, 1):
                self.update(state="countdown", countdown=remaining)
                if self.cancel.wait(1):
                    return
            self.update(state="recognizing", countdown=0)
            deadline = time.monotonic() + 8
            stable = StableHand()
            while not self.cancel.is_set() and time.monotonic() < deadline:
                hand, confidence = self.recognize(self.service.camera.snapshot())
                now = time.monotonic()
                self.update(detected=hand, confidence=round(confidence, 3), countdown=max(0, int(deadline-now)+1))
                if stable.update(hand, now):
                    with self.lock:
                        if self.cancel.is_set():
                            return
                        result = outcome(hand, cpu)
                        user_wins = self.state['userWins'] + (result == 'win')
                        cpu_wins = self.state['cpuWins'] + (result == 'lose')
                        finished = max(user_wins, cpu_wins) >= 2
                        self.state.update(state="result", user=hand, cpu=cpu, outcome=result,
                                          userWins=user_wins, cpuWins=cpu_wins, finished=finished,
                                          round=self.state['round']+1)
                        if finished:
                            self.service.event('game', '完成真实手势对战 · '+('你获胜' if user_wins >= 2 else '小萤获胜'))
                    return
                self.cancel.wait(.1)
            if not self.cancel.is_set():
                self.update(state="retry", error="没有看清一个稳定手势。请把一只手完整放入画面，掌心朝向相机，再试一次。")
        except Exception as exc:
            self.update(state="error", error="手势识别暂不可用："+str(exc))
        finally:
            if self.cancel.is_set():
                self.update(state="cancelled", detected=None)
            self.service.operations.release()

    def stop(self):
        with self.lock:
            self.cancel.set()

    def reset(self):
        with self.lock:
            if self.state['state'] in ('loading', 'countdown', 'recognizing'):
                raise ValueError("请先结束当前出拳")
            self.state = {"state": "idle", "userWins": 0, "cpuWins": 0, "round": 0, "finished": False}
            return dict(self.state)

    def close(self):
        self.stop()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=10)
        if self.recognizer and (not self.thread or not self.thread.is_alive()):
            self.recognizer.close()
            self.recognizer = None
