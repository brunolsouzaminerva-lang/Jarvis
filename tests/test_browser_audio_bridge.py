"""Ponte de audio em memoria: sem microfone, main.py ou servicos externos."""
import asyncio
import importlib.util
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


PATH = Path(__file__).resolve().parents[1] / "integracao" / "browser_audio_bridge.py"
SPEC = importlib.util.spec_from_file_location("jarvis_bridge", PATH)
bridge_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge_module)
ORIGIN = bridge_module.ORIGIN


def frame(values):
    return np.asarray(values, dtype="<f4").tobytes()


class InterfaceWindowTests(unittest.TestCase):
    def test_native_mode_opens_only_the_microphone_companion(self):
        with tempfile.TemporaryDirectory(prefix="jarvis-native-window-synthetic-") as folder:
            edge = Path(folder) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            edge.parent.mkdir(parents=True)
            edge.write_text("SYNTHETIC - DO NOT EXECUTE", encoding="utf-8")
            with patch.object(bridge_module.sys, "platform", "win32"), \
                    patch.dict(bridge_module.os.environ, {
                        "JARVIS_INTERFACE_MODE": "native", "PROGRAMFILES": folder,
                    }, clear=True), \
                    patch.object(bridge_module.webbrowser, "open") as browser, \
                    patch.object(bridge_module.subprocess, "Popen") as process:
                bridge_module._open_interface()
            process.assert_called_once_with(
                [str(edge), f"--app={ORIGIN}/microfone", "--window-size=520,660"], close_fds=True)
            browser.assert_not_called()

    def test_normal_start_uses_the_existing_default_browser(self):
        with patch.dict(bridge_module.os.environ, {}, clear=True), \
                patch.object(bridge_module.webbrowser, "open") as browser, \
                patch.object(bridge_module.subprocess, "Popen") as process:
            bridge_module._open_interface()
        browser.assert_called_once_with(ORIGIN)
        process.assert_not_called()

    def test_desktop_mode_opens_edge_app_window_with_argument_list(self):
        with tempfile.TemporaryDirectory(prefix="jarvis-window-synthetic-") as folder:
            root = Path(folder) / "Programs with spaces & symbols"
            edge = root / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            edge.parent.mkdir(parents=True)
            edge.write_text("SYNTHETIC EXECUTABLE - DO NOT RUN", encoding="utf-8")
            with patch.object(bridge_module.sys, "platform", "win32"), \
                    patch.dict(bridge_module.os.environ, {
                        "JARVIS_INTERFACE_MODE": "app", "PROGRAMFILES": str(root),
                    }, clear=True), \
                    patch.object(bridge_module.webbrowser, "open") as browser, \
                    patch.object(bridge_module.subprocess, "Popen") as process:
                bridge_module._open_interface()
            process.assert_called_once_with([str(edge), f"--app={ORIGIN}"], close_fds=True)
            browser.assert_not_called()

    def test_unavailable_edge_uses_default_browser_without_new_dependency(self):
        with patch.object(bridge_module.sys, "platform", "win32"), \
                patch.dict(bridge_module.os.environ, {"JARVIS_INTERFACE_MODE": "app"}, clear=True), \
                patch.object(bridge_module.webbrowser, "open") as browser, \
                patch.object(bridge_module.subprocess, "Popen") as process:
            bridge_module._open_interface()
        browser.assert_called_once_with(ORIGIN)
        process.assert_not_called()


class AudioConversionTests(unittest.TestCase):
    def test_pcm_values_are_little_endian_and_clipped(self):
        converter = bridge_module.PCMConverter()
        result = converter.feed(frame([1, 1, 1, -1, -1, -1, 2, 2, 2, -2, -2, -2]))
        np.testing.assert_array_equal(np.frombuffer(result, dtype="<i2"), [32767, -32767, 32767, -32768])

    def test_arbitrary_message_boundaries_preserve_all_samples(self):
        values = np.linspace(-0.9, 0.9, 48000, dtype=np.float32)
        whole = np.rint(values.reshape(-1, 3).mean(axis=1, dtype=np.float64) * 32767).astype("<i2").tobytes()
        converter = bridge_module.PCMConverter()
        chunks = [values[i:i + 4096] for i in range(0, len(values), 4096)]
        separate = b"".join(converter.feed(chunk.astype("<f4").tobytes()) for chunk in chunks)
        self.assertEqual(separate, whole)
        self.assertEqual(len(separate), 16000 * 2)

    def test_rejects_malformed_nonfinite_and_oversized_frames(self):
        for raw in [b"x", frame([float("nan")]), frame([float("inf")]),
                    bytes(bridge_module.MAX_FRAME_BYTES + 4)]:
            with self.subTest(length=len(raw)):
                with self.assertRaises(ValueError):
                    bridge_module.PCMConverter().feed(raw)


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jarvis-bridge-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in bridge_module.ASSETS:
            (self.root / name).write_text("<html><body>JARVIS</body></html>" if name == "index.html" else "/* synthetic */", encoding="utf-8")
        self.received = []
        self.delivery = threading.Event()
        self.muted = False

        def receive(data):
            self.received.append(data)
            self.delivery.set()

        self.bridge = bridge_module.BrowserAudioBridge(
            receive, lambda: self.muted, ui_root=self.root)
        self.client = TestClient(self.bridge.app, base_url=ORIGIN)
        self.addCleanup(self.client.close)

    def connect(self, origin=ORIGIN):
        return self.client.websocket_connect(ORIGIN.replace("http://", "ws://") + "/jarvis-audio", headers={"Origin": origin})

    def test_home_injects_only_local_voice_module_and_assets_are_allowlisted(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('<script type="module" src="/voice.js"></script>', response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.client.get("/voice.js").status_code, 200)
        (self.root / ".env").write_text("SYNTHETIC_ONLY=example")
        (self.root / "main.py").write_text("raise AssertionError('must not execute')")
        for url in ["/.env", "/main.py", "/config/api_keys.json", "/docs", "/openapi.json", "/../main.py"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
        self.assertIn('/voice.js', self.client.get('/index.html').text)

    def test_missing_assets_fail_closed(self):
        (self.root / "voice.js").unlink()
        self.assertEqual(self.client.get("/").status_code, 503)
        self.assertEqual(self.client.get("/microfone").status_code, 503)

    def test_native_microphone_page_uses_shared_capture_without_full_app(self):
        response = self.client.get("/microfone")
        self.assertEqual(response.status_code, 200)
        self.assertIn('src="/voice.js"', response.text)
        self.assertIn('id="voice-status"', response.text)
        self.assertIn('class="mic-action"', response.text)
        self.assertIn('data-voice-start', response.text)
        self.assertNotIn('src="app.js"', response.text)
        self.assertNotIn('src="/app.js"', response.text)
        self.assertNotIn('getUserMedia(', response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_symlink_asset_cannot_serve_files_outside_the_interface(self):
        outside = self.root / "synthetic-secret.txt"
        outside.write_text("SYNTHETIC_ONLY=example")
        asset = self.root / "core.js"
        asset.unlink()
        try:
            asset.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Criacao de links nao disponivel neste sistema")
        self.assertEqual(self.client.get("/core.js").status_code, 404)
        self.assertEqual(self.client.get("/").status_code, 503)

    def test_rebinding_host_and_foreign_origins_are_refused(self):
        self.assertEqual(self.client.get("/", headers={"Host": "attacker.example:8765"}).status_code, 400)
        for origin in ["https://attacker.example", "null", "http://127.0.0.1:8790", "http://localhost:8765"]:
            with self.subTest(origin=origin):
                with self.assertRaises(WebSocketDisconnect) as error:
                    with self.connect(origin):
                        pass
                self.assertEqual(error.exception.code, 1008)
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect(ORIGIN.replace("http://", "ws://") + "/jarvis-audio"):
                pass
        self.assertEqual(self.received, [])

    def test_binary_audio_delivered_once_and_disconnect_clears_status(self):
        with self.connect() as ws:
            self.assertEqual(ws.receive_json(), {"type": "ready", "muted": False})
            ws.send_bytes(frame([0.25] * 6))
            self.assertTrue(self.delivery.wait(1))
            self.assertTrue(self.client.get("/bridge-status").json()["connected"])
        self.assertFalse(self.client.get("/bridge-status").json()["connected"])
        self.assertEqual(len(self.received), 1)
        np.testing.assert_array_equal(np.frombuffer(self.received[0], dtype="<i2"), [8192, 8192])

    def test_muted_audio_is_discarded_and_state_change_is_reported(self):
        self.muted = True
        with self.connect() as ws:
            self.assertEqual(ws.receive_json(), {"type": "ready", "muted": True})
            ws.send_bytes(frame([1] * 3))
            self.assertFalse(self.delivery.wait(0.05))
            self.assertTrue(self.client.get("/bridge-status").json()["muted"])
            self.muted = False
            # O servidor deve notificar sem exigir audio enquanto esta no mudo.
            self.assertEqual(ws.receive_json(), {"type": "muted", "value": False})
            ws.send_bytes(frame([0] * 3))
            self.assertTrue(self.delivery.wait(1))
        self.assertEqual(self.received, [b"\x00\x00"])

    def test_second_client_does_not_replace_or_disconnect_first(self):
        with self.connect() as first:
            first.receive_json()
            with self.assertRaises(WebSocketDisconnect) as error:
                with self.connect():
                    pass
            self.assertEqual(error.exception.code, 1008)
            self.assertTrue(self.client.get("/bridge-status").json()["connected"])
            first.send_bytes(frame([0.5] * 3))
            self.assertTrue(self.delivery.wait(1))
        self.assertEqual(len(self.received), 1)
        with self.connect() as later:
            self.assertEqual(later.receive_json()["type"], "ready")

    def test_bad_audio_closes_without_reaching_callback(self):
        for raw in [b"broken", frame([float("nan")]), bytes(bridge_module.MAX_FRAME_BYTES + 4)]:
            with self.subTest(length=len(raw)):
                with self.connect() as ws:
                    ws.receive_json()
                    ws.send_bytes(raw)
                    with self.assertRaises(WebSocketDisconnect) as error:
                        ws.receive_bytes()
                    self.assertEqual(error.exception.code, 1003)
        self.assertEqual(self.received, [])

    def test_async_callback_uses_the_same_pcm_contract(self):
        async def receive(data):
            await asyncio.sleep(0)
            self.received.append(data)
            self.delivery.set()

        self.bridge.on_pcm16 = receive
        with self.connect() as ws:
            ws.receive_json()
            ws.send_bytes(frame([0.5] * 3))
            self.assertTrue(self.delivery.wait(1))
        self.assertEqual(self.received, [b"\x00\x40"])

    def test_callback_error_does_not_expose_details(self):
        def fail(data):
            raise RuntimeError("SYNTHETIC_PRIVATE_DETAIL")

        self.bridge.on_pcm16 = fail
        with self.connect() as ws:
            ws.receive_json()
            ws.send_bytes(frame([0] * 3))
            error = ws.receive_json()
            self.assertEqual(error["type"], "error")
            self.assertNotIn("SYNTHETIC_PRIVATE_DETAIL", str(error))
            with self.assertRaises(WebSocketDisconnect) as closed:
                ws.receive_bytes()
            self.assertEqual(closed.exception.code, 1011)

    def test_wait_connected_crosses_threads_without_blocking_event_loop(self):
        async def exercise():
            ticks = []

            async def ticker():
                await asyncio.sleep(0.01)
                ticks.append(True)

            timer = threading.Timer(0.03, self.bridge._connected.set)
            timer.start()
            try:
                ready, _ = await asyncio.gather(self.bridge.wait_connected(0.5), ticker())
                self.assertTrue(ready)
                self.assertEqual(ticks, [True])
                self.bridge._connected.clear()
                self.assertFalse(await self.bridge.wait_connected(0.001))
            finally:
                timer.join()

        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
