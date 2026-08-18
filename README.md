# LLMGarage

[中文](#中文) | [English](#english)

## 中文

LLMGarage 是一个面向新手的本地大模型启动工具。它当前提供一个轻量的 Web 控制台，用来配置、启动、停止和测试 `llama.cpp` 的 `llama-server.exe`，并保存本机常用的 GGUF 模型运行预设。

目标是逐步发展成一站式本地 AI 应用：检测显卡、推荐可运行模型、下载 llama.cpp、下载模型，并帮助用户在自己的电脑上快速跑起本地大模型。

### 当前功能

- 管理多个本地运行预设
- 配置 `llama-server.exe` 和 GGUF 模型路径
- 设置 host、port、上下文长度、GPU layers、线程数、batch、parallel、temperature、top-p 等参数
- 生成启动命令预览
- 启动和停止由 LLMGarage 管理的 `llama-server.exe`
- Windows 下支持强制停止所有 `llama-server.exe` 进程
- 查看运行日志
- 调用 `/health`、`/v1/models` 或 OpenAI 兼容接口做简单连通性测试
- 控制接口拒绝跨站写入，并只允许测试本机 llama-server
- 检测 Windows、CPU 核心/线程、总计与可用 RAM、NVIDIA GPU、总计与可用 VRAM、驱动和 `nvidia-smi`
- 在非 NVIDIA 或探测失败时自动采用保守 CPU 推荐路线
- 用当前空闲资源和透明预算规则推荐 8 个官方 Qwen GGUF，同时展示稳妥档与“吃力可跑”档
- 每张模型卡同时提供魔搭社区和 Hugging Face 链接，兼顾国内访问
- 逐项讲解参数量、量化、GGUF、权重内存、KV cache、CPU 推理、GPU 全卸载、CPU+GPU 混合卸载和 `--gpu-layers` 选取原理
- 通过独立的 `/advisor` 页面查看机况、模型推荐和学习内容，默认 `/` 保持为运行控制台

只读 API：

- `GET /api/app`：返回当前 LLMGarage 进程、版本和能力列表
- `GET /api/hardware`：返回硬件事实、检测来源、置信度与警告
- `GET /api/recommendations`：返回同一份硬件快照、推荐规则、模型卡片、内存/卸载预算和学习内容

P1 的规则、模型数据和 llama.cpp 卸载语义均记录在 [P1 研究说明](docs/P1_RESEARCH.md)，并固定了调研日期与上游源码版本。

### 路线图

- 从推荐结果生成并确认保存 preset 草稿
- 自动下载或更新 llama.cpp
- 集成魔搭社区模型下载
- 更友好的新手引导流程
- 桌面应用打包

### 快速开始

需要：

- Windows
- Python 3
- 已下载的 `llama-server.exe`
- 一个 `.gguf` 模型文件

启动：

```bat
start.bat
```

或直接运行：

```bash
python app.py
```

然后打开：

```text
控制台：http://127.0.0.1:58001/
机况、推荐与学习台：http://127.0.0.1:58001/advisor
```

再次运行 `start.bat` 时，启动器会先确认并替换同端口的旧 LLMGarage，再加载当前代码，避免“新版前端连接旧版后端”造成检测 API 404。启动器会优先正常关闭旧实例；仅当已确认是 LLMGarage 且旧版本没有释放端口时，才终止该监听进程。

停止 LLMGarage：

```bat
stop.bat
```

### 本地数据

LLMGarage 会在 `data/` 下保存本地预设、日志和 pid 文件。预设通过原子替换保存，运行日志达到 2 MiB 后轮转并保留 3 份历史文件。`data/presets.json` 可能包含你的本机路径和模型路径，默认不会被 Git 追踪。

### 测试

```bash
python -m unittest discover -s tests -p "test_*.py"
```

### 许可证

本项目基于 MIT License 开源。

## English

LLMGarage is a beginner-friendly launcher for local LLMs. It currently provides a lightweight web console for configuring, starting, stopping, and testing `llama.cpp` `llama-server.exe` with local GGUF model presets.

The long-term goal is an all-in-one local AI app that can detect GPUs, recommend runnable models, download llama.cpp, download models, and help new users run local LLMs on their own machines quickly.

### Current Features

- Manage multiple local runtime presets
- Configure `llama-server.exe` and GGUF model paths
- Tune host, port, context size, GPU layers, threads, batch, parallel, temperature, top-p, and advanced arguments
- Preview the generated startup command
- Start and stop the `llama-server.exe` process managed by LLMGarage
- Force-stop all `llama-server.exe` processes on Windows
- View runtime logs
- Run simple connectivity checks through `/health`, `/v1/models`, or OpenAI-compatible endpoints
- Reject cross-origin control requests and restrict connectivity tests to local llama-server instances
- Detect Windows, CPU cores/threads, total and available RAM, NVIDIA GPUs, total and free VRAM, drivers, and `nvidia-smi`
- Fall back to a conservative CPU recommendation path when NVIDIA detection is unavailable
- Recommend eight official Qwen GGUF models using current free resources, with both stable and stretch tiers
- Link every model card to both ModelScope and Hugging Face for accessible downloads
- Teach parameters, quantization, GGUF, weight memory, KV cache, CPU inference, full GPU offload, hybrid CPU/GPU offload, and `--gpu-layers` selection
- Keep the runtime console at `/` and expose hardware guidance and learning on the dedicated `/advisor` page

Read-only APIs:

- `GET /api/app`: the current LLMGarage process, version, and capability list
- `GET /api/hardware`: hardware facts, detection source, confidence, and warnings
- `GET /api/recommendations`: the hardware snapshot, rules, model cards, memory/offload budgets, and learning content

The recommendation rules, model data, and llama.cpp offload semantics are documented with pinned upstream sources in [the P1 research notes](docs/P1_RESEARCH.md).

### Roadmap

- Generate user-confirmed preset drafts from recommendations
- Automatic llama.cpp download and update flow
- ModelScope model downloads
- Friendlier onboarding for beginners
- Desktop app packaging

### Quick Start

Requirements:

- Windows
- Python 3
- A downloaded `llama-server.exe`
- A `.gguf` model file

Start:

```bat
start.bat
```

Or run directly:

```bash
python app.py
```

Then open:

```text
Console: http://127.0.0.1:58001/
Hardware advisor: http://127.0.0.1:58001/advisor
```

Running `start.bat` again now verifies and replaces an older LLMGarage instance on the same port before loading the current code. It first requests a graceful shutdown and only terminates the listener if it is a verified LLMGarage process that did not release the port. This prevents a newly served frontend from calling stale backend routes.

Stop LLMGarage:

```bat
stop.bat
```

### Local Data

LLMGarage stores local presets, logs, and pid files under `data/`. Presets are saved with atomic replacement, and runtime logs rotate at 2 MiB with 3 backups retained. `data/presets.json` may contain local filesystem paths and model paths, so it is ignored by Git by default.

### Tests

```bash
python -m unittest discover -s tests -p "test_*.py"
```

### License

This project is open source under the MIT License.
