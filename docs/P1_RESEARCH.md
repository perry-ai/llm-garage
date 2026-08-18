# P1 硬件检测、模型推荐与 llama.cpp 卸载研究

> 调研日期：2026-07-31
>
> 用途：为 LLMGarage P1 的硬件检测 API、透明推荐规则和学习内容提供实现依据。
> llama.cpp 基线：[`ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31`](https://github.com/ggml-org/llama.cpp/tree/ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31)。llama.cpp 参数和内存分配仍在快速变化，产品应显示“规则版本”和“估算而非承诺”。

## 结论摘要

1. Windows + NVIDIA 的首选检测入口是 `nvidia-smi` 的选择性 CSV 查询；同时记录总显存和**检测当下的可用显存**。总显存用于给机器分档，可用显存用于决定当前能否安全启动。
2. 没有 `nvidia-smi`、命令超时、返回非零、字段无法解析、没有 NVIDIA GPU，均进入保守 CPU 路线；不要把 Windows `Win32_VideoController.AdapterRAM` 当成可靠的高显存检测值。
3. 当前 llama.cpp 的 `-ngl/--gpu-layers` 接受整数、`auto` 或 `all`，默认 `auto`。当前自动适配默认给每个设备留 1024 MiB，并可把上下文最低降到 4096；这应成为新版本运行时的优先选择，但 LLMGarage 仍需给出可解释的数值估算，并兼容尚不支持 `auto` 的旧版二进制。
4. 数值 `gpu-layers` 不是“GPU 使用百分比”。在本次锁定的 llama.cpp 代码中，输入层总是留在 CPU；数值卸载从靠后的重复层开始，输出层也计入可卸载层。因此一个含 `N` 个重复层的普通稠密模型，完全卸载通常是 `N + 1` 个可卸载层，最稳妥的跨模型写法是 `all`。
5. 显存不是只装 GGUF 权重。还要预留 KV cache、计算缓冲区、CUDA/驱动与桌面占用。推荐首跑使用 4096 上下文、单并发、Q4_K_M，并至少保留 `max(1 GiB, 总显存的 15%)`；这个 15% 是 LLMGarage 的保守产品规则，不是上游保证。
6. 第一批模型建议控制为 8 个官方 Qwen GGUF：0.5B、1.5B、3B、4B、7B、8B、14B 与 30B-A3B，覆盖约 0.49–18.60 GB 的 Q4_K_M 文件。清单既给安全首推，也保留需要混合卸载或接受更慢速度的“吃力可跑”档。3B 使用 Qwen Research License，其余表中模型页面标示为 Apache-2.0，界面应显式展示许可证差异，并同时提供魔搭社区与 Hugging Face 入口。

## 1. 硬件检测

### 1.1 NVIDIA 检测命令

建议 Windows 首选：

```powershell
nvidia-smi --query-gpu=index,name,memory.total,memory.free,driver_version --format=csv,noheader,nounits
```

NVIDIA 文档规定：

- `--query-gpu` 接受逗号分隔的属性列表；`--format=csv` 是必选格式，`noheader` 和 `nounits` 可用于稳定解析。[NVIDIA：Selective Query Options](https://docs.nvidia.com/deploy/nvidia-smi/index.html#selective-query-options)
- `Product Name` 是 GPU 的官方产品名。[NVIDIA：Product Name](https://docs.nvidia.com/deploy/nvidia-smi/index.html#product-name)
- FB Memory 的 `Total` 是板载显存总量，`Free` 是检测当时可用量。[NVIDIA：FB Memory Usage](https://docs.nvidia.com/deploy/nvidia-smi/index.html#fb-memory-usage)
- `nvidia-smi` 的返回码能区分成功、驱动未加载、NVML 缺失、设备不可访问等情况。[NVIDIA：Return Value](https://docs.nvidia.com/deploy/nvidia-smi/index.html#return-value)

实现要求：

- 使用参数数组调用进程，不经过 shell。
- 设置短超时（建议 3–5 秒）。
- 支持多行输出，即多块 GPU；保留每块卡的数据，不只返回第一块。
- 原始单位是 MiB。API 内部最好保留整数 MiB，展示层再转 GiB。
- 驱动版本是可选展示字段，不应让它拖垮 GPU/显存检测。NVIDIA 当前文档已把旧的 `Driver Version` 标为 deprecated、推荐 `KMD Version`；为兼容存量 Windows 驱动，可先查询广泛支持的 `driver_version`，若该字段导致命令失败，再降级为不含驱动字段的核心显存查询。
- 同时返回 `nvidiaSmiAvailable`、命令路径、退出码或简化后的失败原因，以便用户理解为什么走 CPU 路线。
- 推荐引擎以“单卡能容纳的安全方案”为 P1 默认。多卡层切分需要考虑 `split-mode` 与设备间差异，留到后续高级功能。

### 1.2 `memory.total` 和 `memory.free` 的可靠性边界

`memory.total` 不是显卡包装盒上的绝对容量：ECC 可让可报告总量减少几个百分点，驱动即使没有活跃工作也会保留少量显存。`memory.free` 是瞬时值，桌面、浏览器、游戏或其他推理进程都可能在随后改变它；在某些 NUMA/操作系统内存管理场景，报告还可能存在偏差。[NVIDIA：FB Memory Usage 说明](https://docs.nvidia.com/deploy/nvidia-smi/index.html#fb-memory-usage)

因此 API 应返回：

```text
totalMiB       机器分档依据
freeMiB        当前启动估算依据
observedAt     检测时间
source         "nvidia-smi"
confidence     "high" | "degraded"
warnings[]     动态占用、解析降级等
```

界面文案应是“按当前空闲显存估算”，不要写“你的显卡一定能运行”。

### 1.3 CPU、RAM 与操作系统

P1 至少返回：

- 操作系统名称、版本、架构；
- CPU 名称；
- 物理核心数；
- 逻辑线程数；
- 总 RAM、当前可用 RAM；
- NVIDIA GPU 列表及显存；
- `nvidia-smi` 是否可用。

Windows 可通过 CIM 获取 CPU 名称、`NumberOfCores` 和 `NumberOfLogicalProcessors`。若 CIM 调用失败，`os.cpu_count()` 只能作为逻辑线程数降级值，物理核心应返回 `null`，不能假装二者相同。RAM 检测失败时也应返回 `null + warning`，不要返回 0。

### 1.4 CPU 保守路线

出现以下任一情况即走 CPU 路线：

- 非 NVIDIA GPU；
- NVIDIA GPU 存在，但 `nvidia-smi` 不存在、超时或解析失败；
- 可用显存未知；
- 当前可用显存不足以覆盖安全预算。

CPU 路线不是“不能运行”，而是：

- `gpuLayers = 0`；
- 若要明确禁止任何设备卸载，支持时同时使用 `--device none`；官方帮助把 `none` 定义为“不卸载”；
- 使用当前可用 RAM 做硬门槛；
- 首推 1.5B 或 3B Q4_K_M；
- 初始上下文 4096；
- 生成线程先取物理核心数，物理核心未知时用逻辑线程数的一半并限制至少为 1；这是保守起点，最终应以本机基准测试调整。

llama.cpp 官方定位包含纯 CPU 推理，也明确支持 CPU+GPU 混合推理，让大于总显存的模型得到部分加速。[llama.cpp README](https://github.com/ggml-org/llama.cpp/blob/ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31/README.md#description)

## 2. 要给用户讲清的 llama.cpp 知识

### 2.1 参数量、GGUF、量化不是同一个概念

- **参数量**（如 7B）表示模型包含多少可学习参数，通常参数更多意味着更大的能力上限和更高资源需求，但不能直接代表质量。
- **GGUF** 是 llama.cpp 使用的模型容器；文件除权重外还含模型结构、词表和运行元数据。
- **量化** 把高精度权重转换为更低精度表示，减少文件与运行内存，也可能加快推理，但会带来不同程度的精度损失。llama.cpp 官方量化文档明确说明这一取舍。[llama.cpp：quantize](https://github.com/ggml-org/llama.cpp/blob/ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31/tools/quantize/README.md#quantize)
- `Q4_K_M` 不是“所有权重严格 4 bit”。官方工具默认允许 K-quant 混合；`--pure` 才会禁用混合并让所有张量使用同一类型。[llama.cpp：quantize options](https://github.com/ggml-org/llama.cpp/blob/ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31/tools/quantize/README.md#quantize-the-gguf)

产品文案可写：

> 参数量像发动机排量，量化像压缩与材料方案，GGUF 文件大小才是本次要搬进内存的权重基线。Q4_K_M 通常是本项目首跑时在体积和质量之间的折中点，但不是无损格式。

### 2.2 内存由哪些部分组成

一次推理至少包含：

1. **模型权重**：以 GGUF 文件大小为可解释的近似基线；
2. **KV cache**：保存上下文中每个 token、每层注意力需要复用的 K/V 状态；
3. **计算缓冲区**：受 batch、ubatch、后端、Flash Attention 和模型结构影响；
4. **运行时开销**：CUDA context、驱动、图形桌面与其他应用；
5. **主机侧内存**：未卸载权重、映射页、CPU 计算缓冲和应用本身。

所以不能用“8 GB 显存大于 5 GB GGUF”直接得出一定能全卸载。

### 2.3 KV cache 为什么随上下文变大

llama.cpp 当前实现按层创建 K、V 张量，维度包含该层的 GQA K/V 宽度、KV 槽数量和 stream 数；这说明 KV 大小随上下文槽数量、层数、KV 头宽度、并行 stream 和数据类型共同变化。[llama-kv-cache.cpp](https://github.com/ggml-org/llama.cpp/blob/ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31/src/llama-kv-cache.cpp#L204-L248)

对本清单中的普通稠密 GQA 模型、单 stream、K/V 都为 F16，可做教学估算：

```text
KV bytes
≈ 2(K+V) × 层数 × 上下文 token 数 × KV 头数 × head_dim × 每元素字节数
```

其中 F16 每元素 2 字节。这个公式不应泛化到 MLA、滑动窗口、混合/可变量宽 KV、量化 KV、多并发或未来实现；这些情况应以 llama.cpp 启动日志打印的实际 KV buffer 为准。

`llama-server` 当前提供：

- `-c/--ctx-size`：上下文大小；
- `-b/--batch-size`：逻辑最大 batch；
- `-ub/--ubatch-size`：物理最大 batch；
- `-ctk/-ctv`：K/V cache 数据类型，默认 F16；
- `--kv-offload/--no-kv-offload`：KV 是否卸载；
- `--device none`：不使用设备卸载；
- `-t/--threads`：生成时 CPU 线程数。

参数定义见锁定版本的 [`tools/server/README.md`](https://github.com/ggml-org/llama.cpp/blob/ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31/tools/server/README.md#common-params)。

首跑推荐 4096 而不是直接使用模型标称 32768，原因是 KV 和部分计算缓冲会随上下文增长。模型“支持 32K”表示架构/训练能力，不表示每台机器都应默认分配 32K。

### 2.4 CPU 推理、GPU 全卸载、CPU+GPU 混合卸载

**CPU 推理**

- `gpu-layers = 0`，并在需要保证纯 CPU 时使用 `--device none`；仅把层数设成 0 不应被产品解释成“任何版本、任何后端都绝不会触碰 GPU”；
- 主要受可用 RAM、内存带宽、CPU 指令集和线程设置影响；
- 优点是兼容、容量通常比显存大；缺点通常是生成速度较慢。

**GPU 全卸载**

- 权重主体、对应层计算以及默认开启的 KV offload 进入 GPU；
- 通常速度更高，但显存必须同时容纳权重、KV、计算缓冲和余量；
- 新版优先用 `gpu-layers = all`，不要假设模型的“层数”就是完整卸载数。

**CPU+GPU 混合卸载**

- 一部分层留在 CPU，另一部分层放入 GPU；
- 它解决“模型权重不能整体装进显存，但系统 RAM 足够”的场景；
- 更多层进入 GPU 通常能提升速度，但 PCIe 传输、CPU 速度和模型结构会影响收益；“卸载 50% 的层”不等于“获得 50% 的 GPU 性能”。

### 2.5 `gpu-layers` 的准确语义

当前官方帮助将 `-ngl/--gpu-layers/--n-gpu-layers` 定义为“最多存入 VRAM 的层数”，可以是整数、`auto` 或 `all`，默认 `auto`。[llama-server 参数表](https://github.com/ggml-org/llama.cpp/blob/ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31/tools/server/README.md#common-params)

锁定版本源码还揭示了数值语义：

- 输入层因收益很小始终留在 CPU；
- 从靠后的重复层开始分配到 GPU；
- 输出层参与分配；
- `n_gpu_layers < 0` 表示全卸载；CLI 层把 `auto` 与 `all` 映射成不同内部状态。

见 [`llama-model.cpp` 的层分配](https://github.com/ggml-org/llama.cpp/blob/ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31/src/llama-model.cpp#L1253-L1340) 和 [`common.h` 的参数状态](https://github.com/ggml-org/llama.cpp/blob/ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31/common/common.h#L469-L483)。

因此，假设模型元数据显示 `block_count = 36`：

```text
0        纯 CPU 路线
1..36    部分卸载；并非简单的 1/36..36/36 GPU 百分比
37       在本次锁定实现中可覆盖 36 个重复层 + 输出层
all      跨模型表达“尽可能全卸载”的首选写法
auto     让支持该能力的新版 llama.cpp 按设备内存自动适配
```

旧版 llama.cpp 的计数和默认值可能不同，所以 LLMGarage 应在运行时检查 `llama-server --help` 或版本能力，不能只靠 P1 研究时的规则永久硬编码。

### 2.6 最新版 `auto` 的意义与边界

锁定版本中：

- `n_gpu_layers = -1` 是 `auto`，`<= -2` 是 `all`；
- 自动适配默认开启；
- 默认每设备目标余量是 1024 MiB；
- 必要时允许把上下文降到最低 4096。

对应源码见 [`common.h`](https://github.com/ggml-org/llama.cpp/blob/ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31/common/common.h#L469-L483)，CLI 还暴露 `--fit`、`--fit-target` 和 `--fit-ctx`。[llama-server 参数表](https://github.com/ggml-org/llama.cpp/blob/ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31/tools/server/README.md#common-params)

产品策略：

- 检测到支持 `auto` 的二进制：运行建议优先 `auto`，界面仍展示 LLMGarage 的预估层数和预算分解；
- 不支持 `auto`：使用下面的保守数值算法；
- 用户明确选择“全卸载”：支持时写 `all`，旧版退化为明显大于 `block_count + 1` 的数值；
- 自动适配也不是绝对保证，其他进程会在检测后抢占显存，特殊后端/模型结构也可能改变开销。

## 3. 数值卸载层数的保守选择原则

### 3.1 先算可用于权重的显存

P1 建议公式：

```text
系统余量 = max(1024 MiB, 总显存 × 15%)
计算余量 = max(512 MiB, 总显存 × 5%)
KV 估算 = 按模型结构、ctx=4096、F16 K/V、单并发计算

权重显存预算
= 当前 freeMiB - 系统余量 - 计算余量 - KV 估算
```

解释：

- 1024 MiB 与当前上游 `--fit-target` 默认一致；
- 15% 和额外计算余量是 LLMGarage 为桌面 Windows 用户增加的保守规则，不是 llama.cpp 官方保证；
- 应使用 `freeMiB`，不能只用 `totalMiB`；
- 预算小于等于 0 时走 CPU；
- 用户改变上下文、KV 类型、batch、并发或其他 GPU 占用后必须重新估算。

### 3.2 再估算层数

没有读取 GGUF 每个张量精确尺寸时，可采用“故意偏保守”的近似：

```text
保守每层权重 ≈ GGUF 文件 MiB / block_count
估算可卸载重复层 = floor(权重显存预算 / 保守每层权重)
```

因为 GGUF 文件还含 embedding、output 和元数据，用整个文件除以重复层数通常会高估每个重复层，从而少推荐几层，符合 P1 的“先稳定启动”原则。但这个近似对 MoE、不同层宽、混合量化和特殊结构误差可能很大。

数值输出建议：

```text
estimatedGpuLayers = clamp(估算可卸载重复层, 0, block_count)
```

若完整预算能够覆盖：

```text
GGUF 文件 + KV 估算 + 计算余量 + 系统余量 <= freeMiB
```

则：

- 新版建议 `all`；
- 兼容数值建议 `block_count + 1`；
- UI 展示“预计全卸载”，但仍标注“启动日志为准”。

### 3.3 启动后的校准闭环

P1 只能做静态估算。后续阶段应读取 llama.cpp 启动日志中的实际值：

- CPU/GPU model buffer；
- KV buffer；
- compute buffer；
- `offloaded X/Y layers`；
- OOM 或分配失败。

若失败，自动退档顺序应是：

1. 降低 `gpu-layers`；
2. 把上下文降到 4096；
3. 降低 batch/ubatch；
4. 改为 CPU 路线；
5. 明确告诉用户调整了什么。

不要静默反复重试，也不要把 Windows 共享显存或页面文件当作与独立显存/物理 RAM 等价的安全容量。

## 4. 第一批 8 个模型

统一选择 Q4_K_M，便于解释和建立一致规则。文件大小取 2026-07-31 官方仓库实际文件字节数，表中 GB 为十进制近似。模型层数和上下文来自各官方模型卡。

| 推荐 ID | 模型与官方 GGUF | 参数量 | 重复层 | 原生上下文 | Q4_K_M 文件 | F16 KV @ 4K（约） | 定位 |
|---|---|---:|---:|---:|---:|---:|---|
| `qwen25-05b-q4` | [HF](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF) · [魔搭](https://modelscope.cn/models/Qwen/Qwen2.5-0.5B-Instruct-GGUF) | 0.49B | 24 | 32,768 | 0.491 GB | 48 MiB | 极低配/验证链路，不作为能力优先选择 |
| `qwen25-15b-q4` | [HF](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF) · [魔搭](https://modelscope.cn/models/Qwen/Qwen2.5-1.5B-Instruct-GGUF) | 1.54B | 28 | 32,768 | 1.117 GB | 112 MiB | CPU 与低显存安全首推 |
| `qwen25-3b-q4` | [HF](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF) · [魔搭](https://modelscope.cn/models/Qwen/Qwen2.5-3B-Instruct-GGUF) | 3.09B | 36 | 32,768 | 2.105 GB | 144 MiB | 低配机器的能力/速度折中 |
| `qwen3-4b-q4` | [HF](https://huggingface.co/Qwen/Qwen3-4B-GGUF) · [魔搭](https://modelscope.cn/models/Qwen/Qwen3-4B-GGUF) | 4.0B | 36 | 32,768 | 2.497 GB | 576 MiB | 4–6 GB 显存主力候选 |
| `qwen25-7b-q4` | [HF](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF) · [魔搭](https://modelscope.cn/models/Qwen/Qwen2.5-7B-Instruct-GGUF) | 7.61B | 28 | 32,768 | 4.683 GB（两分片） | 224 MiB | 8 GB 档的成熟稳妥选择 |
| `qwen3-8b-q4` | [HF](https://huggingface.co/Qwen/Qwen3-8B-GGUF) · [魔搭](https://modelscope.cn/models/Qwen/Qwen3-8B-GGUF) | 8.2B | 36 | 32,768 | 5.028 GB | 576 MiB | 8–12 GB 档的能力首选 |
| `qwen3-14b-q4` | [HF](https://huggingface.co/Qwen/Qwen3-14B-GGUF) · [魔搭](https://modelscope.cn/models/Qwen/Qwen3-14B-GGUF) | 14.8B | 40 | 32,768 | 9.002 GB | 640 MiB | 12 GB 尝试、16 GB+ 舒适 |
| `qwen3-30b-a3b-q4` | [HF](https://huggingface.co/Qwen/Qwen3-30B-A3B-GGUF) · [魔搭](https://modelscope.cn/models/Qwen/Qwen3-30B-A3B-GGUF) | 30.5B 总计 / 3.3B 激活 | 48 | 32,768 | 18.600 GB | 384 MiB | 16 GB+ 显存配合充足 RAM 的吃力档 |

模型卡依据：

- Qwen2.5 0.5B：0.49B、24 层、GQA 14/2、32K。[官方模型卡](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF)
- Qwen2.5 1.5B：1.54B、28 层、GQA 12/2、32K。[官方模型卡](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF)
- Qwen2.5 3B：3.09B、36 层、GQA 16/2、32K。[官方模型卡](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF)
- Qwen2.5 7B：7.61B、28 层、GQA 28/4、32K。[官方模型卡](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF)
- Qwen3 4B：4.0B、36 层、GQA 32/8、原生 32K。[官方模型卡](https://huggingface.co/Qwen/Qwen3-4B-GGUF)
- Qwen3 8B：8.2B、36 层、GQA 32/8、原生 32K。[官方模型卡](https://huggingface.co/Qwen/Qwen3-8B-GGUF)
- Qwen3 14B：14.8B、40 层、GQA 40/8、原生 32K。[官方模型卡](https://huggingface.co/Qwen/Qwen3-14B-GGUF)
- Qwen3 30B-A3B：30.5B 总参数、每 token 激活 3.3B、48 层、GQA 32/4、原生 32K。[官方模型卡](https://huggingface.co/Qwen/Qwen3-30B-A3B-GGUF)

文件字节数可由 Hugging Face 官方模型仓库的文件树复核：

- [0.5B Q4_K_M 文件](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/blob/main/qwen2.5-0.5b-instruct-q4_k_m.gguf)
- [1.5B Q4_K_M 文件](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/blob/main/qwen2.5-1.5b-instruct-q4_k_m.gguf)
- [3B Q4_K_M 文件](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/blob/main/qwen2.5-3b-instruct-q4_k_m.gguf)
- [4B Q4_K_M 文件](https://huggingface.co/Qwen/Qwen3-4B-GGUF/blob/main/Qwen3-4B-Q4_K_M.gguf)
- [7B Q4_K_M 分片 1](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/blob/main/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf) 与 [分片 2](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/blob/main/qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf)
- [8B Q4_K_M 文件](https://huggingface.co/Qwen/Qwen3-8B-GGUF/blob/main/Qwen3-8B-Q4_K_M.gguf)
- [14B Q4_K_M 文件](https://huggingface.co/Qwen/Qwen3-14B-GGUF/blob/main/Qwen3-14B-Q4_K_M.gguf)
- [30B-A3B Q4_K_M 仓库与 18.6 GB 文件信息](https://huggingface.co/Qwen/Qwen3-30B-A3B-GGUF)

许可证注意：

- Qwen2.5-3B 官方 GGUF 页面标示 `qwen-research` / Qwen Research License，界面应链接并提示用户阅读；
- 表中其他仓库页面在调研时标示 Apache-2.0；
- 产品不要把“可下载”表述成“可用于任何用途”，许可证状态应作为模型元数据展示。

## 5. 推荐矩阵

推荐分档先看总显存，再用当前空闲显存公式做降档：

| NVIDIA 总显存 | 安全首推 | 可选 | 说明 |
|---:|---|---|---|
| 未知或 `< 4 GB` | Qwen2.5 1.5B Q4，CPU/少量混合 | Qwen2.5 3B Q4 | 0.5B 只用于极低配和验证链路 |
| `4–6 GB` | Qwen2.5 3B 或 Qwen3 4B Q4 | Qwen2.5 7B 部分卸载 | 先 4K 上下文，不把 7B 写成“肯定全卸载” |
| `> 6–10 GB` | Qwen2.5 7B Q4 | Qwen3 8B Q4 | 8 GB 档还要看桌面占用和当前 freeMiB |
| `> 10–16 GB` | Qwen3 8B Q4 | Qwen3 14B Q4 | 12 GB 的 14B 属于尝试项，不是首推 |
| `> 16 GB` | Qwen3 14B Q4 | Qwen3 30B-A3B Q4 混合卸载 | 30B-A3B 是吃力档，需要充足 RAM 与更慢速度预期 |

CPU 路线还要做 RAM 门槛：

“吃力可跑”不是“安全首推”的同义词：

- NVIDIA 路线中，比安全首推更大的模型只有在权重可全卸载，或 RAM 足够且能做部分 GPU 卸载时，才标为吃力档；
- CPU 路线中，大于安全首推但仍能覆盖权重、KV 与系统余量的模型标为吃力档，明确提示纯 CPU 会更慢；
- 当前 RAM/VRAM 安全预算不足的模型仍标为“不推荐”，不能为了扩充清单把不可行模型包装成可运行。

混合卸载时，主机 RAM 判断不能继续要求容纳整份 GGUF。LLMGarage 按未卸载层的权重比例估算主机权重，并额外保留 `max(0.5 GiB, 权重 × 5%)` 给输入、输出与其他非重复层张量；这仍是保守近似，最终以 llama.cpp 启动日志和实测峰值为准。

```text
主机安全余量 = max(2048 MiB, 总 RAM × 20%)
可用于模型的 RAM = 当前 available RAM - 主机安全余量
```

保守判断可要求：

```text
可用于模型的 RAM
>= GGUF 文件 + KV 估算 + 1024 MiB CPU/应用余量
```

即使采用 GPU 全卸载，也不要完全忽略 RAM；加载、映射、运行时和应用仍需主机内存。

## 6. 推荐卡片必须展示的“为什么”

每张推荐卡应至少输出：

```text
模型：Qwen3-8B Q4_K_M
结论：安全 / 舒适 / 尝试 / 不推荐
当前依据：GPU 总显存、当前空闲显存、可用 RAM
权重：官方 GGUF 约 5.03 GB
KV：4K、F16、单并发约 576 MiB
余量：系统余量 + 计算余量
卸载：auto（兼容估算 0..37 层）
上下文：首跑 4096；模型原生支持 32768
一句话理由：为什么它比上下一个型号更稳
风险：检测后显存可能变化；最终以启动日志为准
规则版本：p1-2026-07-31
```

状态定义：

- **安全**：权重、KV、计算余量和系统余量均覆盖；
- **舒适**：覆盖后仍有明显空闲，可考虑 8K 上下文；
- **尝试**：需要部分卸载、降低上下文或关闭其他 GPU 应用；
- **不推荐**：当前 RAM/VRAM 预算不足，不进入默认前三项。

“安全”仍是概率性工程判断，不是成功保证。

## 7. API 与实现建议

建议把原始事实和推荐结论分开：

```json
{
  "hardware": {
    "observedAt": "ISO-8601",
    "os": {},
    "cpu": {
      "name": "...",
      "physicalCores": 8,
      "logicalThreads": 16
    },
    "memory": {
      "totalMiB": 32768,
      "availableMiB": 21800
    },
    "gpus": [
      {
        "vendor": "NVIDIA",
        "name": "...",
        "totalMiB": 12288,
        "freeMiB": 10800,
        "driverVersion": "...",
        "source": "nvidia-smi"
      }
    ],
    "warnings": []
  },
  "recommendation": {
    "rulesVersion": "p1-2026-07-31",
    "runtimePath": "nvidia-or-cpu",
    "models": []
  }
}
```

工程边界：

- 检测函数负责事实与置信度，不负责选模型；
- 推荐函数接收硬件快照和模型目录，保持纯函数，便于做硬件矩阵测试；
- 模型目录保存官方字段、许可证、文件大小、层数和 KV 结构字段；
- 所有估算值明确单位，内部统一 MiB；
- 不把检测失败伪装成“0 GB GPU”；
- P1 只展示，不自动下载、不自动写 preset、不自动启动服务。

## 8. 必测场景

1. Windows + 单 NVIDIA，CSV 正常；
2. 多 NVIDIA，分别保留总/空闲显存；
3. `nvidia-smi` 不存在；
4. `nvidia-smi` 超时、非零退出、`N/A`、本地化/额外空格；
5. 只有 AMD/Intel，进入 CPU 路线；
6. 8 GB 总显存但当前只空闲 3 GB，推荐应降档；
7. 总 RAM 足够但 available RAM 不足，不能给“安全”；
8. 4K 改成 8K 后，KV 估算近似翻倍并可能降档；
9. `auto/all` 可用与旧版只接收整数两种运行时；
10. `block_count = 36` 时完整数值卸载按 37 处理；
11. 模型目录恰好保持 5–8 个；
12. 每张推荐都有预算分解、理由、风险和规则版本。

## 9. 一手资料索引

- [llama.cpp README：CPU、CUDA 与 CPU+GPU hybrid inference](https://github.com/ggml-org/llama.cpp/blob/ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31/README.md)
- [llama-server 参数表](https://github.com/ggml-org/llama.cpp/blob/ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31/tools/server/README.md)
- [llama.cpp 当前 offload 默认值与 1 GiB fit target](https://github.com/ggml-org/llama.cpp/blob/ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31/common/common.h#L469-L483)
- [llama.cpp 当前输入层/重复层/输出层分配逻辑](https://github.com/ggml-org/llama.cpp/blob/ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31/src/llama-model.cpp#L1253-L1340)
- [llama.cpp KV 张量分配](https://github.com/ggml-org/llama.cpp/blob/ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31/src/llama-kv-cache.cpp#L204-L248)
- [llama.cpp 量化工具说明](https://github.com/ggml-org/llama.cpp/blob/ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31/tools/quantize/README.md)
- [NVIDIA System Management Interface 文档](https://docs.nvidia.com/deploy/nvidia-smi/index.html)
- [Qwen 官方 Hugging Face 组织](https://huggingface.co/Qwen)
- [Qwen 官方 ModelScope 组织](https://modelscope.cn/organization/Qwen)
