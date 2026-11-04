"""Contrato visual sintetico para testes/preview, sem importar o Jarvis privado.

Os componentes sao widgets Qt reais. As acoes apenas registram chamadas em
memoria; nenhum arquivo, dispositivo, provedor ou servico e acessado.
"""
from __future__ import annotations

from types import ModuleType

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QTextEdit,
    QVBoxLayout, QWidget,
)


class SignalBridge(QObject):
    state = pyqtSignal(str)
    amplitude = pyqtSignal(float)
    speaking = pyqtSignal(bool)


def create_legacy_module(name: str = "ui") -> ModuleType:
    """Retorna um modulo independente com facade e callbacks legados ficticios."""
    legacy = ModuleType(name)
    legacy.APP_VERSION = "MARK SINTETICO"

    class HudCanvas(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.state = "LISTENING"
            self.muted = False
            self.speaking = False
            self.hud_style = "face"
            self._amp_disp = .35
            self._core_phase = 0.0
            self.original_steps = 0
            self.original_paints = 0
            self.setMinimumSize(280, 330)
            self._tmr = QTimer(self)
            self._tmr.timeout.connect(self._step)
            self._tmr.start(16)

        def _step(self):
            self.original_steps += 1
            self._core_phase += .03
            self.update()

        def paintEvent(self, event):
            self.original_paints += 1
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor("#15563a"))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(20, 35, "AVATAR SINTETICO")
            painter.end()

    class MainWindow(QMainWindow):
        def __init__(self, sig=None):
            super().__init__()
            self.sig = sig if sig is not None else SignalBridge()
            self.calls = []
            self.delivery_threads = []
            self._assistant_name = "Jarvis"
            self._muted = False
            self._drawer_open = False
            self._voice_open = False
            self._panels = []
            central = QWidget(self)
            self.setCentralWidget(central)
            self._layout = QVBoxLayout(central)
            self._layout.setContentsMargins(16, 12, 16, 14)
            self._layout.setSpacing(12)
            self._layout.addWidget(self._build_header())

            content = QHBoxLayout()
            content.setSpacing(20)
            self.hud = legacy.HudCanvas(central)
            content.addWidget(self.hud, 1)
            conversation = QVBoxLayout()
            title = QLabel("CONVERSA · EXEMPLO LOCAL", central)
            title.setStyleSheet("color: #9fdff5; font: 11pt 'Segoe UI';")
            conversation.addWidget(title)
            self.transcript = QTextEdit(central)
            self.transcript.setReadOnly(True)
            self.transcript.setPlainText(
                "VOCE\nJarvis, organize meu dia.\n\n"
                "JARVIS\nTudo pronto. Como posso ajudar?\n\n"
                "Previa com dados sinteticos; nenhuma voz ou API conectada."
            )
            self.transcript.setStyleSheet(
                "background: #07111e; color: #d8effa; border: 1px solid #16364c;"
                "border-radius: 10px; padding: 18px; font: 11pt 'Segoe UI';"
            )
            conversation.addWidget(self.transcript, 1)
            content.addLayout(conversation, 1)
            self._layout.addLayout(content, 1)

            controls = QHBoxLayout()
            self._mute_btn = QPushButton("Mute", central)
            self._mute_btn.setStyleSheet("QPushButton { letter-spacing: 1px; }\n")
            self._mute_btn.clicked.connect(self._toggle_mute)
            self._interrupt_btn = QPushButton("Stop", central)
            self._interrupt_btn.clicked.connect(self._interrupt)
            self._hud_btn = QPushButton("Avatar", central)
            self._hud_btn.clicked.connect(self._toggle_hud_style)
            for button in (self._mute_btn, self._interrupt_btn, self._hud_btn):
                controls.addWidget(button)
            controls.addStretch()
            self._layout.addLayout(controls)

            self.drawer = QFrame(central)
            self.drawer.setObjectName("synthetic-settings-drawer")
            drawer_layout = QHBoxLayout(self.drawer)
            self.drawer_buttons = {}
            for label, method_name in (
                ("Aparencia", "_open_customize"),
                ("Audio", "_open_audio_devices"),
                ("Provedores", "_open_providers"),
                ("Memoria", "_open_memory_panel"),
            ):
                button = QPushButton(label, self.drawer)
                button.clicked.connect(getattr(self, method_name))
                drawer_layout.addWidget(button)
                self.drawer_buttons[method_name] = button
            self._layout.addWidget(self.drawer)
            self.drawer.hide()

            self.voice_controls = QFrame(central)
            voice_layout = QHBoxLayout(self.voice_controls)
            self._wake_btn = QPushButton("Ativacao por voz", self.voice_controls)
            self._wake_btn.setCheckable(True)
            self._wake_btn.clicked.connect(self._refresh_wake_btns)
            self._talk_btn = QPushButton("Conversacao", self.voice_controls)
            self._talk_btn.setCheckable(True)
            self._talk_btn.clicked.connect(self._refresh_talk_btns)
            voice_layout.addWidget(self._wake_btn)
            voice_layout.addWidget(self._talk_btn)
            self._layout.addWidget(self.voice_controls)
            self.voice_controls.hide()
            self.sig.state.connect(self._on_state)
            self.sig.amplitude.connect(self._on_amplitude)
            self.sig.speaking.connect(self._on_speaking)
            self._style_mute_btn()
            self._refresh_hud_btn()
            self.resize(1080, 700)

        def _build_header(self):
            header = QWidget(self)
            layout = QHBoxLayout(header)
            layout.setContentsMargins(12, 2, 12, 2)
            self._title_lbl = QLabel("JARVIS", header)
            self._sub_lbl = QLabel("SINTETICO", header)
            self._version_lbl = QLabel(legacy.APP_VERSION, header)
            self._drawer_btn = QPushButton("⚙", header)
            self._drawer_btn.clicked.connect(self._toggle_drawer)
            self._ctrl_btn = QPushButton("♫", header)
            self._ctrl_btn.clicked.connect(self._toggle_voice_controls)
            for widget in (self._title_lbl, self._sub_lbl, self._version_lbl):
                layout.addWidget(widget)
            layout.addStretch()
            layout.addWidget(self._ctrl_btn)
            layout.addWidget(self._drawer_btn)
            return header

        def _toggle_drawer(self):
            self._drawer_open = not self._drawer_open
            self.drawer.setVisible(self._drawer_open)
            self.calls.append(("drawer", self._drawer_open))

        def _toggle_voice_controls(self):
            self._voice_open = not self._voice_open
            self.voice_controls.setVisible(self._voice_open)
            self.calls.append(("voice_controls", self._voice_open))

        def _toggle_mute(self):
            self._muted = not self._muted
            self.hud.muted = self._muted
            self.calls.append(("mute", self._muted))
            self._style_mute_btn()

        def _style_mute_btn(self):
            self._mute_btn.setText("Muted" if self._muted else "Mute")
            self._mute_btn.setStyleSheet("QPushButton { letter-spacing: 1px; }\n")

        def _interrupt(self):
            self.calls.append(("interrupt",))

        def _refresh_hud_btn(self):
            self._hud_btn.setText(self.hud.hud_style)

        def _toggle_hud_style(self):
            self.hud.hud_style = "core" if self.hud.hud_style == "face" else "face"
            self._refresh_hud_btn()

        def _refresh_wake_btns(self):
            self.calls.append(("wake", self._wake_btn.isChecked()))
            self._wake_btn.setStyleSheet("QPushButton { color: #bbbbbb; }")

        def _refresh_talk_btns(self):
            self.calls.append(("talk", self._talk_btn.isChecked()))
            self._talk_btn.setStyleSheet("QPushButton { color: #bbbbbb; }")

        def _panel(self, title):
            self.calls.append((title,))
            panel = QFrame(self.centralWidget())
            layout = QHBoxLayout(panel)
            layout.addWidget(QLabel(title, panel))
            button = QPushButton("Aplicar", panel)
            button.setObjectName("synthetic-apply")
            button.clicked.connect(lambda: self.calls.append(("apply", title)))
            layout.addWidget(button)
            self._layout.addWidget(panel)
            self._panels.append(panel)
            return panel

        def _open_customize(self):
            return self._panel("customize")

        def _open_audio_devices(self):
            return self._panel("audio_devices")

        def _open_providers(self):
            return self._panel("providers")

        def _open_memory_panel(self):
            return self._panel("memory")

        def _open_plugin_manager(self):
            return self._panel("plugins")

        def _open_plugin_settings(self, plugin_id, *, enabled=True):
            self.calls.append(("plugin_settings", plugin_id, enabled))
            return plugin_id, enabled

        @pyqtSlot(str)
        def _on_state(self, state):
            self.delivery_threads.append(QThread.currentThread())
            self.hud.state = state
            self.hud.update()

        @pyqtSlot(float)
        def _on_amplitude(self, amplitude):
            self.delivery_threads.append(QThread.currentThread())
            self.hud._amp_disp = amplitude
            self.hud.update()

        @pyqtSlot(bool)
        def _on_speaking(self, speaking):
            self.delivery_threads.append(QThread.currentThread())
            self.hud.speaking = speaking
            self.hud.update()

    class JarvisUI:
        def __init__(self):
            self.sig = SignalBridge()
            self.window = legacy.MainWindow(self.sig)

        def set_state(self, state):
            self.sig.state.emit(state)

        def set_amplitude(self, amplitude):
            self.sig.amplitude.emit(amplitude)

        def set_speaking(self, speaking):
            self.sig.speaking.emit(speaking)

    legacy.HudCanvas = HudCanvas
    legacy.MainWindow = MainWindow
    legacy.JarvisUI = JarvisUI
    return legacy
