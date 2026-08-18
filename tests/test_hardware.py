import subprocess
import unittest
from unittest.mock import patch

from hardware import HardwareSnapshotCache, LocalSystemProbe, detect_hardware


class NvidiaProbe:
    def operating_system(self):
        return {
            "name": "Windows",
            "release": "11",
            "version": "10.0.26100",
            "architecture": "AMD64",
        }

    def cpu(self):
        return {
            "name": "AMD Ryzen 7 7700",
            "physicalCores": 8,
            "logicalThreads": 16,
        }

    def ram_total_bytes(self):
        return 32 * 1024**3

    def ram_available_bytes(self):
        return 20 * 1024**3

    def nvidia(self):
        return {
            "available": True,
            "path": r"C:\Windows\System32\nvidia-smi.exe",
            "gpus": [
                {
                    "index": 0,
                    "name": "NVIDIA GeForce RTX 4070",
                    "vramTotalBytes": 12 * 1024**3,
                    "vramFreeBytes": 10 * 1024**3,
                    "driverVersion": "576.80",
                }
            ],
        }

    def display_adapters(self):
        return []


class CpuFallbackProbe(NvidiaProbe):
    def nvidia(self):
        return {
            "available": False,
            "path": None,
            "gpus": [],
            "error": "nvidia-smi was not found",
        }

    def display_adapters(self):
        return [{"name": "AMD Radeon Graphics", "vendor": "AMD"}]


class BrokenNvidiaProbe(CpuFallbackProbe):
    def nvidia(self):
        raise OSError("driver query failed")


class BrokenMemoryProbe(CpuFallbackProbe):
    def ram_total_bytes(self):
        raise OSError("total RAM query failed")

    def ram_available_bytes(self):
        raise OSError("available RAM query failed")


class HardwareDetectionTests(unittest.TestCase):
    def test_hardware_snapshot_cache_reuses_and_isolates_recent_detection(self):
        calls = []

        def detector():
            calls.append("called")
            return {"ok": True, "gpus": [{"name": "GPU"}]}

        cache = HardwareSnapshotCache(detector, max_age_seconds=2)
        first = cache.get()
        first["gpus"][0]["name"] = "mutated"
        second = cache.get()

        self.assertEqual(calls, ["called"])
        self.assertEqual(second["gpus"][0]["name"], "GPU")

    def test_nvidia_parser_keeps_valid_gpus_when_another_row_is_invalid(self):
        mixed_rows = subprocess.CompletedProcess(
            ["nvidia-smi"],
            returncode=0,
            stdout=(
                "0, NVIDIA Valid GPU, 8192, 7168, 576.80\n"
                "1, NVIDIA Invalid GPU, N/A, N/A, 576.80\n"
                "2, NVIDIA Second GPU, 24576, 20000, 576.80\n"
            ),
            stderr="",
        )
        with (
            patch("hardware.shutil.which", return_value=r"C:\nvidia-smi.exe"),
            patch("hardware.subprocess.run", return_value=mixed_rows),
        ):
            result = LocalSystemProbe().nvidia()

        self.assertTrue(result["available"])
        self.assertEqual(len(result["gpus"]), 2)
        self.assertEqual(result["gpus"][0]["name"], "NVIDIA Valid GPU")
        self.assertEqual(result["gpus"][1]["vramTotalBytes"], 24576 * 1024**2)
        self.assertEqual(result["confidence"], "degraded")
        self.assertIn("row", result["warning"].lower())

    def test_windows_build_number_distinguishes_windows_eleven(self):
        with (
            patch("hardware.platform.system", return_value="Windows"),
            patch("hardware.platform.release", return_value="10"),
            patch("hardware.platform.version", return_value="10.0.26200"),
            patch("hardware.platform.machine", return_value="AMD64"),
        ):
            operating_system = LocalSystemProbe().operating_system()

        self.assertEqual(operating_system["release"], "11")
        self.assertEqual(operating_system["displayName"], "Windows 11")

    def test_nvidia_query_degrades_when_driver_field_is_unavailable(self):
        failed_driver_query = subprocess.CompletedProcess(
            ["nvidia-smi"],
            returncode=2,
            stdout="",
            stderr="Field driver_version is not a valid field",
        )
        core_query = subprocess.CompletedProcess(
            ["nvidia-smi"],
            returncode=0,
            stdout="0, NVIDIA Test GPU, 8192, 7168\n",
            stderr="",
        )
        with (
            patch("hardware.shutil.which", return_value=r"C:\nvidia-smi.exe"),
            patch(
                "hardware.subprocess.run",
                side_effect=[failed_driver_query, core_query],
            ),
        ):
            result = LocalSystemProbe().nvidia()

        self.assertTrue(result["available"])
        self.assertEqual(result["confidence"], "degraded")
        self.assertIsNone(result["gpus"][0]["driverVersion"])
        self.assertIn("driver version", result["warning"].lower())

    def test_default_probe_returns_a_usable_local_report(self):
        report = detect_hardware()

        self.assertTrue(report["ok"])
        self.assertIn(report["recommendationPath"], {"nvidia", "cpu"})
        self.assertGreaterEqual(report["cpu"]["logicalThreads"], 1)
        self.assertGreater(report["memory"]["ramTotalBytes"], 0)

    def test_nvidia_machine_reports_capacity_and_acceleration_path(self):
        report = detect_hardware(NvidiaProbe())

        self.assertTrue(report["ok"])
        self.assertEqual(report["recommendationPath"], "nvidia")
        self.assertEqual(report["cpu"]["physicalCores"], 8)
        self.assertEqual(report["cpu"]["logicalThreads"], 16)
        self.assertEqual(report["memory"]["ramTotalBytes"], 32 * 1024**3)
        self.assertEqual(report["memory"]["ramTotalGiB"], 32.0)
        self.assertEqual(report["memory"]["ramAvailableBytes"], 20 * 1024**3)
        self.assertEqual(report["memory"]["ramAvailableGiB"], 20.0)
        self.assertEqual(report["gpus"][0]["vramTotalGiB"], 12.0)
        self.assertEqual(report["gpus"][0]["vramFreeGiB"], 10.0)
        self.assertEqual(report["gpus"][0]["source"], "nvidia-smi")
        self.assertEqual(report["gpus"][0]["confidence"], "high")
        self.assertTrue(report["nvidiaSmi"]["available"])
        self.assertEqual(report["warnings"], [])

    def test_non_nvidia_machine_uses_conservative_cpu_path(self):
        report = detect_hardware(CpuFallbackProbe())

        self.assertTrue(report["ok"])
        self.assertEqual(report["recommendationPath"], "cpu")
        self.assertEqual(report["gpus"], [{"name": "AMD Radeon Graphics", "vendor": "AMD"}])
        self.assertFalse(report["nvidiaSmi"]["available"])
        self.assertIn("nvidia-smi was not found", report["warnings"])

    def test_failed_nvidia_probe_does_not_break_hardware_report(self):
        report = detect_hardware(BrokenNvidiaProbe())

        self.assertTrue(report["ok"])
        self.assertEqual(report["recommendationPath"], "cpu")
        self.assertIn("driver query failed", report["warnings"][0])

    def test_failed_memory_probe_returns_unknown_values_and_warnings(self):
        report = detect_hardware(BrokenMemoryProbe())

        self.assertTrue(report["ok"])
        self.assertIsNone(report["memory"]["ramTotalBytes"])
        self.assertIsNone(report["memory"]["ramAvailableBytes"])
        self.assertTrue(
            any("total RAM query failed" in warning for warning in report["warnings"])
        )


if __name__ == "__main__":
    unittest.main()
