import unittest

from recommendations import build_recommendation_report


def hardware_report(
    *,
    path="nvidia",
    vram_gib=8.0,
    free_vram_gib=None,
    ram_gib=32.0,
    ram_available_gib=None,
):
    gpus = []
    if path == "nvidia":
        free = free_vram_gib if free_vram_gib is not None else vram_gib
        gpus = [
            {
                "index": 0,
                "name": "NVIDIA Test GPU",
                "vendor": "NVIDIA",
                "vramTotalBytes": int(vram_gib * 1024**3),
                "vramFreeBytes": int(free * 1024**3),
                "vramTotalGiB": vram_gib,
                "vramFreeGiB": free,
            }
        ]
    return {
        "ok": True,
        "recommendationPath": path,
        "operatingSystem": {"name": "Windows", "release": "11"},
        "cpu": {"name": "Test CPU", "physicalCores": 8, "logicalThreads": 16},
        "memory": {
            "ramTotalBytes": int(ram_gib * 1024**3),
            "ramTotalGiB": ram_gib,
            "ramAvailableBytes": int(
                (ram_available_gib if ram_available_gib is not None else ram_gib * 0.75)
                * 1024**3
            ),
            "ramAvailableGiB": (
                ram_available_gib if ram_available_gib is not None else ram_gib * 0.75
            ),
        },
        "gpus": gpus,
        "nvidiaSmi": {"available": path == "nvidia", "path": "nvidia-smi"},
        "warnings": [],
    }


class RecommendationTests(unittest.TestCase):
    def test_every_model_card_contains_provenance_budget_reason_and_risk(self):
        report = build_recommendation_report(hardware_report(vram_gib=8.0))

        for model in report["models"]:
            with self.subTest(model=model["id"]):
                self.assertTrue(model["officialUrl"].startswith("https://"))
                self.assertTrue(
                    model["modelScopeUrl"].startswith(
                        "https://modelscope.cn/models/Qwen/"
                    )
                )
                self.assertTrue(model["license"])
                self.assertTrue(model["reasons"])
                self.assertTrue(model["risk"])
                self.assertEqual(model["rulesVersion"], "p1-2026-07-31")
                self.assertIn("calculation", model["offload"])
                self.assertIn("ramAvailableGiB", model["fit"])
                self.assertIn("modelRamBudgetGiB", model["fit"])

    def test_eight_k_context_doubles_kv_and_can_downgrade_the_safe_default(self):
        hardware = hardware_report(vram_gib=8.0, free_vram_gib=6.35)

        four_k = build_recommendation_report(hardware, context_size=4096)
        eight_k = build_recommendation_report(hardware, context_size=8192)
        four_k_seven_b = next(
            model
            for model in four_k["models"]
            if model["id"] == "qwen2.5-7b-instruct-q4-k-m"
        )
        eight_k_seven_b = next(
            model
            for model in eight_k["models"]
            if model["id"] == "qwen2.5-7b-instruct-q4-k-m"
        )

        self.assertAlmostEqual(
            eight_k_seven_b["memory"]["estimatedKvCacheGiB"],
            four_k_seven_b["memory"]["estimatedKvCacheGiB"] * 2,
            places=3,
        )
        self.assertEqual(four_k["models"][0]["id"], "qwen2.5-7b-instruct-q4-k-m")
        self.assertEqual(eight_k["models"][0]["id"], "qwen3-4b-q4-k-m")

    def test_zero_free_vram_never_falls_back_to_total_vram(self):
        report = build_recommendation_report(
            hardware_report(vram_gib=8.0, free_vram_gib=0.0, ram_gib=16.0)
        )

        self.assertEqual(report["models"][0]["offload"]["mode"], "cpu")
        self.assertEqual(
            report["models"][0]["offload"]["calculation"]["vramFreeGiB"],
            0.0,
        )
        self.assertTrue(
            all(model["offload"]["mode"] != "full" for model in report["models"])
        )

    def test_unknown_available_ram_is_never_labeled_safe(self):
        hardware = hardware_report(path="cpu", ram_gib=16.0)
        hardware["memory"]["ramAvailableBytes"] = None
        hardware["memory"]["ramAvailableGiB"] = None

        report = build_recommendation_report(hardware)

        self.assertEqual(report["models"][0]["position"], "lowest-risk")
        self.assertTrue(
            all(
                model["fit"]["status"] == "not-recommended"
                for model in report["models"]
            )
        )

    def test_full_gpu_offload_still_requires_the_declared_host_ram_reserve(self):
        report = build_recommendation_report(
            hardware_report(
                vram_gib=8.0,
                free_vram_gib=8.0,
                ram_gib=64.0,
                ram_available_gib=2.2,
            )
        )

        self.assertEqual(report["models"][0]["position"], "lowest-risk")
        self.assertEqual(report["models"][0]["fit"]["status"], "not-recommended")
        self.assertEqual(report["models"][0]["fit"]["modelRamBudgetGiB"], 0.0)

    def test_exhausted_vram_uses_cpu_semantics_for_the_lowest_risk_model(self):
        report = build_recommendation_report(
            hardware_report(vram_gib=8.0, free_vram_gib=1.0, ram_gib=16.0)
        )

        self.assertEqual(
            report["models"][0]["id"],
            "qwen2.5-0.5b-instruct-q4-k-m",
        )
        self.assertEqual(report["models"][0]["offload"]["mode"], "cpu")
        self.assertEqual(report["models"][0]["suggested"]["gpuLayers"], 0)

    def test_reported_sixteen_gib_card_prefers_fourteen_billion_model(self):
        report = build_recommendation_report(
            hardware_report(vram_gib=15.99, free_vram_gib=14.4)
        )

        self.assertEqual(report["models"][0]["id"], "qwen3-14b-q4-k-m")
        self.assertEqual(report["models"][0]["position"], "safe-default")

    def test_sixteen_gib_card_also_exposes_a_thirty_billion_stretch_option(self):
        report = build_recommendation_report(
            hardware_report(
                vram_gib=16.0,
                free_vram_gib=16.0,
                ram_gib=64.0,
                ram_available_gib=48.0,
            )
        )

        stretch = next(
            model
            for model in report["models"]
            if model["id"] == "qwen3-30b-a3b-q4-k-m"
        )
        self.assertEqual(len(report["models"]), 8)
        self.assertEqual(stretch["fit"]["status"], "try")
        self.assertEqual(stretch["fit"]["label"], "吃力可跑")
        self.assertEqual(stretch["offload"]["mode"], "hybrid")
        self.assertEqual(
            stretch["modelScopeUrl"],
            "https://modelscope.cn/models/Qwen/Qwen3-30B-A3B-GGUF",
        )
        self.assertIn("吃力可跑", report["posture"])

    def test_hybrid_stretch_uses_remaining_host_weights_instead_of_full_model(self):
        report = build_recommendation_report(
            hardware_report(
                vram_gib=15.99,
                free_vram_gib=14.37,
                ram_gib=31.75,
                ram_available_gib=15.25,
            )
        )

        stretch = next(
            model
            for model in report["models"]
            if model["id"] == "qwen3-30b-a3b-q4-k-m"
        )
        self.assertEqual(stretch["fit"]["status"], "try")
        self.assertEqual(stretch["fit"]["label"], "吃力可跑")
        self.assertEqual(stretch["offload"]["mode"], "hybrid")
        self.assertLessEqual(
            stretch["offload"]["calculation"]["estimatedHostWeightGiB"],
            stretch["fit"]["modelRamBudgetGiB"],
        )

    def test_twelve_gib_keeps_fourteen_billion_model_as_a_try_option(self):
        report = build_recommendation_report(
            hardware_report(vram_gib=12.0, free_vram_gib=12.0)
        )

        self.assertEqual(report["models"][0]["id"], "qwen3-8b-q4-k-m")
        self.assertEqual(
            report["models"][0]["offload"]["numericCompatibilityValue"],
            37,
        )
        fourteen_b = next(
            model for model in report["models"] if model["id"] == "qwen3-14b-q4-k-m"
        )
        self.assertEqual(fourteen_b["fit"]["status"], "try")
        self.assertIn("更大的能力选项", fourteen_b["fit"]["reason"])

    def test_cpu_recommendation_uses_available_ram_not_installed_ram(self):
        report = build_recommendation_report(
            hardware_report(
                path="cpu",
                ram_gib=16.0,
                ram_available_gib=5.0,
            )
        )

        self.assertEqual(
            report["models"][0]["id"],
            "qwen2.5-0.5b-instruct-q4-k-m",
        )
        self.assertEqual(report["models"][0]["fit"]["status"], "safe")
        three_b = next(
            model
            for model in report["models"]
            if model["id"] == "qwen2.5-3b-instruct-q4-k-m"
        )
        self.assertEqual(three_b["fit"]["status"], "not-recommended")

    def test_busy_eight_gib_gpu_is_downgraded_by_current_free_vram(self):
        report = build_recommendation_report(
            hardware_report(vram_gib=8.0, free_vram_gib=3.0)
        )

        self.assertEqual(
            report["models"][0]["id"],
            "qwen2.5-1.5b-instruct-q4-k-m",
        )
        self.assertEqual(report["models"][0]["position"], "safe-default")
        self.assertIn("3", " ".join(report["models"][0]["reasons"]))

    def test_cpu_fallback_recommends_small_model_and_zero_gpu_layers(self):
        report = build_recommendation_report(
            hardware_report(path="cpu", ram_gib=16.0)
        )

        self.assertEqual(
            report["models"][0]["id"],
            "qwen2.5-1.5b-instruct-q4-k-m",
        )
        self.assertTrue(
            all(model["suggested"]["gpuLayers"] == 0 for model in report["models"])
        )
        self.assertEqual(report["models"][0]["offload"]["mode"], "cpu")
        self.assertIn("CPU", report["models"][0]["reasons"][0])

    def test_cpu_fallback_marks_larger_memory_fitting_models_as_stretch_options(self):
        report = build_recommendation_report(
            hardware_report(
                path="cpu",
                ram_gib=16.0,
                ram_available_gib=12.0,
            )
        )

        three_b = next(
            model
            for model in report["models"]
            if model["id"] == "qwen2.5-3b-instruct-q4-k-m"
        )
        self.assertEqual(three_b["fit"]["status"], "try")
        self.assertEqual(three_b["fit"]["label"], "吃力可跑")
        self.assertIn("纯 CPU", three_b["fit"]["reason"])

    def test_eight_gib_nvidia_prefers_stable_seven_billion_q4_model(self):
        report = build_recommendation_report(hardware_report(vram_gib=8.0))

        self.assertTrue(report["ok"])
        self.assertEqual(len(report["models"]), 8)
        self.assertEqual(report["models"][0]["id"], "qwen2.5-7b-instruct-q4-k-m")
        self.assertEqual(report["models"][0]["position"], "safe-default")
        self.assertEqual(report["models"][0]["suggested"]["gpuLayers"], "auto")
        self.assertEqual(report["models"][0]["offload"]["mode"], "full")
        self.assertEqual(report["models"][0]["offload"]["numericCompatibilityValue"], 29)
        self.assertIn("启动日志", report["models"][0]["risk"])
        self.assertEqual(report["models"][0]["rulesVersion"], "p1-2026-07-31")
        self.assertTrue(report["models"][0]["artifact"]["sharded"])
        self.assertIn("两分片", report["models"][0]["artifact"]["note"])
        self.assertGreaterEqual(len(report["models"][0]["reasons"]), 2)
        self.assertGreaterEqual(len(report["rules"]), 5)

    def test_hybrid_offload_exposes_the_layer_budget_calculation(self):
        report = build_recommendation_report(
            hardware_report(vram_gib=6.0, free_vram_gib=4.0)
        )
        larger_model = next(
            model
            for model in report["models"]
            if model["id"] == "qwen3-14b-q4-k-m"
        )

        self.assertEqual(larger_model["offload"]["mode"], "hybrid")
        self.assertGreater(larger_model["offload"]["layerCount"], 0)
        self.assertLess(
            larger_model["offload"]["layerCount"],
            larger_model["offload"]["blockCount"],
        )
        calculation = larger_model["offload"]["calculation"]
        self.assertEqual(calculation["vramTotalGiB"], 6.0)
        self.assertEqual(calculation["vramFreeGiB"], 4.0)
        self.assertIn("estimatedLayerGiB", calculation)
        self.assertIn("runtimeReserveGiB", calculation)
        self.assertIn("--gpu-layers", larger_model["offload"]["explanation"])

    def test_learning_surface_covers_memory_and_cpu_gpu_offload_in_depth(self):
        report = build_recommendation_report(hardware_report(vram_gib=8.0))
        topics = {topic["id"]: topic for topic in report["learning"]}

        self.assertTrue(
            {
                "parameters",
                "quantization",
                "gguf",
                "weight-memory",
                "kv-cache",
                "cpu-inference",
                "gpu-offload",
                "hybrid-offload",
                "gpu-layer-selection",
                "context-and-batch",
            }.issubset(topics)
        )
        layer_topic = topics["gpu-layer-selection"]
        self.assertIn("--gpu-layers", layer_topic["details"])
        self.assertIn("输出层", layer_topic["details"])
        self.assertIn("auto", topics["gpu-offload"]["details"])
        self.assertIn("all", topics["gpu-offload"]["details"])
        self.assertIn("--device none", topics["cpu-inference"]["details"])
        self.assertGreaterEqual(len(layer_topic["steps"]), 4)
        self.assertGreaterEqual(len(layer_topic["sources"]), 1)
        self.assertIn("不是精确值", layer_topic["caution"])


if __name__ == "__main__":
    unittest.main()
