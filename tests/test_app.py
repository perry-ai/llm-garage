import http.client
import json
import os
import socket
import shutil
import subprocess
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from contextlib import contextmanager, nullcontext
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import app


@contextmanager
def running_http_server(*, enable_logs=False):
    log_context = nullcontext() if enable_logs else patch("app.add_log")
    with log_context:
        server = ThreadingHTTPServer(("127.0.0.1", 0), app.LLMGarageHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


def post_json(url, payload, *, origin=None):
    headers = {"Content-Type": "application/json"}
    if origin is not None:
        headers["Origin"] = origin
    return post_raw(url, json.dumps(payload).encode("utf-8"), headers=headers)


def post_raw(url, data, *, headers=None):
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers or {},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def post_with_declared_length(url, length):
    parsed = urllib.parse.urlparse(url)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=2)
    try:
        connection.putrequest("POST", parsed.path)
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", str(length))
        connection.endheaders()
        response = connection.getresponse()
        return response.status, json.loads(response.read().decode("utf-8"))
    finally:
        connection.close()


def get_json(url):
    with urllib.request.urlopen(url, timeout=2) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


class HardwareApiTests(unittest.TestCase):
    def test_console_links_to_advisor_without_embedding_advisor_regions(self):
        with running_http_server() as base:
            with urllib.request.urlopen(base + "/", timeout=2) as response:
                html = response.read().decode("utf-8")

        self.assertIn('href="/advisor"', html)
        self.assertNotIn('id="hardwareSummary"', html)
        self.assertNotIn('id="recommendationModels"', html)
        self.assertNotIn('id="recommendationRules"', html)
        self.assertNotIn('id="learningTopics"', html)

    def test_advisor_page_exposes_hardware_recommendation_and_learning_regions(self):
        with running_http_server() as base:
            with urllib.request.urlopen(base + "/advisor", timeout=2) as response:
                html = response.read().decode("utf-8")

        self.assertIn('id="hardwareSummary"', html)
        self.assertIn('id="recommendationModels"', html)
        self.assertIn('id="recommendationRules"', html)
        self.assertIn('id="learningTopics"', html)
        self.assertIn('id="refreshRecommendationsBtn"', html)
        self.assertIn('src="/advisor.js"', html)
        self.assertNotIn('src="/app.js"', html)

    def test_app_metadata_advertises_advisor_capability(self):
        with running_http_server() as base:
            status, payload = get_json(base + "/api/app")

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["name"], "LLMGarage")
        self.assertEqual(payload["pid"], os.getpid())
        self.assertIn("advisor", payload["capabilities"])
        self.assertIn("hardware-recommendations", payload["capabilities"])

    def test_hardware_report_is_available_over_http(self):
        with running_http_server() as base:
            status, payload = get_json(base + "/api/hardware")

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertIn(payload["recommendationPath"], {"nvidia", "cpu"})
        self.assertIn("physicalCores", payload["cpu"])
        self.assertIn("logicalThreads", payload["cpu"])
        self.assertIn("ramTotalGiB", payload["memory"])
        self.assertIn("available", payload["nvidiaSmi"])

    def test_recommendations_api_combines_hardware_models_and_learning(self):
        with running_http_server() as base:
            status, payload = get_json(base + "/api/recommendations")

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertIn("recommendationPath", payload["hardware"])
        self.assertGreaterEqual(len(payload["models"]), 5)
        self.assertLessEqual(len(payload["models"]), 8)
        self.assertGreaterEqual(len(payload["learning"]), 10)
        self.assertEqual(
            payload["assumptions"]["rulesVersion"],
            "p1-2026-07-31",
        )


class AppStartupTests(unittest.TestCase):
    def test_replace_hands_running_port_to_new_app_process(self):
        data_directory = TemporaryDirectory()
        environment = os.environ.copy()
        environment["LLMGARAGE_DATA_DIR"] = data_directory.name
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]

        command = [sys.executable, str(Path(app.__file__).resolve()), "--port", str(port)]
        first = subprocess.Popen(
            command,
            cwd=Path(app.__file__).resolve().parent,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=environment,
        )
        second = None
        try:
            first_metadata = self.wait_for_app(port)
            self.assertIn("hardware-recommendations", first_metadata["capabilities"])
            first_app_pid = first_metadata["pid"]

            second = subprocess.Popen(
                [*command, "--replace"],
                cwd=Path(app.__file__).resolve().parent,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=environment,
            )

            second_metadata = self.wait_for_app(port, replaced_pid=first_app_pid)
            self.assertNotEqual(second_metadata["pid"], first_app_pid)
            first.wait(timeout=4)
            status, recommendations = get_json(
                f"http://127.0.0.1:{port}/api/recommendations"
            )
            self.assertEqual(status, 200)
            self.assertTrue(recommendations["ok"])
        finally:
            try:
                post_raw(
                    f"http://127.0.0.1:{port}/api/shutdown",
                    b"{}",
                    headers={"Content-Type": "application/json"},
                )
            except (OSError, urllib.error.URLError):
                pass
            for process in (second, first):
                if process is None:
                    continue
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            data_directory.cleanup()

    @unittest.skipUnless(os.name == "nt", "Legacy process replacement uses Windows taskkill.")
    def test_replace_recovers_when_legacy_shutdown_does_not_release_port(self):
        legacy_source = r"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class LegacyHandler(BaseHTTPRequestHandler):
    server_version = "LLMGarage/0.1"

    def send_payload(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.send_payload(404, {"ok": False, "messages": ["Unknown API endpoint."]})

    def do_POST(self):
        if self.path == "/api/shutdown":
            self.send_payload(200, {"ok": True})
        else:
            self.send_payload(404, {"ok": False})

    def log_message(self, *_):
        pass

ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), LegacyHandler).serve_forever()
"""
        data_directory = TemporaryDirectory()
        environment = os.environ.copy()
        environment["LLMGARAGE_DATA_DIR"] = data_directory.name
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]

        legacy = subprocess.Popen(
            [sys.executable, "-c", legacy_source, str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        replacement = None
        try:
            self.wait_for_listener(port)
            replacement = subprocess.Popen(
                [
                    sys.executable,
                    str(Path(app.__file__).resolve()),
                    "--port",
                    str(port),
                    "--replace",
                ],
                cwd=Path(app.__file__).resolve().parent,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=environment,
            )

            metadata = self.wait_for_app(port, replaced_pid=-1, timeout=8)
            self.assertIn("hardware-recommendations", metadata["capabilities"])
            legacy.wait(timeout=4)
        finally:
            try:
                post_raw(
                    f"http://127.0.0.1:{port}/api/shutdown",
                    b"{}",
                    headers={"Content-Type": "application/json"},
                )
            except (OSError, urllib.error.URLError):
                pass
            for process in (replacement, legacy):
                if process is None:
                    continue
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        check=False,
                        capture_output=True,
                    )
                    process.wait(timeout=3)
            data_directory.cleanup()

    def wait_for_listener(self, port):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.05)
        self.fail(f"No process listened on port {port}.")

    def wait_for_app(self, port, *, replaced_pid=None, timeout=5):
        deadline = time.monotonic() + timeout
        last_error = None
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    pass
                _, payload = get_json(f"http://127.0.0.1:{port}/api/app")
                if replaced_pid is None or payload.get("pid") != replaced_pid:
                    return payload
            except urllib.error.HTTPError as exc:
                last_error = exc
                exc.close()
            except (OSError, urllib.error.URLError) as exc:
                last_error = exc
            time.sleep(0.05)
        self.fail(
            f"LLMGarage did not claim port {port} after replacing PID {replaced_pid}: {last_error}"
        )


class HttpSecurityTests(unittest.TestCase):
    def test_cross_origin_post_is_rejected(self):
        with TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            with patch("app.PRESETS_FILE", presets_file), running_http_server() as base:
                status, payload = post_json(
                    base + "/api/presets",
                    {"presets": [app.DEFAULT_PRESET]},
                    origin="https://attacker.example",
                )

        self.assertEqual(status, 403)
        self.assertFalse(payload["ok"])
        self.assertFalse(presets_file.exists())

    def test_malformed_origin_is_rejected(self):
        with running_http_server() as base:
            status, payload = post_json(
                base + "/api/validate",
                {},
                origin="http://localhost:not-a-port",
            )

        self.assertEqual(status, 403)
        self.assertFalse(payload["ok"])

    def test_different_loopback_origin_is_rejected(self):
        with running_http_server() as base:
            status, payload = post_json(
                base + "/api/validate",
                {},
                origin=base.replace("127.0.0.1", "localhost"),
            )

        self.assertEqual(status, 403)
        self.assertFalse(payload["ok"])

    def test_oversized_request_body_is_rejected(self):
        with running_http_server() as base:
            status, payload = post_with_declared_length(
                base + "/api/validate",
                1024 * 1024 + 1,
            )

        self.assertEqual(status, 413)
        self.assertFalse(payload["ok"])

    def test_health_check_rejects_non_loopback_target(self):
        with patch("app.request_json", side_effect=AssertionError("network request attempted")):
            with running_http_server() as base:
                status, payload = post_json(
                    base + "/api/health",
                    {"host": "192.168.1.20", "port": 8080},
                )

        self.assertEqual(status, 400)
        self.assertIn("local", payload["messages"][0].lower())

    def test_malformed_json_returns_json_error(self):
        with running_http_server() as base:
            status, payload = post_raw(
                base + "/api/validate",
                b"{",
                headers={"Content-Type": "application/json"},
            )

        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])


class RequestProxyTests(unittest.TestCase):
    def test_json_request_does_not_follow_redirects(self):
        class RedirectHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", "/target")
                    self.end_headers()
                    return
                body = b'{"followed": true}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaises(urllib.error.HTTPError) as error:
                app.request_json(f"http://127.0.0.1:{server.server_port}/redirect")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(error.exception.code, 302)


class PresetPersistenceTests(unittest.TestCase):
    def test_invalid_preset_does_not_replace_saved_presets(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            presets_file = data_dir / "presets.json"
            log_file = data_dir / "runtime.log"
            original = {"presets": [app.DEFAULT_PRESET]}
            presets_file.write_text(json.dumps(original), encoding="utf-8")
            invalid = {**app.DEFAULT_PRESET, "serverPath": []}

            with (
                patch("app.DATA_DIR", data_dir),
                patch("app.PRESETS_FILE", presets_file),
                patch("app.LOG_FILE", log_file),
                running_http_server() as base,
            ):
                status, payload = post_json(base + "/api/presets", {"presets": [invalid]})
                _, saved = get_json(base + "/api/presets")

        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])
        self.assertEqual(saved, original)

    def test_same_origin_request_saves_valid_presets(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            presets_file = data_dir / "presets.json"
            changed = {**app.DEFAULT_PRESET, "name": "Local model"}
            with (
                patch("app.DATA_DIR", data_dir),
                patch("app.PRESETS_FILE", presets_file),
                patch("app.LOG_FILE", data_dir / "runtime.log"),
                running_http_server() as base,
            ):
                status, payload = post_json(
                    base + "/api/presets",
                    {"presets": [changed]},
                    origin=base,
                )
                _, saved = get_json(base + "/api/presets")

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(saved, {"presets": [changed]})

    def test_fractional_integer_field_is_rejected(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            invalid = {**app.DEFAULT_PRESET, "port": 8080.5}
            with (
                patch("app.DATA_DIR", data_dir),
                patch("app.PRESETS_FILE", data_dir / "presets.json"),
                patch("app.LOG_FILE", data_dir / "runtime.log"),
                running_http_server() as base,
            ):
                status, payload = post_json(base + "/api/presets", {"presets": [invalid]})

        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])

    def test_unknown_preset_metadata_is_preserved(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            extended = {
                **app.DEFAULT_PRESET,
                "recommendation": {"source": "future-hardware-rules"},
            }
            with (
                patch("app.DATA_DIR", data_dir),
                patch("app.PRESETS_FILE", data_dir / "presets.json"),
                patch("app.LOG_FILE", data_dir / "runtime.log"),
                running_http_server() as base,
            ):
                status, payload = post_json(base + "/api/presets", {"presets": [extended]})
                _, saved = get_json(base + "/api/presets")

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(saved["presets"][0]["recommendation"], extended["recommendation"])

    def test_failed_atomic_save_preserves_existing_file(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "presets.json"
            original = {"presets": [app.DEFAULT_PRESET]}
            path.write_text(json.dumps(original), encoding="utf-8")

            with patch("app.os.replace", side_effect=OSError("replace failed")):
                with self.assertRaises(OSError):
                    app.write_json(path, {"presets": [{**app.DEFAULT_PRESET, "name": "Changed"}]})

            saved = json.loads(path.read_text(encoding="utf-8"))
            temporary_files = list(path.parent.glob(f".{path.name}.*.tmp"))

        self.assertEqual(saved, original)
        self.assertEqual(temporary_files, [])


@unittest.skipUnless(os.name == "nt", "Windows process lifecycle test")
class ProcessLifecycleTests(unittest.TestCase):
    def test_exited_process_reports_return_code(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            server_path = data_dir / "llama-server.exe"
            model_path = data_dir / "model.gguf"
            shutil.copy2(Path(os.environ["SystemRoot"]) / "System32" / "where.exe", server_path)
            model_path.touch()
            preset = {
                **app.DEFAULT_PRESET,
                "serverPath": str(server_path),
                "modelPath": str(model_path),
            }

            with (
                patch("app.STATE", app.RuntimeState()),
                patch("app.DATA_DIR", data_dir),
                patch("app.LOG_FILE", data_dir / "runtime.log"),
                running_http_server(enable_logs=True) as base,
            ):
                start_status, start_payload = post_json(base + "/api/start", {"preset": preset})
                deadline = time.time() + 3
                state = {}
                log_text = ""
                while time.time() < deadline:
                    _, state = get_json(base + "/api/state")
                    log_path = data_dir / "runtime.log"
                    log_text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
                    if state.get("lastExitCode") is not None and "exited with code" in log_text.lower():
                        break
                    time.sleep(0.05)

        self.assertEqual(start_status, 200)
        self.assertTrue(start_payload["ok"])
        self.assertFalse(state["running"])
        self.assertIsInstance(state.get("lastExitCode"), int)
        self.assertEqual(state.get("lastExitReason"), "unexpected")
        self.assertIn("exited with code", log_text.lower())

    def test_kill_all_preserves_managed_process_exit_code(self):
        ping_exe = Path(os.environ["SystemRoot"]) / "System32" / "ping.exe"
        process = subprocess.Popen(
            [str(ping_exe), "-n", "30", "127.0.0.1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        state = app.RuntimeState()
        state.process = process
        state.started_at = time.time()

        def terminate_managed_process(command, **kwargs):
            process.terminate()
            process.wait(timeout=2)
            return subprocess.CompletedProcess(
                command,
                returncode=0,
                stdout="SUCCESS",
                stderr="",
            )

        try:
            with (
                patch("app.STATE", state),
                patch("app.subprocess.run", side_effect=terminate_managed_process),
                patch("app.add_log"),
            ):
                result = app.kill_all_llama_servers()
                status = app.runtime_status()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)

        self.assertTrue(result["ok"])
        self.assertEqual(status["lastExitCode"], process.returncode)
        self.assertEqual(status["lastExitReason"], "killed")


class BuildArgvTests(unittest.TestCase):
    def test_builds_structured_and_advanced_args(self):
        preset = {
            "serverPath": r"C:\llama\llama-server.exe",
            "modelPath": r"D:\models\model.gguf",
            "host": "127.0.0.1",
            "port": 8080,
            "ctxSize": 8192,
            "gpuLayers": 35,
            "threads": 8,
            "batchSize": 1024,
            "ubatchSize": 256,
            "parallel": 2,
            "temperature": 0.7,
            "topP": 0.9,
            "embedding": True,
            "reranking": False,
            "advancedArgs": "--alias local-qwen",
        }
        with patch("app.parse_extra_args", return_value=["--alias", "local-qwen"]):
            argv = app.build_argv(preset)

        self.assertEqual(argv[0], r"C:\llama\llama-server.exe")
        self.assertIn("--model", argv)
        self.assertIn(r"D:\models\model.gguf", argv)
        self.assertIn("--ctx-size", argv)
        self.assertIn("8192", argv)
        self.assertIn("--embedding", argv)
        self.assertEqual(argv[-2:], ["--alias", "local-qwen"])

    def test_auto_values_are_omitted_from_argv(self):
        preset = {
            "serverPath": r"C:\llama\llama-server.exe",
            "modelPath": r"D:\models\model.gguf",
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
            "advancedArgs": "",
        }

        argv = app.build_argv(preset)

        self.assertNotIn("--gpu-layers", argv)
        self.assertNotIn("--threads", argv)
        self.assertNotIn("--batch-size", argv)
        self.assertNotIn("--ubatch-size", argv)
        self.assertNotIn("--parallel", argv)
        self.assertNotIn("--temp", argv)
        self.assertNotIn("--top-p", argv)
    def test_requires_paths(self):
        with self.assertRaises(ValueError):
            app.build_argv({"serverPath": "", "modelPath": ""})


class PromptApiTests(unittest.TestCase):
    def test_chat_completion_uses_numeric_temperature(self):
        with patch("app.request_json", return_value={"status": 200, "body": {}}) as request:
            result = app.api_test_prompt(
                {"host": "127.0.0.1", "port": 8080, "prompt": "Hello"}
            )

        sent_payload = request.call_args.args[1]
        self.assertTrue(result["ok"])
        self.assertEqual(sent_payload["temperature"], 0.2)


class ValidationTests(unittest.TestCase):
    def test_validation_accepts_existing_exe_and_gguf(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            server = root / "llama-server.exe"
            model = root / "model.gguf"
            server.write_text("", encoding="utf-8")
            model.write_text("", encoding="utf-8")

            result = app.validate_preset(
                {
                    "serverPath": str(server),
                    "modelPath": str(model),
                    "host": "127.0.0.1",
                    "port": 8080,
                }
            )

        self.assertTrue(result["ok"], result["messages"])

    def test_validation_rejects_bad_port(self):
        result = app.validate_preset(
            {
                "serverPath": r"C:\missing\llama-server.exe",
                "modelPath": r"C:\missing\model.gguf",
                "port": 70000,
            }
        )
        self.assertFalse(result["ok"])
        self.assertTrue(any("port" in message for message in result["messages"]))



class LLMGarageLogTests(unittest.TestCase):
    def test_routine_app_polling_does_not_enter_runtime_log(self):
        handler = object.__new__(app.LLMGarageHandler)

        with patch("app.add_log") as add_log:
            handler.log_message('"%s" %s -', "GET /api/state HTTP/1.1", "200")
            handler.log_message('"%s" %s -', "GET /api/logs HTTP/1.1", "200")

        add_log.assert_not_called()

    def test_runtime_log_rotates_when_size_limit_is_reached(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            log_file = data_dir / "runtime.log"
            rotated_file = data_dir / "runtime.1.log"
            with (
                patch("app.DATA_DIR", data_dir),
                patch("app.LOG_FILE", log_file),
                patch("app.MAX_LOG_FILE_BYTES", 160, create=True),
                patch("app.MAX_LOG_BACKUPS", 2, create=True),
            ):
                for number in range(8):
                    app.add_log(f"message {number}: " + "x" * 32)

            current_text = log_file.read_text(encoding="utf-8")
            rotated_text = rotated_file.read_text(encoding="utf-8")

        self.assertIn("message 7", current_text)
        self.assertIn("message 5", rotated_text)

    def test_single_log_line_is_truncated_to_size_limit(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            log_file = data_dir / "runtime.log"
            with (
                patch("app.DATA_DIR", data_dir),
                patch("app.LOG_FILE", log_file),
                patch("app.MAX_LOG_FILE_BYTES", 160),
            ):
                app.add_log("x" * 1024)

            size = log_file.stat().st_size
            log_text = log_file.read_text(encoding="utf-8")

        self.assertLessEqual(size, 160)
        self.assertIn("[truncated]", log_text)


class LLMGaragePidTests(unittest.TestCase):
    def test_app_pid_file_lifecycle(self):
        with TemporaryDirectory() as temp_dir:
            pid_file = Path(temp_dir) / "llmgarage.pid"
            with patch("app.DATA_DIR", Path(temp_dir)), patch("app.PID_FILE", pid_file):
                app.write_app_pid()
                self.assertEqual(pid_file.read_text(encoding="ascii"), str(app.os.getpid()))
                app.clear_app_pid()
                self.assertFalse(pid_file.exists())

    def test_clear_app_pid_keeps_foreign_pid(self):
        with TemporaryDirectory() as temp_dir:
            pid_file = Path(temp_dir) / "llmgarage.pid"
            pid_file.write_text("999999", encoding="ascii")
            with patch("app.PID_FILE", pid_file):
                app.clear_app_pid()
                self.assertTrue(pid_file.exists())

if __name__ == "__main__":
    unittest.main()




