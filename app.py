from __future__ import annotations

import ctypes
import ipaddress
import json
import math
import os
import shlex
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


HOST = "127.0.0.1"
PORT = 58001
ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DATA_DIR = ROOT / "data"
PRESETS_FILE = DATA_DIR / "presets.json"
LOG_FILE = DATA_DIR / "runtime.log"
PID_FILE = DATA_DIR / "llmgarage.pid"
MAX_LOG_LINES = 500
MAX_LOG_FILE_BYTES = 2 * 1024 * 1024
MAX_LOG_BACKUPS = 3
MAX_REQUEST_BODY_BYTES = 1024 * 1024


class RequestError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


class RuntimeState:
    def __init__(self) -> None:
        self.process: subprocess.Popen[str] | None = None
        self.started_at: float | None = None
        self.command: list[str] = []
        self.last_exit_code: int | None = None
        self.last_exit_at: float | None = None
        self.last_exit_reason: str | None = None
        self.requested_exit_reason: str | None = None
        self.logs: deque[str] = deque(maxlen=MAX_LOG_LINES)
        self.lock = threading.RLock()


STATE = RuntimeState()


DEFAULT_PRESET = {
    "id": "default",
    "name": "Default llama.cpp server",
    "serverPath": "",
    "modelPath": "",
    "host": "127.0.0.1",
    "port": 8080,
    "ctxSize": 4096,
    "gpuLayers": "",
    "threads": "",
    "batchSize": "",
    "ubatchSize": "",
    "parallel": "",
    "temperature": "",
    "topP": "",
    "embedding": False,
    "reranking": False,
    "advancedArgs": "",
}

PRESET_STRING_FIELDS = {"serverPath", "modelPath", "host", "advancedArgs"}
PRESET_INTEGER_FIELDS = {
    "port",
    "ctxSize",
    "gpuLayers",
    "threads",
    "batchSize",
    "ubatchSize",
    "parallel",
}
PRESET_FLOAT_FIELDS = {
    "temperature",
    "topP",
}
PRESET_BOOLEAN_FIELDS = {"embedding", "reranking"}


def ensure_data_files() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if not PRESETS_FILE.exists():
        write_json(PRESETS_FILE, {"presets": [DEFAULT_PRESET]})
    if not LOG_FILE.exists():
        LOG_FILE.touch()

def write_app_pid() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="ascii")


def clear_app_pid() -> None:
    try:
        if PID_FILE.exists() and PID_FILE.read_text(encoding="ascii").strip() == str(os.getpid()):
            PID_FILE.unlink()
    except OSError:
        pass

def read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
            newline="\n",
        ) as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.replace(temporary_path, path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def validate_presets(presets: Any) -> list[dict[str, Any]]:
    if not isinstance(presets, list):
        raise ValueError("presets must be a list")

    seen_ids: set[str] = set()
    for index, preset in enumerate(presets):
        label = f"preset {index + 1}"
        if not isinstance(preset, dict):
            raise ValueError(f"{label} must be an object")

        preset_id = preset.get("id")
        name = preset.get("name")
        if not isinstance(preset_id, str) or not preset_id.strip() or len(preset_id) > 128:
            raise ValueError(f"{label} id must be a non-empty string up to 128 characters")
        if preset_id in seen_ids:
            raise ValueError(f"duplicate preset id: {preset_id}")
        seen_ids.add(preset_id)
        if not isinstance(name, str) or not name.strip() or len(name) > 256:
            raise ValueError(f"{label} name must be a non-empty string up to 256 characters")

        for field in PRESET_STRING_FIELDS:
            if field in preset and not isinstance(preset[field], str):
                raise ValueError(f"{label} field {field} must be a string")
        for field in PRESET_INTEGER_FIELDS:
            value = preset.get(field, "")
            if value in ("", "auto", None):
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{label} field {field} must be an integer or auto")
        for field in PRESET_FLOAT_FIELDS:
            value = preset.get(field, "")
            if value in ("", "auto", None):
                continue
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError(f"{label} field {field} must be a finite number or auto")
        for field in PRESET_BOOLEAN_FIELDS:
            if field in preset and not isinstance(preset[field], bool):
                raise ValueError(f"{label} field {field} must be a boolean")

        port = preset.get("port")
        if port not in ("", "auto", None) and not 1 <= port <= 65535:
            raise ValueError(f"{label} port must be between 1 and 65535")

    return presets


def rotated_log_path(index: int) -> Path:
    return LOG_FILE.with_name(f"{LOG_FILE.stem}.{index}{LOG_FILE.suffix}")


def rotate_log_if_needed(incoming_bytes: int) -> None:
    if not LOG_FILE.exists() or LOG_FILE.stat().st_size + incoming_bytes <= MAX_LOG_FILE_BYTES:
        return
    rotated_log_path(MAX_LOG_BACKUPS).unlink(missing_ok=True)
    for index in range(MAX_LOG_BACKUPS - 1, 0, -1):
        source = rotated_log_path(index)
        if source.exists():
            os.replace(source, rotated_log_path(index + 1))
    os.replace(LOG_FILE, rotated_log_path(1))


def bounded_log_line(line: str) -> str:
    suffix = " [truncated]"
    if len((line + "\n").encode("utf-8")) <= MAX_LOG_FILE_BYTES:
        return line
    byte_budget = MAX_LOG_FILE_BYTES - len((suffix + "\n").encode("utf-8"))
    prefix = line.encode("utf-8")[: max(0, byte_budget)].decode("utf-8", errors="ignore")
    return prefix + suffix


def add_log(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = bounded_log_line(f"[{timestamp}] {message}")
    with STATE.lock:
        STATE.logs.append(line)
        LOG_FILE.parent.mkdir(exist_ok=True)
        encoded_line = (line + "\n").encode("utf-8")
        rotate_log_if_needed(len(encoded_line))
        with LOG_FILE.open("ab") as handle:
            handle.write(encoded_line)


def parse_extra_args(raw: str) -> list[str]:
    raw = (raw or "").strip()
    if not raw:
        return []
    if os.name == "nt":
        return command_line_to_argv_windows(raw)
    return shlex.split(raw)


def command_line_to_argv_windows(command_line: str) -> list[str]:
    argc = ctypes.c_int()
    argv_ptr = ctypes.windll.shell32.CommandLineToArgvW(command_line, ctypes.byref(argc))
    if not argv_ptr:
        raise ValueError("Unable to parse advanced arguments")
    try:
        return [argv_ptr[i] for i in range(argc.value)]
    finally:
        ctypes.windll.kernel32.LocalFree(argv_ptr)


def coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def maybe_add_value(argv: list[str], flag: str, value: Any, *, positive_only: bool = True) -> None:
    if value in ("", None, "auto"):
        return
    number = coerce_int(value, 0)
    if positive_only and number <= 0:
        return
    argv.extend([flag, str(number)])


def build_argv(preset: dict[str, Any]) -> list[str]:
    server_path = str(preset.get("serverPath", "")).strip()
    model_path = str(preset.get("modelPath", "")).strip()
    if not server_path:
        raise ValueError("llama-server.exe path is required")
    if not model_path:
        raise ValueError("GGUF model path is required")

    argv = [server_path, "--model", model_path]
    host = str(preset.get("host", "")).strip() or "127.0.0.1"
    port = coerce_int(preset.get("port"), 8080)
    argv.extend(["--host", host, "--port", str(port)])

    maybe_add_value(argv, "--ctx-size", preset.get("ctxSize"))
    maybe_add_value(argv, "--gpu-layers", preset.get("gpuLayers"), positive_only=False)
    maybe_add_value(argv, "--threads", preset.get("threads"))
    maybe_add_value(argv, "--batch-size", preset.get("batchSize"))
    maybe_add_value(argv, "--ubatch-size", preset.get("ubatchSize"))
    maybe_add_value(argv, "--parallel", preset.get("parallel"))

    temperature = coerce_float(preset.get("temperature"), 0.0)
    if temperature > 0:
        argv.extend(["--temp", str(temperature)])
    top_p = coerce_float(preset.get("topP"), 0.0)
    if top_p > 0:
        argv.extend(["--top-p", str(top_p)])

    if preset.get("embedding"):
        argv.append("--embedding")
    if preset.get("reranking"):
        argv.append("--reranking")

    argv.extend(parse_extra_args(str(preset.get("advancedArgs", ""))))
    return argv


def command_preview(argv: list[str]) -> str:
    return subprocess.list2cmdline(argv)


def validate_preset(preset: dict[str, Any]) -> dict[str, Any]:
    messages: list[str] = []
    ok = True
    server_path = Path(str(preset.get("serverPath", "")).strip())
    model_path = Path(str(preset.get("modelPath", "")).strip())

    if not str(server_path):
        ok = False
        messages.append("llama-server.exe path is required.")
    elif not server_path.is_file():
        ok = False
        messages.append("llama-server.exe path does not exist or is not a file.")
    elif server_path.name.lower() != "llama-server.exe":
        messages.append("Server executable is not named llama-server.exe.")

    if not str(model_path):
        ok = False
        messages.append("GGUF model path is required.")
    elif not model_path.is_file():
        ok = False
        messages.append("GGUF model path does not exist or is not a file.")
    elif model_path.suffix.lower() != ".gguf":
        ok = False
        messages.append("Model file must have a .gguf extension.")

    port = coerce_int(preset.get("port"), 0)
    if port < 1 or port > 65535:
        ok = False
        messages.append("llama-server port must be between 1 and 65535.")

    try:
        argv = build_argv(preset)
        preview = command_preview(argv)
    except Exception as exc:
        ok = False
        preview = ""
        messages.append(str(exc))

    return {"ok": ok, "messages": messages or ["Validation passed."], "command": preview}


def is_managed_running() -> bool:
    with STATE.lock:
        return STATE.process is not None and STATE.process.poll() is None


def runtime_status() -> dict[str, Any]:
    with STATE.lock:
        running = STATE.process is not None and STATE.process.poll() is None
        return {
            "running": running,
            "pid": STATE.process.pid if running and STATE.process else None,
            "startedAt": STATE.started_at,
            "uptimeSeconds": int(time.time() - STATE.started_at) if running and STATE.started_at else 0,
            "command": command_preview(STATE.command) if STATE.command else "",
            "lastExitCode": STATE.last_exit_code,
            "lastExitAt": STATE.last_exit_at,
            "lastExitReason": STATE.last_exit_reason,
            "appUrl": f"http://{HOST}:{PORT}",
        }


def read_stream(stream: Any, label: str) -> None:
    try:
        for line in iter(stream.readline, ""):
            if not line:
                break
            add_log(f"{label}: {line.rstrip()}")
    finally:
        stream.close()


def finalize_process_exit(
    process: subprocess.Popen[str],
    returncode: int,
    reason: str | None = None,
    *,
    log_exit: bool = True,
) -> str | None:
    with STATE.lock:
        if STATE.process is not process:
            return None
        exit_reason = reason or STATE.requested_exit_reason or "unexpected"
        STATE.last_exit_code = returncode
        STATE.last_exit_at = time.time()
        STATE.last_exit_reason = exit_reason
        STATE.requested_exit_reason = None
        STATE.process = None
        STATE.started_at = None
        STATE.command = []
    if log_exit:
        add_log(
            f"llama-server process PID {process.pid} exited with code {returncode} "
            f"({exit_reason})."
        )
    return exit_reason


def watch_process(process: subprocess.Popen[str]) -> None:
    returncode = process.wait()
    finalize_process_exit(process, returncode)


def start_process(preset: dict[str, Any]) -> dict[str, Any]:
    validation = validate_preset(preset)
    if not validation["ok"]:
        add_log("Start rejected: " + "; ".join(validation["messages"]))
        return {"ok": False, "messages": validation["messages"]}

    with STATE.lock:
        if STATE.process is not None and STATE.process.poll() is None:
            return {"ok": False, "messages": ["An LLMGarage-managed llama-server process is already running."]}
        argv = build_argv(preset)
        cwd = str(Path(argv[0]).resolve().parent)
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        STATE.process = process
        STATE.started_at = time.time()
        STATE.command = argv
        STATE.last_exit_code = None
        STATE.last_exit_at = None
        STATE.last_exit_reason = None
        STATE.requested_exit_reason = None

    add_log("Started llama-server: " + command_preview(argv))
    if process.stdout:
        threading.Thread(target=read_stream, args=(process.stdout, "stdout"), daemon=True).start()
    if process.stderr:
        threading.Thread(target=read_stream, args=(process.stderr, "stderr"), daemon=True).start()
    threading.Thread(target=watch_process, args=(process,), daemon=True).start()
    return {"ok": True, "messages": ["llama-server started."], "status": runtime_status()}


def stop_process() -> dict[str, Any]:
    with STATE.lock:
        process = STATE.process
        if process is None:
            return {"ok": True, "messages": ["No LLMGarage-managed process is running."]}
        returncode = process.poll()
        if returncode is not None:
            finalize_process_exit(process, returncode)
            return {"ok": True, "messages": ["No LLMGarage-managed process is running."]}
        pid = process.pid
        STATE.requested_exit_reason = "stopped"
        process.terminate()
    try:
        returncode = process.wait(timeout=8)
        add_log(f"Stopped LLMGarage-managed llama-server process PID {pid} with code {returncode}.")
    except subprocess.TimeoutExpired:
        process.kill()
        returncode = process.wait(timeout=2)
        add_log(f"Force killed LLMGarage-managed llama-server process PID {pid} with code {returncode}.")
    finalize_process_exit(process, returncode, "stopped", log_exit=False)
    return {"ok": True, "messages": [f"Stopped process PID {pid}."]}


def kill_all_llama_servers() -> dict[str, Any]:
    if os.name != "nt":
        return {"ok": False, "messages": ["Global stop is only implemented for Windows."]}
    with STATE.lock:
        managed_process = STATE.process
        if managed_process is not None and managed_process.poll() is None:
            STATE.requested_exit_reason = "killed"
    result = subprocess.run(
        ["taskkill", "/IM", "llama-server.exe", "/F"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    output = (result.stdout + result.stderr).strip()
    add_log("Global stop llama-server.exe result: " + (output or f"exit code {result.returncode}"))
    with STATE.lock:
        managed_process = STATE.process
        managed_returncode = managed_process.poll() if managed_process is not None else None
        if (
            result.returncode != 0
            and managed_process is not None
            and managed_returncode is None
            and STATE.requested_exit_reason == "killed"
        ):
            STATE.requested_exit_reason = None
    if managed_process is not None and managed_returncode is not None:
        finalize_process_exit(managed_process, managed_returncode)
    return {"ok": result.returncode == 0, "messages": [output or f"taskkill exited {result.returncode}"]}


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        return None


def request_json(url: str, payload: dict[str, Any] | None = None, timeout: int = 10) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    opener = urllib.request.build_opener(NoRedirectHandler)
    with opener.open(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = body
        return {"status": response.status, "body": parsed}


def api_health(payload: dict[str, Any]) -> dict[str, Any]:
    base = base_url(payload)
    attempts = ["/health", "/v1/models"]
    errors: list[str] = []
    for path in attempts:
        url = base + path
        try:
            result = request_json(url, timeout=5)
            return {"ok": True, "url": url, "result": result}
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            errors.append(f"{url}: {exc}")
    return {"ok": False, "messages": errors}


def api_test_prompt(payload: dict[str, Any]) -> dict[str, Any]:
    base = base_url(payload)
    prompt = str(payload.get("prompt") or "Say hello in one short sentence.")
    chat_payload = {
        "model": "local",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 96,
    }
    try:
        return {"ok": True, "url": base + "/v1/chat/completions", "result": request_json(base + "/v1/chat/completions", chat_payload, timeout=30)}
    except (urllib.error.URLError, TimeoutError, OSError) as chat_error:
        completion_payload = {"prompt": prompt, "temperature": 0.2, "n_predict": 96}
        try:
            return {"ok": True, "url": base + "/completion", "result": request_json(base + "/completion", completion_payload, timeout=30)}
        except (urllib.error.URLError, TimeoutError, OSError) as completion_error:
            return {"ok": False, "messages": [str(chat_error), str(completion_error)]}


def base_url(payload: dict[str, Any]) -> str:
    host = str(payload.get("host") or "127.0.0.1").strip()
    port = coerce_int(payload.get("port"), 8080)
    if port < 1 or port > 65535:
        raise ValueError("Local llama-server port must be between 1 and 65535.")
    if host == "0.0.0.0":
        host = "127.0.0.1"
    elif host in ("::", "[::]"):
        host = "::1"
    if host.lower() == "localhost":
        request_host = "localhost"
    else:
        unwrapped_host = host[1:-1] if host.startswith("[") and host.endswith("]") else host
        try:
            address = ipaddress.ip_address(unwrapped_host)
        except ValueError as exc:
            raise ValueError("Only local llama-server hosts are allowed.") from exc
        if not address.is_loopback:
            raise ValueError("Only local llama-server hosts are allowed.")
        request_host = f"[{address}]" if address.version == 6 else str(address)
    return f"http://{request_host}:{port}"


def normalized_loopback_hostname(hostname: str | None) -> str | None:
    if not hostname:
        return None
    if hostname.lower() == "localhost":
        return "localhost"
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return None
    return str(address) if address.is_loopback else None


def is_allowed_browser_origin(
    origin: str | None,
    request_host: str | None,
    server_port: int,
) -> bool:
    if not origin:
        return True
    if not request_host:
        return False
    try:
        parsed_origin = urlparse(origin)
        parsed_request_host = urlparse(f"http://{request_host}")
        origin_port = parsed_origin.port
        request_port = parsed_request_host.port
    except ValueError:
        return False
    if (
        parsed_origin.scheme != "http"
        or parsed_origin.path
        or parsed_origin.query
        or parsed_origin.fragment
        or parsed_origin.username
        or parsed_origin.password
        or origin_port != server_port
        or request_port != server_port
    ):
        return False
    origin_hostname = normalized_loopback_hostname(parsed_origin.hostname)
    request_hostname = normalized_loopback_hostname(parsed_request_host.hostname)
    return origin_hostname is not None and origin_hostname == request_hostname


class LLMGarageHandler(BaseHTTPRequestHandler):
    server_version = "LLMGarage/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            self.send_json(runtime_status())
        elif parsed.path == "/api/logs":
            with STATE.lock:
                self.send_json({"lines": list(STATE.logs)})
        elif parsed.path == "/api/presets":
            ensure_data_files()
            self.send_json(read_json(PRESETS_FILE, {"presets": [DEFAULT_PRESET]}))
        elif parsed.path.startswith("/api/"):
            self.send_json({"ok": False, "messages": ["Unknown API endpoint."]}, status=404)
        else:
            self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if not is_allowed_browser_origin(
            self.headers.get("Origin"),
            self.headers.get("Host"),
            self.server.server_port,
        ):
            self.send_json({"ok": False, "messages": ["Cross-origin requests are not allowed."]}, status=403)
            return
        try:
            payload = self.read_body()
            if parsed.path == "/api/presets":
                presets = validate_presets(payload.get("presets", []))
                write_json(PRESETS_FILE, {"presets": presets})
                add_log(f"Saved {len(presets)} preset(s).")
                self.send_json({"ok": True, "presets": presets})
            elif parsed.path == "/api/validate":
                self.send_json(validate_preset(payload.get("preset", payload)))
            elif parsed.path == "/api/command":
                argv = build_argv(payload.get("preset", payload))
                self.send_json({"ok": True, "argv": argv, "command": command_preview(argv)})
            elif parsed.path == "/api/start":
                self.send_json(start_process(payload.get("preset", payload)))
            elif parsed.path == "/api/stop":
                self.send_json(stop_process())
            elif parsed.path == "/api/kill-all":
                self.send_json(kill_all_llama_servers())
            elif parsed.path == "/api/health":
                self.send_json(api_health(payload))
            elif parsed.path == "/api/test":
                self.send_json(api_test_prompt(payload))
            elif parsed.path == "/api/shutdown":
                self.send_json({"ok": True, "messages": ["LLMGarage shutdown requested."]})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                self.send_json({"ok": False, "messages": ["Unknown API endpoint."]}, status=404)
        except RequestError as exc:
            self.send_json({"ok": False, "messages": [str(exc)]}, status=exc.status)
        except Exception as exc:
            add_log(f"API error at {parsed.path}: {exc}")
            self.send_json({"ok": False, "messages": [str(exc)]}, status=400)

    def read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_REQUEST_BODY_BYTES:
            raise RequestError(413, f"Request body exceeds the {MAX_REQUEST_BODY_BYTES}-byte limit.")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def serve_static(self, request_path: str) -> None:
        if request_path in ("", "/"):
            file_path = WEB_DIR / "index.html"
        else:
            relative = request_path.lstrip("/")
            file_path = (WEB_DIR / relative).resolve()
            if WEB_DIR.resolve() not in file_path.parents and file_path != WEB_DIR.resolve():
                self.send_error(403)
                return
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404)
            return
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
        }.get(file_path.suffix.lower(), "application/octet-stream")
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        message = format % args
        if "GET /api/state " in message or "GET /api/logs " in message:
            return
        if "GET / " in message or "GET /app.js " in message or "GET /styles.css " in message:
            return
        add_log("llmgarage: " + message)

def main() -> None:
    ensure_data_files()
    url = f"http://{HOST}:{PORT}"
    write_app_pid()
    add_log(f"LLMGarage listening on {url}")
    print(f"LLMGarage: {url}")
    try:
        ThreadingHTTPServer((HOST, PORT), LLMGarageHandler).serve_forever()
    finally:
        clear_app_pid()


if __name__ == "__main__":
    main()










