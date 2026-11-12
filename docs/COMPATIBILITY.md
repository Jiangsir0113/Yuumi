# 兼容性与已知问题

## 当前发布目标

- Windows 64 位；使用 Python 3.14、PySide6 6.10.1、NumPy 2.5.4、OpenCV headless 5.0.0.93 和 Pillow 12.2.0 构建。
- 当前 NumPy 构建需要 `X86_V2`，即 x86-64-v2 指令集。
- 当前 OpenCV 构建的基础指令集为 SSE、SSE2、SSE3，其余指令集按可用情况分派。
- 实际多显示器摆放、旧硬件、Windows ARM 模拟层和不同虚拟机配置尚未全面验证。

## 启动时报 X86_V2 不支持

典型错误：

```text
NumPy was built with baseline optimizations:
(X86_V2) but your machine doesn't support:
(X86_V2)
```

这表示 exe 内置 NumPy 的最低 CPU 要求高于当前运行环境提供的指令集。可能与旧 CPU、虚拟机 CPU 特征屏蔽或模拟环境有关，不能只根据该截图确定具体硬件型号。

NumPy 从 2.4 开始将 x86 默认 baseline 提高到 x86-64-v2：

- [NumPy 2.4 发布说明](https://numpy.org/doc/stable/release/2.4.0-notes.html)
- [CPU 构建选项与旧 CPU 目标](https://numpy.org/doc/2.4/reference/simd/build-options.html)

独立 exe 使用内置依赖，在电脑上另行安装 Python 或 NumPy不会替换它。修复方向是重新选择兼容的依赖或以较低 baseline 编译，然后重新打包，并检查 OpenCV 等其他原生库。

低指令集兼容版目前尚未构建和验证。请在报告问题时提供 CPU 型号、Windows 版本、是否使用虚拟机和完整错误文字；不要将当前发布文件视为通用旧电脑版本。

## 动画帧率

动作素材按 64 FPS 采样，窗口与动作播放采用独立计时。实际显示受 CPU、显示器刷新率、系统调度和负载影响，不保证任意硬件在每一帧都达到同样帧间隔。
