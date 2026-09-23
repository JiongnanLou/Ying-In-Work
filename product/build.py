"""Run with the project virtual environment: python product/build.py."""
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
WORKSPACE=ROOT.parent
OUT=WORKSPACE/'output'/'萤InWork-1.3.1'
required = ['native/ffmpeg.exe','native/UVCCamera.dll','native/UVCCameraTest.exe',
            'native/link_camera_bridge.exe','assets/gesture_recognizer.task',
            'assets/face_detection_yunet_2023mar.onnx']
missing = [name for name in required if not (ROOT/name).is_file()]
if missing:
    raise SystemExit('Missing build inputs: '+', '.join(missing)+
                     '\nPrepare the matching runtime archive using tools/setup_runtime.py first.')
OUT.mkdir(parents=True,exist_ok=True)
subprocess.run([sys.executable,'-m','PyInstaller',str(ROOT/'main.py'),
    '--noconfirm','--clean','--onefile','--windowed','--name','萤InWork',
    '--icon',str(ROOT/'assets/ying.ico'),
    '--version-file',str(ROOT/'version_info.txt'),
    '--distpath',str(OUT),'--workpath',str(WORKSPACE/'tmp/exe-build'),
    '--specpath',str(WORKSPACE/'tmp'),
    '--paths',str(ROOT),
    '--add-data',f'{ROOT / "frontend"};frontend',
    '--add-data',f'{ROOT / "assets"};assets',
    '--add-data',f'{ROOT / "voice.ps1"};.',
    '--add-binary',f'{ROOT / "native/UVCCamera.dll"};native',
    '--add-binary',f'{ROOT / "native/link_camera_bridge.exe"};native',
    '--add-binary',f'{ROOT / "native/UVCCameraTest.exe"};native',
    '--add-binary',f'{ROOT / "native/ffmpeg.exe"};native',
    '--hidden-import','cv2_enumerate_cameras.windows_backend',
    '--hidden-import','webview.platforms.edgechromium',
    '--hidden-import','pystray._win32',
    '--collect-all','mediapipe',
    '--exclude-module','pytest','--exclude-module','tkinter',
    '--exclude-module','PyQt5','--exclude-module','PyQt6','--exclude-module','PySide6',
],check=True)
print(OUT/'萤InWork.exe')
