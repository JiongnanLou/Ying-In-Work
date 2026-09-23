# 第三方组件

本项目组合了团队提供的模块和第三方运行组件。整体项目许可证尚由团队确定；这里的说明不为第三方代码另行授予许可。

| 组件 | 用途及来源 |
| --- | --- |
| Flask / Waitress | 本机 API 服务；版本见 `product/requirements.txt` |
| pywebview / WebView2 | Windows 桌面界面；WebView2 由系统单独安装 |
| pystray / pythonnet / clr_loader | 托盘和 Windows 悬浮窗 |
| OpenCV / NumPy / Pillow | 图像处理；许可证及第三方声明见 `licenses/` |
| YuNet | 本地人脸框检测；`product/assets/YuNet-LICENSE.txt` 和 `licenses/YuNet-source.txt` |
| MediaPipe | 本地手势识别；许可证和模型来源见 `licenses/mediapipe/`、`licenses/MediaPipe-model-source.txt` |
| FFmpeg 7.1 Gyan essentials | 独立进程进行摄像头取流；GPLv3 及源码/构建来源见 `licenses/FFmpeg-*` |
| Insta360 Link SDK | 官方设备控制 DLL 与控制台工具；来源见 `licenses/Insta360-SDK-source.txt`，适用原 SDK 条款 |
| PyInstaller | EXE 构建工具；许可见 `licenses/PyInstaller-COPYING.txt` |
| EyeLei / JiuZuo / MiZiCao 等团队模块 | 团队提供并整合；源码位于 `product/` |

源码仓库不包含 EXE/DLL 运行组件；配套运行组件包及 Windows 包保留对应许可说明。公开分发前，应由维护者确认第三方 SDK、模型和所选 FFmpeg 构建的许可要求。

`licenses/` 保留了已收集的原始许可证、版权说明和来源文件。项目 logo、名称及团队代码的使用授权由团队决定。
