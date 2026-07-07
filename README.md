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

### 路线图

- 显卡和显存检测
- 根据硬件推荐可运行模型
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
http://127.0.0.1:58001
```

停止 LLMGarage：

```bat
stop.bat
```

### 本地数据

LLMGarage 会在 `data/` 下保存本地预设、日志和 pid 文件。`data/presets.json` 可能包含你的本机路径和模型路径，默认不会被 Git 追踪。

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

### Roadmap

- GPU and VRAM detection
- Hardware-aware model recommendations
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
http://127.0.0.1:58001
```

Stop LLMGarage:

```bat
stop.bat
```

### Local Data

LLMGarage stores local presets, logs, and pid files under `data/`. `data/presets.json` may contain local filesystem paths and model paths, so it is ignored by Git by default.

### Tests

```bash
python -m unittest discover -s tests -p "test_*.py"
```

### License

This project is open source under the MIT License.
