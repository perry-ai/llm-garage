# LLMGarage Product Roadmap / 产品路线图

## Product Tone / 产品调性

LLMGarage 是一个给本地 AI 玩家准备的“鼓捣车库”。它帮助用户在自己的电脑上跑起本地大模型，而不要求用户一开始就懂 llama.cpp、GGUF、量化、显存估算和模型选择。

LLMGarage is a local AI garage for people who want to get their own machine running a local model without first becoming a llama.cpp operator, model curator, quantization expert, or hardware planner.

它应该像一张结实的车库工作台：实用、可见、宽容，也带一点鼓捣东西的乐趣。用户要感觉这台机器是自己的，LLMGarage 不是把所有东西藏进黑盒，而是帮用户安全启动，并用人话解释发生了什么。

The product should feel like a sturdy workbench in a small garage: practical, visible, forgiving, and a little playful. The user should always feel that the machine is theirs. LLMGarage should not hide everything behind magic; it should help users start safely, explain what it is doing, and leave the tools on the bench for deeper tinkering.

它不是模型商店，也不是裸命令行封装。它更像一个本地运行时工作间：有控制台、有新手流程图、有稳妥推荐，也有能让用户慢慢学会硬件、模型大小、量化、内存和上下文取舍的学习表面。

It is not a glossy model store and not a bare command-line wrapper. It is a guided local runtime workshop: a console, a beginner wall chart, a stable recommendation assistant, and a learning surface for hardware, model size, quantization, memory, and context tradeoffs.

长期来看，LLMGarage 的身份是：**本地 AI 鼓捣车库**。新手可以快速把第一台“本地模型车”开起来，好奇的人可以继续打开引擎盖，逐步理解每一个旋钮。

The long-term identity is: **a local tinkering garage for AI**. New users can get their first model running quickly, while curious users can gradually open the hood and learn what every knob does.

## Target User / 目标用户

第一目标用户是 Windows 新手：听说过本地大模型，但不知道该下载哪个 llama.cpp、哪个 GGUF、自己的显卡能跑什么，也不知道参数量、量化、VRAM、RAM 和上下文长度意味着什么。

The first target user is a Windows beginner who has heard about local LLMs but does not know which llama.cpp build to download, which GGUF model to choose, what their GPU can run, or what model parameters, quantization, VRAM, RAM, and context size mean.

同时，LLMGarage 也要继续服务半熟手：他们可能已经有 llama.cpp 或 GGUF，只是需要一个方便的本地控制台来管理预设、启动服务、测试接口和查看日志。

LLMGarage should also remain useful for semi-experienced users who already have llama.cpp or GGUF models and want a convenient local control panel.

## Core Success Experience / 核心成功体验

MVP 的成功标准很具体：用户从一个未配置的 LLMGarage 出发，最后能在本机收到一次本地模型回复。

The MVP succeeds when a user can go from an unconfigured LLMGarage installation to receiving one reply from a local model.

```text
检测电脑 -> 推荐稳妥模型 -> 准备 llama.cpp -> 准备 GGUF -> 生成预设 -> 启动服务 -> 测试 Prompt -> 收到回复
Detect computer -> recommend a stable model -> prepare llama.cpp -> prepare GGUF -> generate preset -> start server -> test prompt -> receive reply
```

第一次成功要刻意克制：一个模型、一个本地服务、一个测试 Prompt、一次成功回复。聊天 UI、知识库、Agent、模型市场都可以之后再扩展。

The first success is intentionally modest: one model, one local server, one prompt, one successful response. Chat UI, knowledge bases, agents, and model marketplaces can come later.

## Product Principles / 产品原则

### The Workbench Is Always There / 工作台一直都在

默认入口仍然是控制台。LLMGarage 打开后应该先看到主工作台：预设、路径、参数、命令预览、启动停止、接口测试和日志。

The default route remains the control console. LLMGarage should open to the main workbench: presets, paths, parameters, command preview, start/stop actions, API tests, and logs.

新手引导是帮助，不是打扰。用户需要时可以进入，不需要时控制台仍然安静地在那里。

Beginner guidance is help, not interruption. Users can enter it when needed, while the console stays quietly available.

### The Onboarding Page Is A Wall Chart / Onboarding 是墙上的流程图

`/onboarding` 像挂在车库墙上的操作流程图。用户想看就看，想跟着走就跟着走，离开时不应该自动污染当前配置。

`/onboarding` should feel like an operation chart hanging above the workbench. Users can open it whenever they want help, follow the flow, and leave without changing anything automatically.

引导可以生成 preset 草案，但必须在用户确认后才保存。

The onboarding flow may generate a preset draft, but it should only save after explicit user confirmation.

### Success Beats Ambition / 成功优先于野心

默认推荐应该优先选择“稳稳能跑”的模型，而不是硬件可能勉强承受的最大模型。

Default recommendations should prefer a stable model that is likely to run over the largest model the hardware might barely tolerate.

可以展示更强或实验性的选项，但首推应该优化启动成功率、下载体积、运行稳定性和解释成本。

LLMGarage can show stronger or experimental options, but the first recommendation should optimize for success rate, download size, runtime stability, and explainability.

### Teach While Doing / 边做边教

LLMGarage 应该在用户做选择时顺手解释概念：模型参数量、量化、GGUF 文件大小、权重内存、KV cache、上下文长度和显存余量。

LLMGarage should teach concepts at the moment they matter: model size, quantization, GGUF file size, model weight memory, KV cache, context length, and VRAM headroom.

推荐卡片先给一句人话解释，再提供“为什么推荐它？”的展开说明。不要把新手一开始就扔进术语海里。

Recommendation cards should start with one plain-language explanation, then offer an expandable "why this recommendation?" section. Do not throw beginners into a sea of terms.

### Keep The First Recommendation Set Small / 第一批推荐少而稳

第一版不做完整模型市场。推荐列表控制在 5-8 个经过挑选的模型，让新手先少做选择、少踩坑。

The first version should not become a full model marketplace. The recommendation list should stay around 5-8 carefully chosen models so beginners face fewer choices and fewer traps.

想探索更多模型的用户，可以跳转 ModelScope 或 Hugging Face 自己找。

Users who want broader exploration can jump to ModelScope or Hugging Face.

## Product Shape / 产品形态

### `/` Console / 控制台

默认入口是控制台，也就是 LLMGarage 的主工作台。

The default entry is the console, the main LLMGarage workbench.

它包含：

It contains:

- 预设管理 / Preset management.
- `llama-server.exe` 路径和 GGUF 模型路径 / Server path and GGUF model path.
- 运行参数 / Runtime parameters.
- 启动命令预览 / Generated command preview.
- 校验、启动、停止、停止全部 / Validate, start, stop, and kill-all actions.
- API 健康检查和 Prompt 测试 / API health check and prompt test.
- 运行日志 / Runtime logs.
- 进入 `/onboarding` 的入口 / Entry point to `/onboarding`.

### `/onboarding` Wall Chart / 新手流程图

`/onboarding` 是按需打开的新手流程图，不是默认首页，也不记录“是否完成”。

`/onboarding` is an on-demand beginner wall chart. It is not the default home page and does not need a stored "completed" state.

它引导用户：

It guides users through:

1. 检测硬件 / Detect hardware.
2. 理解当前机器 / Understand the detected machine.
3. 选择稳妥推荐模型 / Pick a stable recommended model.
4. 准备 llama.cpp / Prepare llama.cpp.
5. 准备或定位 GGUF / Prepare or locate a GGUF model.
6. 查看生成的 preset 草案 / Review a generated preset draft.
7. 确认是否保存 / Confirm whether to save it.
8. 回到控制台 / Return to the console.

## Roadmap / 路线图

### Phase 1: Hardware Detection And Recommendation Display / 阶段 1：硬件检测与推荐展示

先做第一条纵向薄片：能检测机器，并解释为什么推荐某些模型。这个阶段暂时不需要下载或启动。

Build the first vertical slice: detect the machine and explain why certain models are recommended. This phase does not need to download or start anything yet.

范围 / Scope:

- 新增硬件检测 API / Add a hardware detection API.
- 优先做好 Windows + NVIDIA / Prioritize Windows + NVIDIA.
- 检测 GPU、VRAM、RAM、CPU 核心/线程、操作系统和 `nvidia-smi` / Detect GPU, VRAM, RAM, CPU cores/threads, OS, and `nvidia-smi`.
- 非 NVIDIA 或检测失败时走 CPU 保守路线 / Treat non-NVIDIA or failed detection as a conservative CPU path.
- 增加透明的推荐规则表 / Add a transparent recommendation rules table.
- 展示少量稳妥推荐模型 / Show a small set of stable recommended models.
- 解释推荐原因 / Explain why each model is recommended.
- 讲清参数量、量化、内存和 KV cache / Explain parameters, quantization, memory, and KV cache.

推荐姿态 / Recommendation posture:

- VRAM < 4GB：CPU/小模型路线，1.5B 或 3B Q4。
- VRAM 4-6GB：3B 或保守 7B Q4。
- VRAM 约 8GB：7B/8B Q4 作为安全默认，更大模型作为尝试。
- VRAM 约 12GB：7B/8B 舒适，14B Q4 可选。
- VRAM 16GB+：可以出现 14B Q4 或更大模型，但安全默认仍要清楚。

- VRAM under 4GB: CPU/small-model route, 1.5B or 3B Q4.
- VRAM 4-6GB: 3B or conservative 7B Q4.
- VRAM around 8GB: 7B/8B Q4 as the safe default, larger models as optional experiments.
- VRAM around 12GB: 7B/8B comfortably, 14B Q4 as a stronger option.
- VRAM 16GB and above: 14B Q4 or larger options can appear, but the safe default should still be clear.

### Phase 2: Preset Drafts From Recommendations / 阶段 2：推荐结果生成预设草案

把推荐结果打通到现有控制台预设系统。

Connect recommendation output to the existing console preset system.

范围 / Scope:

- 从推荐模型生成 preset 草案 / Generate a preset draft from a selected recommendation.
- 填入建议的 `ctxSize`、`gpuLayers`、`threads` 和推荐理由 / Fill recommended `ctxSize`, `gpuLayers`, `threads`, and rationale.
- 写入 `data/presets.json` 前必须用户确认 / Require user confirmation before writing to `data/presets.json`.
- 保存后回到控制台，并选中该 preset / Return to the console with the saved preset selected.

### Phase 3: Semi-Automatic llama.cpp Installation / 阶段 3：半自动安装 llama.cpp

增加新手友好的运行时准备流程，但先不做完整版本管理器。

Add a beginner-friendly runtime preparation flow without building a full version manager yet.

范围 / Scope:

- 提供推荐的 Windows llama.cpp release / Offer a recommended Windows llama.cpp release.
- 可行时下载 release 压缩包 / Download the release archive when feasible.
- 解压到 LLMGarage 管理目录 / Extract into an LLMGarage-managed runtime directory.
- 自动定位 `llama-server.exe` / Locate `llama-server.exe`.
- 保存当前运行时路径 / Store the selected runtime path.
- 暂缓多版本切换和回滚 / Defer multi-version switching and rollback.

建议目录 / Suggested layout:

```text
data/runtime/llama.cpp/<version>/llama-server.exe
```

### Phase 4: ModelScope Model Preparation / 阶段 4：ModelScope 模型准备

先支持 ModelScope，再支持 Hugging Face。ModelScope 对目标用户更重要，也更适合作为第一条下载协助路线。

Support ModelScope first, then Hugging Face. ModelScope is important for the intended user base and is a better first download-assistance path.

范围 / Scope:

- 保持推荐模型少而精选 / Keep the first model list small and curated.
- 为推荐模型提供 ModelScope 链接 / Provide ModelScope links for recommendations.
- 支持打开社区页面 / Allow opening the model page.
- 支持复制下载链接或命令 / Allow copying a download link or command.
- 支持选择手动下载的 GGUF 文件 / Allow selecting a manually downloaded GGUF file.
- 只有直链简单时才尝试内置下载 / Attempt built-in direct download only when the URL is straightforward.
- 下载失败时回退到手动下载加文件选择 / Fall back to manual download plus file selection.

第一版要做“模型准备助手”，不是完美下载器。

The first version should be a model preparation assistant, not a perfect download manager.

### Phase 5: `/onboarding` Wall Chart / 阶段 5：`/onboarding` 新手流程图

核心能力稳定后，再把它们串成单独的新手流程页。

After the core pieces exist, connect them into a dedicated beginner flow page.

范围 / Scope:

- 新增独立的 `/onboarding` HTML 页面 / Add `/onboarding` as a separate HTML page.
- `/` 继续作为默认控制台 / Keep `/` as the default console.
- 展示完整新手流程 / Present the full beginner flow.
- 复用硬件检测、推荐、运行时准备、模型准备和 preset 草案 API / Reuse hardware detection, recommendations, runtime preparation, model preparation, and preset draft APIs.
- 只在用户确认后保存 / Save only after explicit user confirmation.

### Phase 6: Hugging Face Support / 阶段 6：支持 Hugging Face

ModelScope 路线稳定后，再加入 Hugging Face。

Add Hugging Face after the ModelScope path is useful and stable.

范围 / Scope:

- 推荐模型增加 Hugging Face 链接 / Add Hugging Face links to recommended models.
- 支持用户粘贴 Hugging Face 模型或文件链接 / Support user-pasted Hugging Face model or file links.
- 处理仓库内文件选择 / Handle file selection inside model repositories.
- 后续考虑镜像、授权、断点续传和失败恢复 / Later consider mirrors, gated models, auth, resume, and failure recovery.

## Open Product Questions / 待定问题

- 第一批 5-8 个推荐模型具体选哪些？ / Which exact 5-8 models should be in the first curated list?
- 默认推荐哪个 llama.cpp release 渠道？ / What llama.cpp release channel should be recommended by default?
- 推荐规则应该预留多少显存余量？ / How much VRAM headroom should the rules reserve?
- 推荐规则放在 Python、JSON，还是混合格式？ / Should recommendation rules live in Python, JSON, or a mixed format?
- `data/` 是否要逐步形成用户可见的 `garage/` 目录结构？ / Should `data/` evolve into a user-visible `garage/` layout?
- 什么时候从 Web 控制台升级到桌面打包应用？ / When should LLMGarage graduate from web console to packaged desktop app?

## Next Build Slice / 下一步开发切片

下一步最适合做：

The next implementation slice should be:

```text
硬件检测 API + 推荐规则 + 推荐展示
Hardware detection API + recommendation rules + recommendation display
```

这一步定义的是 LLMGarage 的“判断力”：它能看懂一台机器，并用人话解释这台机器适合先跑什么。这个判断力立住以后，后面的下载、安装、onboarding 和 preset 生成才都有清晰的落点。

This step defines LLMGarage's judgment. Once it can look at a machine and explain what it can probably run, download, installation, onboarding, and preset generation all have a clearer place to attach.
