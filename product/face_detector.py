"""YuNet face boxes; local inference only, no identity recognition."""
from pathlib import Path
import cv2


class FaceDetector:
    def __init__(self, root):
        self.model = cv2.FaceDetectorYN.create(
            str(Path(root)/'assets/face_detection_yunet_2023mar.onnx'), '', (640,360), .7, .3, 5000)

    def detect(self, frame):
        h,w = frame.shape[:2]
        frame = cv2.resize(frame,(640,round(640*h/w)))
        self.model.setInputSize((frame.shape[1],frame.shape[0]))
        _, faces = self.model.detect(frame)
        return ([] if faces is None else [tuple(map(float,f[:4])) for f in faces]), frame.shape[1], frame.shape[0]
