from __future__ import annotations

import csv
import ctypes
import copy
import json
import os
import platform
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Callable


class HardwareSnapshotCache:
    def __init__(
        self,
        detector: Callable[[], dict[str, Any]],
        *,
        max_age_seconds: float = 2.0,
    ) -> None:
        self.detector = detector
        self.max_age_seconds = max_age_seconds
        self._condition = threading.Condition()
        self._snapshot: dict[str, Any] | None = None
        self._captured_at = 0.0
        self._detecting = False

    def get(self) -> dict[str, Any]:
        with self._condition:
            while True:
                now = time.monotonic()
                if (
                    self._snapshot is not None
                    and now - self._captured_at <= self.max_age_seconds
                ):
                    return copy.deepcopy(self._snapshot)
                if not self._detecting:
                    self._detecting = True
                    break
                self._condition.wait()

        try:
            snapshot = self.detector()
        except Exception:
            with self._condition:
                self._detecting = False
                self._condition.notify_all()
            raise

        with self._condition:
            self._snapshot = copy.deepcopy(snapshot)
            self._captured_at = time.monotonic()
            self._detecting = False
            self._condition.notify_all()
            return copy.deepcopy(self._snapshot)


class LocalSystemProbe:
    def operating_system(self) -> dict[str, Any]:
        name = platform.system() or os.name
        release = platform.release()
        version = platform.version()
        if name == "Windows":
            try:
                build_number = int(version.split(".")[2])
            except (IndexError, ValueError):
                build_number = 0
            if release == "10" and build_number >= 22000:
                release = "11"
        return {
            "name": name,
            "release": release,
            "displayName": f"{name} {release}".strip(),
            "version": version,
            "architecture": platform.machine(),
        }

    def cpu(self) -> dict[str, Any]:
        logical_threads = os.cpu_count() or 1
        fallback = {
            "name": platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER") or "Unknown CPU",
            "physicalCores": None,
            "logicalThreads": logical_threads,
        }
        if os.name != "nt":
            return fallback
        try:
            rows = self._powershell_json(
                "Get-CimInstance Win32_Processor | "
                "Select-Object Name,NumberOfCores,NumberOfLogicalProcessors | "
                "ConvertTo-Json -Compress"
            )
        except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
            return fallback
        processors = rows if isinstance(rows, list) else [rows]
        processors = [item for item in processors if isinstance(item, dict)]
        if not processors:
            return fallback
        return {
            "name": " + ".join(
                str(item.get("Name", "")).strip()
                for item in processors
                if str(item.get("Name", "")).strip()
            )
            or fallback["name"],
            "physicalCores": sum(int(item.get("NumberOfCores") or 0) for item in processors)
            or None,
            "logicalThreads": sum(
                int(item.get("NumberOfLogicalProcessors") or 0) for item in processors
            )
            or logical_threads,
        }

    def ram_total_bytes(self) -> int:
        if os.name == "nt":
            total, _ = self._windows_memory()
            return total
        page_size = os.sysconf("SC_PAGE_SIZE")
        page_count = os.sysconf("SC_PHYS_PAGES")
        return int(page_size * page_count)

    def ram_available_bytes(self) -> int | None:
        if os.name == "nt":
            _, available = self._windows_memory()
            return available
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            page_count = os.sysconf("SC_AVPHYS_PAGES")
        except (AttributeError, OSError, ValueError):
            return None
        return int(page_size * page_count)

    def nvidia(self) -> dict[str, Any]:
        executable = shutil.which("nvidia-smi")
        if not executable:
            return {
                "available": False,
                "path": None,
                "gpus": [],
                "error": "nvidia-smi was not found; using the conservative CPU route.",
            }
        try:
            result = self._run(
                [
                    executable,
                    "--query-gpu=index,name,memory.total,memory.free,driver_version",
                    "--format=csv,noheader,nounits",
                ]
            )
            if result.returncode != 0:
                core_result = self._run(
                    [
                        executable,
                        "--query-gpu=index,name,memory.total,memory.free",
                        "--format=csv,noheader,nounits",
                    ]
                )
                if core_result.returncode != 0:
                    raise OSError(
                        core_result.stderr.strip()
                        or result.stderr.strip()
                        or f"nvidia-smi exited {core_result.returncode}"
                    )
                gpus, invalid_rows = self._parse_nvidia_rows(
                    core_result.stdout,
                    include_driver=False,
                )
                if not gpus:
                    raise ValueError("nvidia-smi returned no usable GPU rows")
                warning = "GPU memory was detected, but the driver version field was unavailable."
                if invalid_rows:
                    warning += f" Skipped {invalid_rows} invalid GPU row(s)."
                return {
                    "available": True,
                    "path": executable,
                    "gpus": gpus,
                    "confidence": "degraded",
                    "warning": warning,
                }
            gpus, invalid_rows = self._parse_nvidia_rows(
                result.stdout,
                include_driver=True,
            )
            if not gpus:
                raise ValueError("nvidia-smi returned no usable GPU rows")
            payload = {
                "available": True,
                "path": executable,
                "gpus": gpus,
                "confidence": "degraded" if invalid_rows else "high",
            }
            if invalid_rows:
                payload["warning"] = f"Skipped {invalid_rows} invalid nvidia-smi GPU row(s)."
            return payload
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            return {
                "available": False,
                "path": executable,
                "gpus": [],
                "error": f"nvidia-smi detection failed ({exc}); using the conservative CPU route.",
            }

    def display_adapters(self) -> list[dict[str, Any]]:
        if os.name != "nt":
            return []
        try:
            rows = self._powershell_json(
                "Get-CimInstance Win32_VideoController | "
                "Select-Object Name,AdapterRAM | ConvertTo-Json -Compress"
            )
        except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
            return []
        adapters = rows if isinstance(rows, list) else [rows]
        result = []
        for adapter in adapters:
            if not isinstance(adapter, dict):
                continue
            name = str(adapter.get("Name", "")).strip()
            if not name:
                continue
            lowered = name.lower()
            vendor = (
                "NVIDIA"
                if "nvidia" in lowered
                else "AMD"
                if "amd" in lowered or "radeon" in lowered
                else "Intel"
                if "intel" in lowered
                else "Unknown"
            )
            item = {"name": name, "vendor": vendor}
            adapter_ram = adapter.get("AdapterRAM")
            if isinstance(adapter_ram, int) and adapter_ram > 0:
                item["vramTotalBytes"] = adapter_ram
                item["vramTotalGiB"] = _gib(adapter_ram)
                item["vramEstimate"] = True
            result.append(item)
        return result

    def _powershell_json(self, script: str) -> Any:
        executable = shutil.which("powershell.exe") or shutil.which("pwsh")
        if not executable:
            raise OSError("PowerShell was not found")
        result = self._run([executable, "-NoProfile", "-NonInteractive", "-Command", script])
        if result.returncode != 0:
            raise OSError(result.stderr.strip() or f"PowerShell exited {result.returncode}")
        if not result.stdout.strip():
            raise ValueError("PowerShell returned no data")
        return json.loads(result.stdout)

    @staticmethod
    def _parse_nvidia_rows(
        output: str,
        *,
        include_driver: bool,
    ) -> tuple[list[dict[str, Any]], int]:
        expected_columns = 5 if include_driver else 4
        gpus = []
        invalid_rows = 0
        for row in csv.reader(StringIO(output)):
            if len(row) != expected_columns:
                invalid_rows += 1
                continue
            values = [value.strip() for value in row]
            try:
                index = int(values[0])
                name = values[1]
                total_mib = int(float(values[2]))
                free_mib = int(float(values[3]))
                if not name or total_mib <= 0 or free_mib < 0:
                    raise ValueError("invalid GPU values")
            except (ValueError, OverflowError):
                invalid_rows += 1
                continue
            gpus.append(
                {
                    "index": index,
                    "name": name,
                    "vramTotalBytes": total_mib * 1024**2,
                    "vramFreeBytes": free_mib * 1024**2,
                    "driverVersion": values[4] if include_driver else None,
                }
            )
        return gpus, invalid_rows

    @staticmethod
    def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            shell=False,
            creationflags=creation_flags,
        )

    @staticmethod
    def _windows_memory() -> tuple[int, int]:
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memoryLoad", ctypes.c_ulong),
                ("totalPhysical", ctypes.c_ulonglong),
                ("availablePhysical", ctypes.c_ulonglong),
                ("totalPageFile", ctypes.c_ulonglong),
                ("availablePageFile", ctypes.c_ulonglong),
                ("totalVirtual", ctypes.c_ulonglong),
                ("availableVirtual", ctypes.c_ulonglong),
                ("availableExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("GlobalMemoryStatusEx failed")
        return int(status.totalPhysical), int(status.availablePhysical)


def _gib(value: int | None) -> float | None:
    if value is None:
        return None
    return round(value / 1024**3, 2)


def detect_hardware(probe: Any | None = None) -> dict[str, Any]:
    probe = probe or LocalSystemProbe()
    detected_at = datetime.now(timezone.utc).isoformat()
    warnings = []
    operating_system = probe.operating_system()
    cpu = probe.cpu()
    try:
        ram_total_bytes = probe.ram_total_bytes()
    except Exception as exc:
        ram_total_bytes = None
        warnings.append(f"Total RAM detection failed ({exc}).")
    try:
        ram_available_bytes = probe.ram_available_bytes()
    except Exception as exc:
        ram_available_bytes = None
        warnings.append(f"Available RAM detection failed ({exc}).")
    try:
        nvidia = probe.nvidia()
    except Exception as exc:
        nvidia = {
            "available": False,
            "path": None,
            "gpus": [],
            "error": f"NVIDIA detection failed ({exc}); using the conservative CPU route.",
        }
    gpus = []
    for gpu in nvidia.get("gpus", []):
        gpus.append(
            {
                **gpu,
                "vendor": "NVIDIA",
                "source": "nvidia-smi",
                "confidence": nvidia.get("confidence", "high"),
                "vramTotalGiB": _gib(gpu.get("vramTotalBytes")),
                "vramFreeGiB": _gib(gpu.get("vramFreeBytes")),
            }
        )
    nvidia_available = bool(nvidia.get("available") and gpus)
    if not nvidia_available:
        gpus = probe.display_adapters()
        if nvidia.get("error"):
            warnings.append(nvidia["error"])
    elif nvidia.get("warning"):
        warnings.append(nvidia["warning"])

    return {
        "ok": True,
        "detectedAt": detected_at,
        "operatingSystem": operating_system,
        "cpu": cpu,
        "memory": {
            "ramTotalBytes": ram_total_bytes,
            "ramTotalGiB": _gib(ram_total_bytes),
            "ramAvailableBytes": ram_available_bytes,
            "ramAvailableGiB": _gib(ram_available_bytes),
        },
        "gpus": gpus,
        "nvidiaSmi": {
            "available": nvidia_available,
            "path": nvidia.get("path"),
        },
        "recommendationPath": "nvidia" if nvidia_available else "cpu",
        "warnings": warnings,
    }
