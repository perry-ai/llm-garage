import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import app


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




