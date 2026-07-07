from __future__ import annotations

import ctypes
import json
import os
import shlex
import subprocess
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


class RuntimeState:
    def __init__(self) -> None:
        self.process: subprocess.Popen[str] | None = None
        self.started_at: float | None = None
        self.command: list[str] = []
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
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def add_log(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    with STATE.lock:
        STATE.logs.append(line)
    DATA_DIR.mkdir(exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


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

    add_log("Started llama-server: " + command_preview(argv))
    if process.stdout:
        threading.Thread(target=read_stream, args=(process.stdout, "stdout"), daemon=True).start()
    if process.stderr:
        threading.Thread(target=read_stream, args=(process.stderr, "stderr"), daemon=True).start()
    return {"ok": True, "messages": ["llama-server started."], "status": runtime_status()}


def stop_process() -> dict[str, Any]:
    with STATE.lock:
        process = STATE.process
        if process is None or process.poll() is not None:
            STATE.process = None
            STATE.started_at = None
            STATE.command = []
            return {"ok": True, "messages": ["No LLMGarage-managed process is running."]}
        pid = process.pid
        process.terminate()
    try:
        process.wait(timeout=8)
        add_log(f"Stopped LLMGarage-managed llama-server process PID {pid}.")
    except subprocess.TimeoutExpired:
        process.kill()
        add_log(f"Force killed LLMGarage-managed llama-server process PID {pid}.")
    with STATE.lock:
        STATE.process = None
        STATE.started_at = None
        STATE.command = []
    return {"ok": True, "messages": [f"Stopped process PID {pid}."]}


def kill_all_llama_servers() -> dict[str, Any]:
    if os.name != "nt":
        return {"ok": False, "messages": ["Global stop is only implemented for Windows."]}
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
        if STATE.process is not None and STATE.process.poll() is not None:
            STATE.process = None
            STATE.started_at = None
            STATE.command = []
    return {"ok": result.returncode == 0, "messages": [output or f"taskkill exited {result.returncode}"]}


def request_json(url: str, payload: dict[str, Any] | None = None, timeout: int = 10) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
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
        "temperature": "",
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
    return f"http://{host}:{port}"


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
        payload = self.read_body()
        try:
            if parsed.path == "/api/presets":
                presets = payload.get("presets", [])
                if not isinstance(presets, list):
                    raise ValueError("presets must be a list")
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
        except Exception as exc:
            add_log(f"API error at {parsed.path}: {exc}")
            self.send_json({"ok": False, "messages": [str(exc)]}, status=400)

    def read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
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










