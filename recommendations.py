from __future__ import annotations

import math
from typing import Any


MODEL_CATALOG = (
    {
        "id": "qwen2.5-0.5b-instruct-q4-k-m",
        "name": "Qwen2.5 0.5B Instruct",
        "parametersBillions": 0.49,
        "quantization": "Q4_K_M",
        "officialFileSizeGB": 0.491,
        "estimatedFileGiB": 0.457,
        "blockCount": 24,
        "nativeContext": 32768,
        "kvCacheGiBAt4096": 0.047,
        "license": "Apache-2.0",
        "officialUrl": "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        "modelScopeUrl": "https://modelscope.cn/models/Qwen/Qwen2.5-0.5B-Instruct-GGUF",
    },
    {
        "id": "qwen2.5-1.5b-instruct-q4-k-m",
        "name": "Qwen2.5 1.5B Instruct",
        "parametersBillions": 1.54,
        "quantization": "Q4_K_M",
        "officialFileSizeGB": 1.117,
        "estimatedFileGiB": 1.04,
        "blockCount": 28,
        "nativeContext": 32768,
        "kvCacheGiBAt4096": 0.11,
        "license": "Apache-2.0",
        "officialUrl": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF",
        "modelScopeUrl": "https://modelscope.cn/models/Qwen/Qwen2.5-1.5B-Instruct-GGUF",
    },
    {
        "id": "qwen2.5-3b-instruct-q4-k-m",
        "name": "Qwen2.5 3B Instruct",
        "parametersBillions": 3.09,
        "quantization": "Q4_K_M",
        "officialFileSizeGB": 2.105,
        "estimatedFileGiB": 1.96,
        "blockCount": 36,
        "nativeContext": 32768,
        "kvCacheGiBAt4096": 0.141,
        "license": "Qwen Research License",
        "officialUrl": "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF",
        "modelScopeUrl": "https://modelscope.cn/models/Qwen/Qwen2.5-3B-Instruct-GGUF",
    },
    {
        "id": "qwen3-4b-q4-k-m",
        "name": "Qwen3 4B",
        "parametersBillions": 4.0,
        "quantization": "Q4_K_M",
        "officialFileSizeGB": 2.497,
        "estimatedFileGiB": 2.325,
        "blockCount": 36,
        "nativeContext": 32768,
        "kvCacheGiBAt4096": 0.563,
        "license": "Apache-2.0",
        "officialUrl": "https://huggingface.co/Qwen/Qwen3-4B-GGUF",
        "modelScopeUrl": "https://modelscope.cn/models/Qwen/Qwen3-4B-GGUF",
    },
    {
        "id": "qwen2.5-7b-instruct-q4-k-m",
        "name": "Qwen2.5 7B Instruct",
        "parametersBillions": 7.61,
        "quantization": "Q4_K_M",
        "officialFileSizeGB": 4.683,
        "estimatedFileGiB": 4.361,
        "blockCount": 28,
        "nativeContext": 32768,
        "kvCacheGiBAt4096": 0.219,
        "license": "Apache-2.0",
        "officialUrl": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF",
        "modelScopeUrl": "https://modelscope.cn/models/Qwen/Qwen2.5-7B-Instruct-GGUF",
        "sharded": True,
    },
    {
        "id": "qwen3-8b-q4-k-m",
        "name": "Qwen3 8B",
        "parametersBillions": 8.2,
        "quantization": "Q4_K_M",
        "officialFileSizeGB": 5.028,
        "estimatedFileGiB": 4.683,
        "blockCount": 36,
        "nativeContext": 32768,
        "kvCacheGiBAt4096": 0.563,
        "license": "Apache-2.0",
        "officialUrl": "https://huggingface.co/Qwen/Qwen3-8B-GGUF",
        "modelScopeUrl": "https://modelscope.cn/models/Qwen/Qwen3-8B-GGUF",
    },
    {
        "id": "qwen3-14b-q4-k-m",
        "name": "Qwen3 14B",
        "parametersBillions": 14.8,
        "quantization": "Q4_K_M",
        "officialFileSizeGB": 9.002,
        "estimatedFileGiB": 8.384,
        "blockCount": 40,
        "nativeContext": 32768,
        "kvCacheGiBAt4096": 0.625,
        "license": "Apache-2.0",
        "officialUrl": "https://huggingface.co/Qwen/Qwen3-14B-GGUF",
        "modelScopeUrl": "https://modelscope.cn/models/Qwen/Qwen3-14B-GGUF",
    },
    {
        "id": "qwen3-30b-a3b-q4-k-m",
        "name": "Qwen3 30B-A3B",
        "parametersBillions": 30.5,
        "activeParametersBillions": 3.3,
        "quantization": "Q4_K_M",
        "officialFileSizeGB": 18.6,
        "estimatedFileGiB": 17.323,
        "blockCount": 48,
        "nativeContext": 32768,
        "kvCacheGiBAt4096": 0.375,
        "license": "Apache-2.0",
        "officialUrl": "https://huggingface.co/Qwen/Qwen3-30B-A3B-GGUF",
        "modelScopeUrl": "https://modelscope.cn/models/Qwen/Qwen3-30B-A3B-GGUF",
    },
)

FIT_LABELS = {
    "comfortable": "舒适",
    "safe": "安全",
    "try": "吃力可跑",
    "not-recommended": "不推荐",
}

RECOMMENDATION_RULES = (
    {
        "condition": "没有可用 NVIDIA GPU，或 nvidia-smi 探测失败",
        "result": "走保守 CPU 路线，优先 0.5B–3B Q4",
    },
    {"condition": "VRAM < 4 GiB", "result": "1.5B Q4 为安全默认，3B 作为尝试"},
    {"condition": "VRAM 4–6 GiB", "result": "3B/4B Q4 为安全候选"},
    {"condition": "VRAM > 6–10 GiB", "result": "7B Q4 为安全默认，8B 作为能力选项"},
    {"condition": "VRAM > 10–约 16 GiB", "result": "8B Q4 为安全默认，14B 作为尝试"},
    {"condition": "约 16 GiB 及以上", "result": "14B Q4 为安全默认"},
)

LLAMA_CPP_SERVER_SOURCE = {
    "label": "llama.cpp server 官方参数说明",
    "url": "https://github.com/ggml-org/llama.cpp/blob/ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31/tools/server/README.md",
}
LLAMA_CPP_BUILD_SOURCE = {
    "label": "llama.cpp 官方构建说明",
    "url": "https://github.com/ggml-org/llama.cpp/blob/ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31/docs/build.md",
}
GGUF_SOURCE = {
    "label": "GGUF 官方格式规范",
    "url": "https://github.com/ggml-org/ggml/blob/master/docs/gguf.md",
}
QUANTIZATION_SOURCE = {
    "label": "llama.cpp 官方量化说明",
    "url": "https://github.com/ggml-org/llama.cpp/blob/ea63b4d32ea1b66bdbe369be7f9443f6c00f8b31/tools/quantize/README.md",
}

LEARNING_TOPICS = (
    {
        "id": "parameters",
        "title": "参数量：模型有多大，不等于它一定有多聪明",
        "summary": "0.5B、7B、14B 表示大约有多少十亿个可训练参数；参数越多，权重通常越大，推理成本也越高。",
        "details": (
            "参数是模型学到的数值。参数量可以帮助估算权重规模，但不能单独代表回答质量："
            "训练数据、架构、指令微调和任务类型同样重要。比较本地模型时，要把参数量与量化格式、"
            "上下文长度和机器内存一起看。"
        ),
        "steps": [
            "先用参数量确定大致档位，例如 1.5B、3B、7B、14B。",
            "再看实际 GGUF 文件大小；它比“B 数”更接近需要装入内存的权重体积。",
            "最后用自己的任务测试质量和速度，不用参数量替代实际体验。",
        ],
        "caution": "同样是 7B，不同架构、量化和训练方式可能有明显不同的质量、速度与内存占用。",
        "sources": [GGUF_SOURCE],
    },
    {
        "id": "quantization",
        "title": "量化：用更少位数保存权重",
        "summary": "Q4_K_M 是常见的四位量化平衡档，通常比 F16 小很多，适合作为本地入门默认值。",
        "details": (
            "量化把高精度权重压到更少的位数，降低下载体积和运行内存。名称里的 Q4 表示主要权重约为"
            "四位；K 与 M 代表 llama.cpp 的具体分组和混合量化方案。位数更低通常更省内存，"
            "但可能损失更多质量；实际速度还取决于 CPU/GPU 后端是否有高效内核。"
        ),
        "steps": [
            "首次运行优先选择 Q4_K_M。",
            "内存非常紧张时再比较更低位量化。",
            "质量更重要且内存充足时，可比较 Q5、Q6 或更高精度。",
        ],
        "caution": "量化名称不是跨工具完全等价的质量等级；应在同一模型、同一任务上比较。",
        "sources": [QUANTIZATION_SOURCE],
    },
    {
        "id": "gguf",
        "title": "GGUF：llama.cpp 读取的模型容器",
        "summary": "一个 GGUF 文件通常同时保存张量、模型结构元数据和分词器信息。",
        "details": (
            "GGUF 是面向快速加载与扩展元数据的二进制格式。LLMGarage 推荐的是具体 GGUF 量化文件，"
            "不是原始训练检查点。文件扩展名正确并不保证当前 llama.cpp 一定支持其中的架构或新字段，"
            "因此遇到加载错误时仍要核对模型卡与运行时版本。"
        ),
        "steps": [
            "确认仓库和发布者可信。",
            "确认文件名中的量化档位。",
            "核对模型卡要求的 llama.cpp 版本和聊天模板。",
        ],
        "caution": "不要仅凭 `.gguf` 后缀判断兼容性，也不要把分片 GGUF 当作单个完整文件随意移动。",
        "sources": [GGUF_SOURCE],
    },
    {
        "id": "weight-memory",
        "title": "权重内存：文件能放下，不代表运行一定能放下",
        "summary": "GGUF 文件大小是权重占用的第一近似值，运行时还要给 KV cache、计算缓冲区和驱动留余量。",
        "details": (
            "CPU 路线主要由系统 RAM 承担权重；GPU 全卸载时主要由 VRAM 承担权重；混合卸载则两边都占。"
            "操作系统文件映射会让“进程工作集”“已提交内存”和文件大小看起来不同。推荐器按文件估算值"
            "再预留空间，目标是提高启动成功率，而不是把显存使用率顶到 100%。"
        ),
        "steps": [
            "先记录 GGUF 文件体积。",
            "加上目标上下文的 KV cache 估算。",
            "再预留运行时、图形桌面和临时计算空间。",
        ],
        "caution": "显存总量与当前空闲显存都要看；浏览器、游戏或桌面应用会减少可用预算。",
        "sources": [LLAMA_CPP_SERVER_SOURCE],
    },
    {
        "id": "kv-cache",
        "title": "KV cache：上下文越长，记忆工作区越大",
        "summary": "KV cache 保存已处理 token 的注意力键和值，通常随上下文长度和并行序列数增长。",
        "details": (
            "权重大小基本固定，而 KV cache 会随使用方式变化。它受层数、KV 头数量、头维度、"
            "K/V 数据类型、上下文长度和并发槽位影响。把 context 从 4K 提高到 8K，"
            "在其他条件相同时，KV cache 通常近似翻倍；具体分配仍取决于模型和 llama.cpp 版本。"
        ),
        "steps": [
            "先从 4096 context 获得稳定基线。",
            "确实需要长文时再逐级提高。",
            "每次提高后观察启动日志、VRAM/RAM 与吞吐。",
        ],
        "caution": "推荐卡上的 KV 数字是按模型结构和常见缓存精度计算的估算，不含全部运行时缓冲。",
        "sources": [LLAMA_CPP_SERVER_SOURCE],
    },
    {
        "id": "cpu-inference",
        "title": "CPU 推理：最保守、兼容面最宽的路线",
        "summary": "GPU 后端不可用时，llama.cpp 可以把模型权重留在系统内存并由 CPU 执行主要计算。",
        "details": (
            "CPU 路线更依赖 RAM 容量与内存带宽，通常比现代独立 GPU 慢，但无需确认 CUDA 后端。"
            "`--threads` 控制生成阶段常用的 CPU 线程数；起点可用物理核心数，再根据温度、"
            "响应速度和系统可用性实测。逻辑线程不是越多越快。当前版本若要明确禁止设备卸载，"
            "除了 `--gpu-layers 0`，还可使用 `--device none`。"
        ),
        "steps": [
            "设置 `--gpu-layers 0` 建立可启动基线。",
            "线程数先取物理核心数；无法检测时取逻辑线程的一半。",
            "选择较小的 Q4 模型并从 4K context 开始。",
            "用相同 Prompt 比较不同线程数的速度与交互流畅度。",
        ],
        "caution": "CPU 路线仍可能因为 RAM 不足失败；小模型能启动也不代表大模型只会“更慢”。",
        "sources": [LLAMA_CPP_SERVER_SOURCE],
    },
    {
        "id": "gpu-offload",
        "title": "GPU 卸载：把模型层放进显存计算",
        "summary": "llama.cpp 的 `--gpu-layers`（`-ngl`）控制尝试卸载到 GPU 的最大层数。",
        "details": (
            "使用 NVIDIA GPU 前，llama.cpp 必须是带 CUDA 后端的构建。卸载更多层通常能减少 CPU "
            "承担的矩阵计算并提高速度，但也会增加显存占用。所谓“全卸载”主要指可卸载的模型层"
            "进入 GPU，并不表示进程、采样、输入输出和所有缓冲都离开 CPU/RAM。锁定研究版本中，"
            "`--gpu-layers` 支持整数、`auto` 和 `all`，默认 `auto`；旧版二进制可能只接受整数，"
            "所以后续生成 preset 时必须先检查运行时能力。"
        ),
        "steps": [
            "确认 `nvidia-smi` 可见 GPU，并使用 CUDA 版 llama.cpp。",
            "用较小层数或推荐值启动。",
            "从日志确认实际卸载层数和后端。",
            "在保持显存余量的前提下逐步提高。",
        ],
        "caution": "只有 NVIDIA 驱动并不够；CPU-only 的 llama.cpp 构建不会因为设置 `-ngl` 自动获得 CUDA。",
        "sources": [LLAMA_CPP_BUILD_SOURCE, LLAMA_CPP_SERVER_SOURCE],
    },
    {
        "id": "hybrid-offload",
        "title": "CPU + GPU 混合卸载：显存不够时分工",
        "summary": "一部分层放入 VRAM，其余层留在 RAM，由 GPU 与 CPU 共同完成一次前向计算。",
        "details": (
            "混合卸载让大于显存的模型仍有机会运行。增加 GPU 层数通常会加速，但剩余 CPU 层、"
            "内存带宽和设备间传输仍可能成为瓶颈。因此 14B 混合卸载不一定比完整装入 GPU 的 7B "
            "更快或更适合日常使用，推荐器会把后者作为安全默认。"
        ),
        "steps": [
            "先确认模型能以 CPU 或较少 GPU 层启动。",
            "保留 KV cache 和运行时显存余量。",
            "每次增加 2–4 层并记录 tokens/s。",
            "出现显存不足时退回最近一次稳定值。",
        ],
        "caution": "层数相同不代表不同模型占用相同；每层大小由模型架构决定。",
        "sources": [LLAMA_CPP_SERVER_SOURCE],
    },
    {
        "id": "gpu-layer-selection",
        "title": "GPU 层数怎么选：预算、估算、启动日志、实测",
        "summary": "先给显存划出安全预算，再按模型每层权重的近似体积分配 `--gpu-layers`。",
        "details": (
            "LLMGarage 从当前空闲显存中扣除 max(1 GiB, 总显存×15%) 的系统余量、"
            "max(0.5 GiB, 总显存×5%) 的计算余量，以及 4K/F16/单并发的 KV cache 估算。"
            "剩余预算除以“GGUF 文件体积 ÷ block_count”的保守单层估算，再向下取整。"
            "`--gpu-layers` 数值计数不是 GPU 百分比：锁定版本从靠后的重复层开始卸载，输入层留在 CPU，"
            "输出层也参与计数；N 个 block 的完整兼容数值通常是 N + 1，新版优先用 `all`。"
        ),
        "steps": [
            "读取总 VRAM 与当前空闲 VRAM，取保守可用预算。",
            "扣除系统余量、计算余量与目标 context 的 KV cache。",
            "用完整 GGUF 体积除以 block 数，故意偏保守地估算每个重复层。",
            "向下取整得到起始层数，绝不超过模型 block 数。",
            "若完整预算覆盖权重，则新版用 all，旧版兼容值用 block_count + 1。",
            "启动后以 llama.cpp 日志和实际显存为准，每次调整 2–4 层。",
        ],
        "caution": "这是为了提高首次启动成功率的起始估算，不是精确值，也不是性能最优值。",
        "sources": [LLAMA_CPP_SERVER_SOURCE],
    },
    {
        "id": "context-and-batch",
        "title": "Context、Batch 与并发：三种不同的内存压力",
        "summary": "Context 主要拉高 KV cache；batch/ubatch 影响提示词处理的临时缓冲与吞吐；并发会复制或切分运行上下文。",
        "details": (
            "`--ctx-size` 决定可用上下文窗口，`--batch-size` 与 `--ubatch-size` 影响提示词批处理方式，"
            "`--parallel` 增加服务并发槽位。它们不是同一个旋钮：长 context 适合长文，"
            "大 batch 可能提高 prompt 处理吞吐，并发则服务更多请求，但三者都可能增加内存压力。"
        ),
        "steps": [
            "先固定模型与 4K context。",
            "单用户先保持 parallel=1。",
            "稳定后单独调整一个参数并记录内存与速度。",
            "发生 OOM 时优先回退最近改动，而不是同时缩小所有参数。",
        ],
        "caution": "不同 llama.cpp 版本和后端的缓冲策略会变化，推荐器不会把这些估算伪装成精确承诺。",
        "sources": [LLAMA_CPP_SERVER_SOURCE],
    },
)


def _safe_default_id(path: str, vram_gib: float, ram_gib: float) -> str:
    if path != "nvidia":
        return (
            "qwen2.5-1.5b-instruct-q4-k-m"
            if ram_gib >= 8
            else "qwen2.5-0.5b-instruct-q4-k-m"
        )
    if vram_gib < 4:
        return "qwen2.5-1.5b-instruct-q4-k-m"
    if vram_gib < 6:
        return (
            "qwen3-4b-q4-k-m"
            if vram_gib >= 5
            else "qwen2.5-3b-instruct-q4-k-m"
        )
    if vram_gib <= 10:
        return "qwen2.5-7b-instruct-q4-k-m"
    if vram_gib < 15.5:
        return "qwen3-8b-q4-k-m"
    return "qwen3-14b-q4-k-m"


def _kv_cache_gib(model: dict[str, Any], context_size: int) -> float:
    return round(model["kvCacheGiBAt4096"] * context_size / 4096, 3)


def _full_offload_fits(
    model: dict[str, Any],
    total_vram: float,
    free_vram: float,
    context_size: int,
) -> bool:
    return (
        model["estimatedFileGiB"]
        + _kv_cache_gib(model, context_size)
        + max(1.0, total_vram * 0.15)
        + max(0.5, total_vram * 0.05)
        <= free_vram
    )


def _offload_layers(
    model: dict[str, Any],
    total_vram: float,
    free_vram: float,
    context_size: int,
) -> int:
    system_reserve = max(1.0, total_vram * 0.15)
    compute_reserve = max(0.5, total_vram * 0.05)
    weight_gib = model["estimatedFileGiB"]
    block_count = model["blockCount"]
    per_layer_gib = weight_gib / block_count
    layer_budget = (
        free_vram
        - system_reserve
        - compute_reserve
        - _kv_cache_gib(model, context_size)
    )
    if layer_budget <= 0:
        return 0
    return min(block_count, max(0, math.floor(layer_budget / per_layer_gib)))


def _estimated_host_weight_gib(
    model: dict[str, Any],
    gpu_layers: int,
) -> float:
    weight_gib = model["estimatedFileGiB"]
    block_count = model["blockCount"]
    if gpu_layers <= 0:
        return weight_gib
    remaining_layer_fraction = max(0, block_count - gpu_layers) / block_count
    non_layer_reserve = max(0.5, weight_gib * 0.05)
    return round(
        min(weight_gib, weight_gib * remaining_layer_fraction + non_layer_reserve),
        3,
    )


def _offload_calculation(
    model: dict[str, Any],
    total_vram: float,
    free_vram: float,
    context_size: int,
    gpu_layers: int,
) -> dict[str, float]:
    weight_gib = model["estimatedFileGiB"]
    block_count = model["blockCount"]
    system_reserve = max(1.0, total_vram * 0.15)
    compute_reserve = max(0.5, total_vram * 0.05)
    per_layer_gib = weight_gib / block_count
    kv_cache_gib = _kv_cache_gib(model, context_size)
    usable_vram = max(
        0.0,
        free_vram - system_reserve - compute_reserve - kv_cache_gib,
    )
    return {
        "vramTotalGiB": total_vram,
        "vramFreeGiB": free_vram,
        "usableVramGiB": round(usable_vram, 2),
        "systemReserveGiB": round(system_reserve, 2),
        "computeReserveGiB": round(compute_reserve, 2),
        "runtimeReserveGiB": round(system_reserve + compute_reserve, 2),
        "estimatedKvCacheGiB": kv_cache_gib,
        "estimatedLayerGiB": round(per_layer_gib, 3),
        "estimatedHostWeightGiB": _estimated_host_weight_gib(model, gpu_layers),
    }


def _non_negative_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0:
        return None
    return number


def build_recommendation_report(
    hardware: dict[str, Any],
    *,
    context_size: int = 4096,
) -> dict[str, Any]:
    if isinstance(context_size, bool) or not isinstance(context_size, int) or context_size <= 0:
        raise ValueError("context_size must be a positive integer")
    path = hardware.get("recommendationPath", "cpu")
    memory = hardware.get("memory", {})
    ram_gib = _non_negative_number(memory.get("ramTotalGiB")) or 0.0
    available_ram_value = _non_negative_number(memory.get("ramAvailableGiB"))
    ram_available_known = available_ram_value is not None
    ram_available_gib = available_ram_value if available_ram_value is not None else 0.0
    host_ram_reserve = max(2.0, ram_gib * 0.2)
    model_ram_budget = max(0.0, ram_available_gib - host_ram_reserve - 1.0)
    host_runtime_fits = (
        ram_available_known
        and ram_available_gib >= host_ram_reserve + 1.0
    )
    nvidia_gpus = [
        gpu
        for gpu in hardware.get("gpus", [])
        if str(gpu.get("vendor", "")).lower() == "nvidia"
    ]
    primary_gpu = max(
        nvidia_gpus,
        key=lambda gpu: float(gpu.get("vramTotalGiB") or 0),
        default={},
    )
    total_vram = _non_negative_number(primary_gpu.get("vramTotalGiB")) or 0.0
    free_vram_value = _non_negative_number(primary_gpu.get("vramFreeGiB"))
    free_vram = free_vram_value if free_vram_value is not None else 0.0
    default_id = _safe_default_id(path, total_vram, ram_gib)
    has_safe_default = False
    if path == "nvidia":
        target_model = next(model for model in MODEL_CATALOG if model["id"] == default_id)
        fitting_models = [
            model
            for model in MODEL_CATALOG
            if model["parametersBillions"] <= target_model["parametersBillions"]
            and _full_offload_fits(model, total_vram, free_vram, context_size)
        ]
        if fitting_models:
            default_id = max(
                fitting_models,
                key=lambda model: model["parametersBillions"],
            )["id"]
            has_safe_default = host_runtime_fits
        else:
            default_id = "qwen2.5-0.5b-instruct-q4-k-m"
            smallest_model = MODEL_CATALOG[0]
            has_safe_default = (
                smallest_model["estimatedFileGiB"]
                + _kv_cache_gib(smallest_model, context_size)
                <= model_ram_budget
            )
    else:
        target_model = next(model for model in MODEL_CATALOG if model["id"] == default_id)
        fitting_models = [
            model
            for model in MODEL_CATALOG
            if model["parametersBillions"] <= target_model["parametersBillions"]
            and model["estimatedFileGiB"] + _kv_cache_gib(model, context_size)
            <= model_ram_budget
        ]
        if fitting_models:
            default_id = max(
                fitting_models,
                key=lambda model: model["parametersBillions"],
            )["id"]
            has_safe_default = True
        else:
            default_id = "qwen2.5-0.5b-instruct-q4-k-m"
    default_parameters = next(
        model["parametersBillions"]
        for model in MODEL_CATALOG
        if model["id"] == default_id
    )

    models = []
    for model in MODEL_CATALOG:
        kv_cache_gib = _kv_cache_gib(model, context_size)
        gpu_layers = (
            _offload_layers(model, total_vram, free_vram, context_size)
            if path == "nvidia"
            else 0
        )
        ram_needed = round(model["estimatedFileGiB"] * 1.15 + 2, 2)
        position = (
            "safe-default"
            if model["id"] == default_id and has_safe_default
            else "lowest-risk"
            if model["id"] == default_id
            else "alternative"
        )
        full_offload = path == "nvidia" and _full_offload_fits(
            model,
            total_vram,
            free_vram,
            context_size,
        )
        offload_mode = (
            "cpu"
            if path != "nvidia" or gpu_layers == 0
            else "full"
            if full_offload
            else "hybrid"
        )
        cpu_memory_fits = (
            model["estimatedFileGiB"] + kv_cache_gib
            <= model_ram_budget
        )
        estimated_host_weight_gib = _estimated_host_weight_gib(model, gpu_layers)
        hybrid_host_fits = estimated_host_weight_gib <= model_ram_budget
        if path != "nvidia":
            if cpu_memory_fits and model["parametersBillions"] > default_parameters:
                fit_status = "try"
                fit_reason = (
                    "当前可用 RAM 可以容纳，但模型大于安全首推；"
                    "纯 CPU 推理会更慢，建议缩短上下文并从单用户开始"
                )
            elif cpu_memory_fits:
                fit_status = "safe"
                fit_reason = "当前可用 RAM 覆盖权重、KV 与主机余量"
            else:
                fit_status = "not-recommended"
                fit_reason = "当前可用 RAM 扣除系统与应用余量后不足"
        elif offload_mode == "cpu":
            fit_status = "safe" if cpu_memory_fits else "not-recommended"
            fit_reason = (
                "当前空闲 VRAM 不足，改走 RAM 可覆盖的保守 CPU 路线"
                if cpu_memory_fits
                else "当前 RAM/VRAM 安全预算均不足"
            )
        elif not host_runtime_fits:
            fit_status = "not-recommended"
            fit_reason = "主机可用 RAM 未知或不足，不能给出安全结论"
        elif full_offload:
            if model["parametersBillions"] > default_parameters:
                fit_status = "try"
                fit_reason = "比安全首推更大的能力选项；即使预算覆盖，也建议先验证速度和余量"
            else:
                fit_status = "comfortable" if free_vram - (
                model["estimatedFileGiB"]
                + kv_cache_gib
                    + max(1.0, total_vram * 0.15)
                    + max(0.5, total_vram * 0.05)
                ) >= 1.0 else "safe"
                fit_reason = "当前空闲 VRAM 覆盖权重、KV 与两类显存余量"
        elif gpu_layers > 0 and hybrid_host_fits:
            fit_status = "try"
            fit_reason = (
                "需要 CPU+GPU 混合卸载；估算主机承担"
                f"约 {estimated_host_weight_gib:g} GiB 权重，并以启动日志校准"
            )
        else:
            fit_status = "not-recommended"
            fit_reason = "当前 RAM/VRAM 安全预算不足"
        calculation = _offload_calculation(
            model,
            total_vram,
            free_vram,
            context_size,
            gpu_layers,
        )
        if offload_mode == "cpu":
            offload_explanation = (
                "建议从 --gpu-layers 0 开始，让权重留在系统内存中；"
                "确认 GPU 后端可用后再逐步增加。"
            )
        elif offload_mode == "full":
            offload_explanation = (
                f"估算可容纳 {model['blockCount']} 个重复层和输出层；"
                "新版优先使用 --gpu-layers auto，明确全卸载时使用 all，"
                f"旧版兼容数值为 {model['blockCount'] + 1}。"
            )
        else:
            offload_explanation = (
                f"按可用显存预算估算先卸载 {gpu_layers}/{model['blockCount']} 层；"
                f"从 --gpu-layers {gpu_layers} 起步，每次增减 2–4 层观察显存和稳定性。"
            )
        models.append(
            {
                "id": model["id"],
                "name": model["name"],
                "position": position,
                "rulesVersion": "p1-2026-07-31",
                "risk": "空闲 RAM/VRAM 会在检测后变化；最终卸载层数与是否成功以 llama.cpp 启动日志为准。",
                "parametersBillions": model["parametersBillions"],
                "activeParametersBillions": model.get("activeParametersBillions"),
                "quantization": model["quantization"],
                "estimatedFileGiB": model["estimatedFileGiB"],
                "officialFileSizeGB": model["officialFileSizeGB"],
                "license": model["license"],
                "officialUrl": model["officialUrl"],
                "modelScopeUrl": model["modelScopeUrl"],
                "artifact": {
                    "sharded": bool(model.get("sharded")),
                    "note": (
                        "官方 Q4_K_M 为两分片 GGUF，需保留全部分片"
                        if model.get("sharded")
                        else "官方 Q4_K_M 为单个 GGUF 文件"
                    ),
                },
                "architecture": {
                    "blockCount": model["blockCount"],
                    "nativeContext": model["nativeContext"],
                },
                "memory": {
                    "estimatedRamRequiredGiB": ram_needed,
                    "estimatedKvCacheGiBAt4096": model["kvCacheGiBAt4096"],
                    "estimatedKvCacheGiB": kv_cache_gib,
                    "kvCacheContextSize": context_size,
                },
                "fit": {
                    "status": fit_status,
                    "label": FIT_LABELS[fit_status],
                    "reason": fit_reason,
                    "ramAvailableGiB": ram_available_gib,
                    "hostRamReserveGiB": round(host_ram_reserve, 2),
                    "applicationRamReserveGiB": 1.0,
                    "modelRamBudgetGiB": round(model_ram_budget, 2),
                },
                "offload": {
                    "mode": offload_mode,
                    "layerCount": gpu_layers,
                    "blockCount": model["blockCount"],
                    "numericCompatibilityValue": (
                        model["blockCount"] + 1 if full_offload else gpu_layers
                    ),
                    "fullOffloadValue": "all",
                    "calculation": calculation,
                    "explanation": offload_explanation,
                },
                "suggested": {
                    "ctxSize": context_size,
                    "gpuLayers": 0 if offload_mode == "cpu" else "auto",
                    "threads": hardware.get("cpu", {}).get("physicalCores")
                    or max(1, int(hardware.get("cpu", {}).get("logicalThreads") or 1) // 2),
                },
                "reasons": [
                    (
                        f"按 {total_vram:g} GiB 总显存与当前空闲 {free_vram:g} GiB 分档"
                        if path == "nvidia"
                        else "未确认可用 NVIDIA 后端，采用保守 CPU 路线"
                    ),
                    (
                        f"Q4_K_M 权重文件约 {model['estimatedFileGiB']} GiB；"
                        f"{context_size} 上下文 KV cache 估算约 {kv_cache_gib} GiB"
                    ),
                ],
            }
        )

    models.sort(key=lambda model: (model["id"] != default_id, model["parametersBillions"]))
    return {
        "ok": True,
        "hardware": hardware,
        "posture": (
            "优先稳定启动，同时保留“吃力可跑”档；这类模型会更慢、"
            "更依赖混合卸载或当前空闲内存，需要从保守参数开始实测。"
        ),
        "rules": list(RECOMMENDATION_RULES),
        "assumptions": {
            "systemVramReserve": "max(1 GiB, total VRAM × 15%)",
            "computeVramReserve": "max(0.5 GiB, total VRAM × 5%)",
            "contextSize": context_size,
            "kvCacheTypes": "F16 K + F16 V",
            "rulesVersion": "p1-2026-07-31",
            "hostRamReserve": "max(2 GiB, total RAM × 20%) + 1 GiB application reserve",
        },
        "models": models,
        "learning": list(LEARNING_TOPICS),
    }
