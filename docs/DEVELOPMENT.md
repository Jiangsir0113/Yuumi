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

界面测试会创建原生 Qt 窗口。`--benchmark-all` 每个动作预热两秒再测量两秒，分别记录冷切换和稳定播放的帧间隔；仅在诊断中循环短的一次性动作，正常玩法仍使用一次性语义。

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
.\.venv\Scripts\python.exe tools/prepare_v13_assets.py
.\.venv\Scripts\python.exe tools/prepare_v131_assets.py
.\.venv\Scripts\python.exe tools/smooth_motion.py
```

这些脚本会提取完整姿势、清理色键、统一同一动作的缩放和落地基线，再编码 64 FPS 动画。更换源图后需要重新检查身份、轮廓、动作顺序和过渡效果。

`animation_engine.py` 将视觉时钟与 `cat_model.py` 的行为时长分开。姿势图连接坐姿、左右站姿、揣手与睡眠；新意图可以反向已有边。局部切换从上一张已显示画面开始，目标动作使用最近姿势相位，走路和小跑共享步态。

v1.3 增加左右站姿直接转身，图允许环路，反向时比较两端的剩余路线。结构进入和局部混合期间暂停目标动作相位，行为时间按 `execution_ready` 推进。后台解码为预分配数组；缓存预算包含待完成解码。动态光流使用独立单线程工作队列，过期排队任务取消，主线程使用轻量混合连续回退。

v1.3.1 将抓板尺寸和源图宽高记录在 `assets/props/garlic-layout.json`；窗口绘制仍明确保持原始比例，避免固定矩形拉伸。缩放、圆槽和绳面接触共用几何参数。更新素材时应核对配置中的源图尺寸，运行不同桌宠大小及左右朝向的接触测试。

`scene_model.py` 无 Qt 依赖，保存世界坐标、物理状态和单个活动意图。到达和接触驱动喂食/拨球，不使用超时冒充成功。`scene_view.py` 只管理独立的小道具窗口，不创建覆盖整个桌面的输入层。抚摸按每次仿真步的真实接触时长计算；鼠标事件只更新轨迹和部位。

## 预览

```powershell
.\.venv\Scripts\python.exe tools/make_transition_preview.py qa/preview C:\path\to\ffmpeg.exe
```

提供 FFmpeg 路径时输出 H.264 MP4。工具使用真实动画引擎，包含快速改向和中途打断。若省略编码器参数，会使用 OpenCV 的 MPEG-4 编码，浏览器兼容性可能不同。

v1.3 场景预览可选安装 `imageio-ffmpeg` 后运行 `python tools/make_v13_preview.py qa/scene-preview`。该工具用真实窗口/场景渲染器采样受控的 64 FPS 时间线，包含抓绳、拨圆槽球、追球、喂食和快速打断。它是渲染输出预览，不是实时吞吐率测试。

## 发布内容

源码、有效运行素材、角色源图和许可进入仓库。单文件 exe、预览和必要的测试记录可作为 GitHub Release 附件发布。个人存档、原始聊天附件、虚拟环境、日志和本机生成的 `.spec` 文件不应提交。

历史版本必须保留，详见 [RELEASING.md](RELEASING.md)。

## v1.4.0 设备素材

使用 `python tools/prepare_v14_assets.py` 登记已生成的设备与互动源图，然后执行 `python tools/smooth_motion.py --states scratch eat sniff drink`。不要直接重跑旧版低位抓挠登记脚本覆盖新比例。`python tools/review_equipment.py` 生成实际渲染接触图；`python tools/make_v14_preview.py qa/v14-preview` 生成受控 64 FPS 时间线预览；`python tools/benchmark_scenes.py qa/scenes.json` 测六种原生场景。预览不是实时性能结果。产品来源见 PRODUCT-REFERENCES.md。
