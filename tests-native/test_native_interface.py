"""Integracao Qt real do tema publico com uma UI inteiramente sintetica."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QCoreApplication, QEvent, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton

from synthetic_ui import create_legacy_module


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "jarvis_native_public_test", ROOT / "integracao" / "jarvis_interface_nativa.py"
)
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)


def image_bytes(image):
    return image.constBits().asstring(image.sizeInBytes())


class NativeInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.qt_exceptions = []
        self.exception_hook = patch.object(
            sys, "excepthook", lambda kind, error, traceback: self.qt_exceptions.append(error)
        )
        self.exception_hook.start()
        self.addCleanup(self.exception_hook.stop)
        self.environment = patch.dict(os.environ, {"JARVIS_REDUCED_MOTION": "0"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        # O runner Windows pode desativar animacoes. Os testes controlam essa
        # entrada externa e exercitam a preferencia pelo ambiente/propriedade Qt.
        unavailable_os_preference = SimpleNamespace(
            user32=SimpleNamespace(SystemParametersInfoW=lambda *args: False)
        )
        self.os_animation = patch.object(
            native.ctypes, "windll", unavailable_os_preference, create=True
        )
        self.os_animation.start()
        self.addCleanup(self.os_animation.stop)
        self.app.setProperty("jarvisReducedMotion", False)
        self.addCleanup(lambda: self.app.setProperty("jarvisReducedMotion", None))
        self.windows = []

    def tearDown(self):
        for window in self.windows:
            window.close()
            window.deleteLater()
        self.app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertEqual(self.qt_exceptions, [], "excecao escapou de um callback Qt")

    def make_window(self, *, show=True):
        legacy = create_legacy_module()
        native.instalar(legacy)
        window = legacy.MainWindow()
        self.windows.append(window)
        if show:
            window.show()
            self.app.processEvents()
        return legacy, window

    def render_hud(self, window):
        self.app.processEvents()
        return window.hud.grab().toImage()

    def test_installation_is_idempotent_and_preserves_original_facade(self):
        legacy = create_legacy_module()
        original_window, original_hud, original_facade = (
            legacy.MainWindow, legacy.HudCanvas, legacy.JarvisUI
        )
        original_set_state = original_facade.set_state
        self.assertIs(native.instalar(legacy), legacy)
        themed = legacy.MainWindow, legacy.HudCanvas
        self.assertTrue(issubclass(legacy.MainWindow, original_window))
        self.assertTrue(issubclass(legacy.HudCanvas, original_hud))
        self.assertIs(legacy.JarvisUI, original_facade)
        self.assertIs(legacy.JarvisUI.set_state, original_set_state)
        self.assertIs(native.instalar(legacy), legacy)
        self.assertEqual((legacy.MainWindow, legacy.HudCanvas), themed)

    def test_main_import_returns_the_exact_original_facade_from_fake_ui(self):
        legacy = create_legacy_module()
        original_facade = legacy.JarvisUI
        with patch.dict(sys.modules, {"ui": legacy}), patch.dict(os.environ):
            self.assertIs(native.JarvisUI, original_facade)
            first_window = legacy.MainWindow
            self.assertIs(native.JarvisUI, original_facade)
            self.assertIs(legacy.MainWindow, first_window)
            self.assertEqual(os.environ["JARVIS_INTERFACE_MODE"], "native")
        with self.assertRaises(AttributeError):
            getattr(native, "not_a_public_export")

    def test_state_labels_cover_normal_processing_response_and_failures(self):
        expected = {
            "LISTENING": "Pronto para ouvir", "PROCESSING": "Processando",
            "THINKING": "Processando", "SPEAKING": "Respondendo",
            "RESPONDING": "Respondendo", "MUTED": "Microfone pausado",
            "IDLE": "Em repouso", "SLEEPING": "Em repouso", "ASLEEP": "Em repouso",
            "ERROR": "Erro na conexão", "FAILED": "Erro na conexão",
            "DISCONNECTED": "Desconectado", "RECONNECTING": "Conectando",
            "CONNECTING": "Conectando", "INITIALISING": "Conectando",
            "INITIALIZING": "Conectando", "CUSTOM": "Em espera",
        }
        for state, label in expected.items():
            with self.subTest(state=state):
                self.assertEqual(native.state_details(state.lower())[0], label)
        self.assertEqual(native.state_details("LISTENING", speaking=True)[0], "Respondendo")
        self.assertEqual(native.state_details("SPEAKING", muted=True)[0], "Microfone pausado")

    def test_real_reactor_rendering_changes_with_assistant_state(self):
        _, window = self.make_window()
        window.hud._tmr.stop()
        images = []
        for state in ("LISTENING", "PROCESSING", "ERROR"):
            window.sig.state.emit(state)
            image = self.render_hud(window)
            self.assertFalse(image.isNull())
            self.assertEqual(image.size(), window.hud.size())
            self.assertLess(image.pixelColor(0, 0).lightness(), 30)
            colors = {image.pixelColor(x, y).rgb()
                      for x in range(0, image.width(), 9)
                      for y in range(0, image.height(), 9)}
            self.assertGreater(len(colors), 40, "reator deve conter luz e aneis pintados")
            images.append(image_bytes(image))
        self.assertEqual(len(set(images)), 3)
        self.assertEqual(window.hud.original_paints, 0)

    def test_resizing_keeps_microphone_inside_the_real_hud(self):
        _, window = self.make_window()
        for width, height in ((820, 580), (1040, 720), (1240, 800)):
            with self.subTest(size=(width, height)):
                window.resize(width, height)
                image = self.render_hud(window)
                microphone = window.hud.findChild(QPushButton, "native-microphone")
                self.assertTrue(microphone.isVisible())
                self.assertTrue(window.hud.rect().contains(microphone.geometry()))
                self.assertAlmostEqual(microphone.geometry().center().x(), image.width() / 2, delta=2)
                self.assertGreater(microphone.geometry().top(), 0)

    def test_both_microphone_controls_call_the_original_mute_handler(self):
        _, window = self.make_window()
        microphone = window.hud.findChild(QPushButton, "native-microphone")
        self.assertEqual(microphone.accessibleName(), "Silenciar microfone")
        QTest.mouseClick(microphone, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertEqual(window.calls, [("mute", True)])
        self.assertTrue(window._muted)
        self.assertTrue(window.hud.muted)
        self.assertEqual(microphone.accessibleName(), "Ativar microfone")
        self.assertEqual(window._mute_btn.text(), "Reativar microfone")
        self.assertIn("#ff7e9a", window._mute_btn.styleSheet())
        QTest.mouseClick(window._mute_btn, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertEqual(window.calls, [("mute", True), ("mute", False)])
        self.assertFalse(window._muted)
        self.assertEqual(microphone.accessibleName(), "Silenciar microfone")
        self.assertEqual(window._mute_btn.text(), "Silenciar microfone")
        QTest.mouseClick(window._interrupt_btn, Qt.MouseButton.LeftButton)
        self.assertEqual(window.calls[-1], ("interrupt",))

    def test_avatar_toggle_uses_original_painter_and_restores_reactor(self):
        _, window = self.make_window()
        microphone = window.hud.findChild(QPushButton, "native-microphone")
        window._hud_btn.click()
        avatar = self.render_hud(window)
        self.assertEqual(window.hud.hud_style, "face")
        self.assertFalse(microphone.isVisible())
        self.assertGreater(window.hud.original_paints, 0)
        self.assertEqual(avatar.pixelColor(0, 0).name(), "#15563a")
        self.assertIn("avatar", window._hud_btn.text())
        window._hud_btn.click()
        reactor = self.render_hud(window)
        self.assertEqual(window.hud.hud_style, "core")
        self.assertTrue(microphone.isVisible())
        self.assertNotEqual(image_bytes(avatar), image_bytes(reactor))
        self.assertIn("reator LED", window._hud_btn.text())

    def test_agents_and_existing_drawer_buttons_reach_original_actions_once(self):
        _, window = self.make_window()
        window._native_agents_btn.click()
        self.assertEqual(self.qt_exceptions, [])
        self.assertEqual(window.calls, [("plugins",)])
        window._drawer_btn.click()
        self.assertTrue(window.drawer.isVisible())
        for method_name, title in (
            ("_open_customize", "customize"), ("_open_audio_devices", "audio_devices"),
            ("_open_providers", "providers"), ("_open_memory_panel", "memory"),
        ):
            with self.subTest(action=method_name):
                before = len(window.calls)
                window.drawer_buttons[method_name].click()
                self.assertEqual(self.qt_exceptions, [])
                self.assertEqual(window.calls[before:], [(title,)])
                button = window._panels[-1].findChild(QPushButton, "synthetic-apply")
                self.assertIn("QPushButton:hover", button.styleSheet())
                self.assertGreaterEqual(button.minimumHeight(), 30)
                button.click()
                self.assertEqual(window.calls[-1], ("apply", title))

    def test_dynamic_styles_preserve_original_rules_and_do_not_accumulate(self):
        _, window = self.make_window()
        original_prefix = "QPushButton { letter-spacing: 1px; }"
        for _ in range(4):
            window._style_mute_btn()
            window._refresh_hud_btn()
        css = window._mute_btn.styleSheet()
        self.assertTrue(css.startswith(original_prefix))
        self.assertEqual(css.count("QPushButton:hover"), 1)
        self.assertIn("QPushButton:pressed", css)
        self.assertIn("QPushButton:focus", css)
        self.assertIn("QPushButton:disabled", css)
        window._ctrl_btn.click()
        self.assertTrue(window.voice_controls.isVisible())
        window._wake_btn.click()
        window._talk_btn.click()
        self.assertEqual(self.qt_exceptions, [])
        self.assertEqual(window.calls[-2:], [("wake", True), ("talk", True)])
        self.assertIn("QPushButton:hover", window._wake_btn.styleSheet())
        self.assertIn("QPushButton:checked", window._talk_btn.styleSheet())
        window._talk_btn.setDisabled(True)
        window._talk_btn.click()
        self.assertEqual(window.calls[-1], ("talk", True))

    def test_wrapped_methods_keep_arguments_keywords_and_return_values(self):
        _, window = self.make_window()
        self.assertEqual(window._open_plugin_settings("demo", enabled=False), ("demo", False))
        self.assertEqual(window.calls[-1], ("plugin_settings", "demo", False))
        panel = window._open_providers()
        self.assertIs(panel, window._panels[-1])
        self.assertIn("QPushButton:hover", panel.findChild(QPushButton).styleSheet())

    def test_original_signal_bridge_delivers_worker_updates_on_the_qt_thread(self):
        legacy = create_legacy_module()
        facade_type = legacy.JarvisUI
        native.instalar(legacy)
        facade = facade_type()
        window = facade.window
        self.windows.append(window)
        original_sig = facade.sig
        self.assertIs(window.sig, original_sig)
        failures = []

        def worker():
            try:
                facade.set_state("PROCESSING")
                facade.set_amplitude(.72)
                facade.set_speaking(True)
            except Exception as error:
                failures.append(error)

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(window.delivery_threads, [], "entrega deve aguardar o event loop Qt")
        self.app.processEvents()
        self.assertEqual(window.hud.state, "PROCESSING")
        self.assertAlmostEqual(window.hud._amp_disp, .72)
        self.assertTrue(window.hud.speaking)
        self.assertEqual(len(window.delivery_threads), 3)
        self.assertTrue(all(thread is self.app.thread() for thread in window.delivery_threads))
        self.assertIs(facade.sig, original_sig)

    def test_original_animation_timer_pauses_hidden_and_minimized_then_resumes(self):
        _, window = self.make_window(show=False)
        timer = window.hud._tmr
        self.assertFalse(timer.isActive())
        window.show()
        self.app.processEvents()
        self.assertTrue(timer.isActive())
        self.assertLessEqual(timer.interval(), 50)
        steps = window.hud.original_steps
        QTest.qWait(90)
        self.assertGreater(window.hud.original_steps, steps)
        window.hide()
        self.app.processEvents()
        self.assertFalse(timer.isActive())
        steps = window.hud.original_steps
        QTest.qWait(70)
        self.assertEqual(window.hud.original_steps, steps)
        window.show()
        self.app.processEvents()
        self.assertTrue(timer.isActive())
        window.showMinimized()
        self.app.processEvents()
        self.assertFalse(timer.isActive())
        window.showNormal()
        self.app.processEvents()
        self.assertTrue(timer.isActive())

    def test_reduced_motion_has_a_slower_timer_and_static_rendering(self):
        os.environ["JARVIS_REDUCED_MOTION"] = "true"
        _, window = self.make_window()
        self.assertTrue(window.hud._tmr.isActive())
        self.assertGreaterEqual(window.hud._tmr.interval(), 100)
        window.hud._tmr.stop()
        before = self.render_hud(window)
        window.hud._core_phase += 4
        window.hud._amp_disp = .95
        after = self.render_hud(window)
        self.assertEqual(image_bytes(before), image_bytes(after))

    def test_normal_motion_reflects_legacy_animation_and_app_can_request_reduction(self):
        _, window = self.make_window()
        window.hud._tmr.stop()
        before = self.render_hud(window)
        window.hud._core_phase += 4
        window.hud._amp_disp = .95
        after = self.render_hud(window)
        self.assertNotEqual(image_bytes(before), image_bytes(after))
        self.app.setProperty("jarvisReducedMotion", True)
        _, reduced = self.make_window()
        self.assertGreaterEqual(reduced.hud._tmr.interval(), 100)


if __name__ == "__main__":
    unittest.main()
