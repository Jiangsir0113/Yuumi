# 开发、构建与验证

## 环境

建议在 Windows x64、Python 3.14 的独立虚拟环境中安装 `requirements.txt`。当前依赖要求支持 x86-64-v2 的 CPU。仓库根目录可直接运行 `main.py`。

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py --state-file qa/dev.json --panel
```

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe main.py --self-test qa/source-test --state-file qa/source-state.json
.\.venv\Scripts\python.exe main.py --benchmark-all qa/all-actions.json --state-file qa/benchmark-state.json
```

界面测试会创建原生 Qt 窗口。`--benchmark-all` 仅在诊断中循环短的一次性动作，方便测量两秒活跃播放；正常玩法仍使用一次性动作语义。

## 生成 Windows exe

```powershell
.\.venv\Scripts\python.exe build.py --output-dir dist
.\.venv\Scripts\python.exe tools/verify_package.py dist/悠米.exe
```

构建脚本会隔离 PATH，避免不相关工具的 ICU DLL 被误收集；暂存运行清单中列出的有效素材，并包含许可证。部署到其他电脑前，还需在对应 CPU 和 Windows 环境上验证，不能只依赖开发机器启动成功。

## 素材维护

当前角色源图位于 `art-source/`，提示词保留在 JSON 中。下列步骤只处理已生成的像素，不重新绘制角色：

```powershell
.\.venv\Scripts\python.exe tools/prepare_assets.py
.\.venv\Scripts\python.exe tools/prepare_bridges.py
.\.venv\Scripts\python.exe tools/smooth_motion.py
```

这些脚本会提取完整姿势、清理色键、统一同一动作的缩放和落地基线，再编码 64 FPS 动画。更换源图后需要重新检查身份、轮廓、动作顺序和过渡效果。

`animation_engine.py` 将视觉时钟与 `cat_model.py` 的行为时长分开。姿势图连接坐姿、左右站姿、揣手与睡眠；新意图可以反向已有边。局部切换从上一张已显示画面开始，目标动作使用最近姿势相位，走路和小跑共享步态。

## 预览

```powershell
.\.venv\Scripts\python.exe tools/make_transition_preview.py qa/preview C:\path\to\ffmpeg.exe
```

提供 FFmpeg 路径时输出 H.264 MP4。工具使用真实动画引擎，包含快速改向和中途打断。若省略编码器参数，会使用 OpenCV 的 MPEG-4 编码，浏览器兼容性可能不同。

## 发布内容

源码、有效运行素材、角色源图和许可进入仓库。单文件 exe、预览和必要的测试记录可作为 GitHub Release 附件发布。个人存档、原始聊天附件、虚拟环境、日志和本机生成的 `.spec` 文件不应提交。
