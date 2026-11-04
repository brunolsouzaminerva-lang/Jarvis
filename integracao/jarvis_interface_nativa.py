"""Tema nativo do Jarvis: nenhuma webview e nenhuma leitura de configuracoes.

O instalador recebe o modulo de UI legado e troca apenas classes visuais em
memoria. O ponto de entrada importa JarvisUI por __getattr__, preservando o
mesmo facade e os mesmos callbacks do aplicativo pessoal.
"""
from __future__ import annotations

import ctypes
import importlib
import inspect
import math
import os

from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QRadialGradient
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton


_MARKER = "/* JARVIS_NATIVE_V1 */"
_INSTALLATION = "_jarvis_native_installation_v1"
BLUE = "#53d9ff"
BACKGROUND = "#030913"
WHITE = "#effbff"


def reduced_motion() -> bool:
    requested = os.environ.get("JARVIS_REDUCED_MOTION", "").lower()
    app = QApplication.instance()
    if requested in {"1", "true", "yes", "on"} or (app and app.property("jarvisReducedMotion") is True):
        return True
    if os.name == "nt":
        try:
            enabled = ctypes.c_int(1)
            # SPI_GETCLIENTAREAANIMATION: consulta, nunca modifica o Windows.
            if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0):
                return not bool(enabled.value)
        except (AttributeError, OSError):
            pass
    return False


def state_details(state: str, muted: bool = False, speaking: bool = False) -> tuple[str, str]:
    """O estado legado descreve o assistente; nao confirma a captura do browser."""
    text = str(state).upper()
    if muted or text == "MUTED":
        return "Microfone pausado", "#ff7e9a"
    if speaking or text in {"SPEAKING", "RESPONDING"}:
        return "Respondendo", "#b7f1ff"
    if text in {"THINKING", "PROCESSING"}:
        return "Processando", "#ffd28d"
    if text in {"ERROR", "FAILED"}:
        return "Erro na conexão", "#ff7e9a"
    if text in {"SLEEPING", "IDLE", "ASLEEP"}:
        return "Em repouso", "#7fabc4"
    if text in {"DISCONNECTED", "RECONNECTING", "CONNECTING", "INITIALISING", "INITIALIZING"}:
        return "Conectando" if text != "DISCONNECTED" else "Desconectado", "#80adca"
    return "Pronto para ouvir" if text == "LISTENING" else "Em espera", BLUE


def _button_css(accent: str = BLUE, danger: bool = False) -> str:
    foreground = "#ffb5c6" if danger else WHITE
    border = "#a33d61" if danger else "#26769c"
    top = "#321727" if danger else "#12354d"
    bottom = "#180d1b" if danger else "#071929"
    return f"""
{_MARKER}
QPushButton {{
  color: {foreground}; background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {top},stop:1 {bottom});
  border: 1px solid {border}; border-top-color: {accent}; border-bottom: 3px solid #020711;
  border-radius: 9px; padding: 5px 9px;
}}
QPushButton:hover {{ color: #ffffff; border-color: {accent}; background: #173f58; }}
QPushButton:pressed {{ padding-top: 7px; padding-bottom: 3px; border-bottom-width: 1px; background: #061522; }}
QPushButton:checked {{ color: #ffffff; background: #17465e; border-color: {accent}; }}
QPushButton:focus {{ border: 2px solid #e6f9ff; }}
QPushButton:disabled {{ color: #6c8297; background: #091420; border-color: #203447; }}
"""


class MicrophoneButton(QPushButton):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("native-microphone")
        self.setFixedSize(58, 58)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName("Silenciar microfone")
        self.setToolTip("Silenciar microfone na janela do Jarvis · F4")
        self._muted = None
        self.set_muted(False)

    def set_muted(self, value: bool):
        value = bool(value)
        if self._muted == value:
            return
        self._muted = value
        color = "#ff7e9a" if value else BLUE
        self.setAccessibleName("Ativar microfone" if value else "Silenciar microfone")
        self.setToolTip(("Ativar" if value else "Silenciar") + " microfone na janela do Jarvis · F4")
        self.setStyleSheet(f"""
QPushButton {{ background: qradialgradient(cx:.5,cy:.35,radius:.8,stop:0 #164764,stop:1 #031021);
border: 2px solid {color}; border-bottom: 4px solid #010710; border-radius: 29px; }}
QPushButton:hover {{ background: #143f59; border-color: #e7fbff; }}
QPushButton:pressed {{ background: #020b15; border-bottom-width: 1px; }}
QPushButton:focus {{ border: 3px solid white; }}
""")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#ffb7c9" if self._muted else WHITE), 2.3,
                            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(24, 12, 10, 23), 5, 5)
        painter.drawArc(QRectF(19, 21, 20, 20), 180 * 16, 180 * 16)
        painter.drawLine(QPointF(29, 41), QPointF(29, 47))
        painter.drawLine(QPointF(23, 47), QPointF(35, 47))
        if self._muted:
            painter.drawLine(QPointF(16, 16), QPointF(43, 43))
        painter.end()


def _modernize_controls(window):
    if getattr(window, "_native_style_busy", False):
        return
    window._native_style_busy = True
    try:
        controls = list(window.findChildren(QPushButton))
        for name in ("_mute_btn", "_interrupt_btn", "_drawer_btn", "_ctrl_btn", "_native_agents_btn"):
            button = getattr(window, name, None)
            if isinstance(button, QPushButton) and button not in controls:
                controls.append(button)
        for button in controls:
            if button.objectName() == "native-microphone":
                continue
            danger = button is getattr(window, "_interrupt_btn", None)
            muted = button is getattr(window, "_mute_btn", None) and bool(getattr(window, "_muted", False))
            original = button.styleSheet().split(_MARKER, 1)[0]
            button.setStyleSheet(original + _button_css("#ff7e9a" if muted or danger else BLUE, muted or danger))
            button.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
            height = 38 if button in (getattr(window, "_mute_btn", None), getattr(window, "_interrupt_btn", None)) else 32
            if button.maximumHeight() < height:
                button.setMaximumHeight(height)
            button.setMinimumHeight(height)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        mute = getattr(window, "_mute_btn", None)
        if isinstance(mute, QPushButton):
            paused = bool(getattr(window, "_muted", False))
            mute.setText("Reativar microfone" if paused else "Silenciar microfone")
            mute.setAccessibleName("Ativar microfone" if paused else "Silenciar microfone")
            mute.setToolTip("Ativar microfone · F4" if paused else "Silenciar microfone · F4")
        interrupt = getattr(window, "_interrupt_btn", None)
        if isinstance(interrupt, QPushButton):
            interrupt.setText("Interromper · Esc")
        for name, tooltip in (("_drawer_btn", "Configurações"), ("_ctrl_btn", "Controles de voz")):
            button = getattr(window, name, None)
            if isinstance(button, QPushButton):
                button.setFixedSize(34, 34)
                button.setAccessibleName(tooltip)
                button.setToolTip(tooltip)
        hud = getattr(window, "hud", None)
        if callable(getattr(hud, "_native_sync_controls", None)):
            hud._native_sync_controls()
    finally:
        window._native_style_busy = False


def instalar(legacy_module):
    """Instala subclasses visuais sem trocar facade, callbacks ou arquivos."""
    if getattr(legacy_module, _INSTALLATION, None):
        return legacy_module
    original_window = legacy_module.MainWindow
    original_hud = legacy_module.HudCanvas

    class NativeHud(original_hud):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.hud_style = "core"
            self._native_reduced = reduced_motion()
            self._native_mic = MicrophoneButton(self)
            self._native_mic.clicked.connect(self._native_toggle_mute)
            self.setAccessibleName("Reator LED do Jarvis")
            self._native_sync_controls()
            self._native_timer()

        def _native_toggle_mute(self):
            callback = getattr(self.window(), "_toggle_mute", None)
            if callable(callback):
                callback()

        def _native_sync_controls(self):
            button = getattr(self, "_native_mic", None)
            if button is not None:
                button.set_muted(bool(getattr(self, "muted", False)))
                button.setVisible(getattr(self, "hud_style", "core") == "core")

        def _native_timer(self):
            timer = getattr(self, "_tmr", None)
            if timer is None:
                return
            if self.isVisible() and not self.window().isMinimized():
                timer.start(200 if self._native_reduced else 33)
            else:
                timer.stop()

        def showEvent(self, event):
            super().showEvent(event)
            self._native_timer()

        def hideEvent(self, event):
            timer = getattr(self, "_tmr", None)
            if timer is not None:
                timer.stop()
            super().hideEvent(event)

        def _step(self):
            super()._step()
            self._native_sync_controls()
            if self.isVisible() and not self.window().isMinimized():
                self.update()

        def paintEvent(self, event):
            if getattr(self, "hud_style", "core") == "face":
                self._native_sync_controls()
                return super().paintEvent(event)
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.fillRect(self.rect(), QColor(BACKGROUND))
            width, height = self.width(), self.height()
            radius = max(32.0, min(width * .39, (height - 148) / 2))
            cx, cy = width / 2, radius + 15
            label, color = state_details(getattr(self, "state", "INITIALISING"),
                                         bool(getattr(self, "muted", False)),
                                         bool(getattr(self, "speaking", False)))
            accent = QColor(color)
            phase = 0 if self._native_reduced else float(getattr(self, "_core_phase", 0)) * 18
            amplitude = max(0.0, min(1.0, float(getattr(self, "_amp_disp", 0))))
            aura = QRadialGradient(QPointF(cx, cy), radius * 1.20)
            aura.setColorAt(0, QColor("#f7fdff"))
            aura.setColorAt(.12, QColor("#e0f8ff"))
            aura.setColorAt(.46, QColor("#4fb9f3"))
            aura.setColorAt(.68, QColor("#073455"))
            aura.setColorAt(.83, QColor("#03172c"))
            aura.setColorAt(1, QColor(BACKGROUND))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(aura)
            painter.drawEllipse(QPointF(cx, cy), radius * 1.2, radius * 1.2)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for scale, opacity, line_width in ((1.02, 90, 1), (.73, 130, 1), (.63, 95, 1)):
                tone = QColor(accent)
                tone.setAlpha(opacity)
                painter.setPen(QPen(tone, line_width))
                painter.drawEllipse(QPointF(cx, cy), radius * scale, radius * scale)
            ring = QRectF(cx - radius * .86, cy - radius * .86, radius * 1.72, radius * 1.72)
            painter.setPen(QPen(QColor(WHITE), max(3, radius * .022), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for angle in (0, 90, 180, 270):
                painter.drawArc(ring, int((angle + phase) * 16), 68 * 16)
            orbit = QRectF(cx - radius * 1.05, cy - radius * 1.05, radius * 2.10, radius * 2.10)
            painter.setPen(QPen(accent, max(2, radius * .014)))
            for angle in (18, 108, 198, 288):
                painter.drawArc(orbit, int((angle - phase * .65) * 16), 26 * 16)
            painter.setPen(QPen(QColor("#16435c"), 1))
            painter.drawLine(QPointF(cx - radius * 1.15, cy), QPointF(cx + radius * 1.15, cy))
            mic_y = min(height - 111, cy + radius + 6)
            self._native_mic.setGeometry(int(cx - 29), int(mic_y), 58, 58)
            self._native_mic.raise_()
            for side in (-1, 1):
                for index in range(11):
                    envelope = 1 - abs(index - 5) / 6
                    wave_height = 2 if self._native_reduced else 3 + amplitude * 23 * envelope
                    wave_color = QColor(accent)
                    wave_color.setAlpha(100 + int(envelope * 130))
                    painter.setPen(QPen(wave_color, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                    x = cx + side * (47 + index * 6)
                    painter.drawLine(QPointF(x, mic_y + 29 - wave_height), QPointF(x, mic_y + 29 + wave_height))
            painter.setPen(QColor(WHITE))
            painter.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
            painter.drawText(QRectF(8, mic_y + 64, width - 16, 24), Qt.AlignmentFlag.AlignCenter, label)
            painter.setPen(QColor("#85acc2"))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(QRectF(8, mic_y + 90, width - 16, 18), Qt.AlignmentFlag.AlignCenter,
                             "Controle a captura na janela Microfone")
            painter.end()

    class NativeMainWindow(original_window):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if self.centralWidget() is not None:
                self.centralWidget().setStyleSheet("background: " + BACKGROUND + ";")
            _modernize_controls(self)
            captions = {
                "◈ SYS MONITOR": "SISTEMA",
                "▸ ACTIVITY LOG": "CONVERSA",
                "▸ FILE UPLOAD": "ARQUIVOS",
                "▸ COMMAND INPUT": "MENSAGEM",
                "No file loaded — drop or click above to upload": "Arraste um arquivo ou clique para selecionar",
                "AI CORE\nACTIVE": "JARVIS\nPESSOAL",
                "SEC\nCLEARED": "CONTROLES\nLOCAIS",
            }
            for label in self.findChildren(QLabel):
                if label.text() in captions:
                    label.setText(captions[label.text()])
            name = str(getattr(self, "_assistant_name", "JARVIS")).strip() or "JARVIS"
            self.setWindowTitle(name.upper())
            screen = QApplication.primaryScreen()
            if screen is not None:
                area = screen.availableGeometry()
                self.resize(min(1240, max(820, area.width() - 56)), min(800, max(580, area.height() - 56)))
                self.move(area.x() + (area.width() - self.width()) // 2,
                          area.y() + (area.height() - self.height()) // 2)

        def _build_header(self):
            header = super()._build_header()
            header.setFixedHeight(54)
            header.setStyleSheet("background: #06111e; border-bottom: 1px solid #1b526d;")
            for label in header.findChildren(QLabel):
                if label.text() == getattr(legacy_module, "APP_VERSION", "MARK LVI"):
                    label.hide()
            title = getattr(self, "_title_lbl", None)
            if title is not None:
                title.setFont(QFont("Segoe UI", 20, QFont.Weight.DemiBold))
                title.setStyleSheet("color: #effbff; background: transparent;")
            subtitle = getattr(self, "_sub_lbl", None)
            if subtitle is not None:
                subtitle.setText("ASSISTENTE INTELIGENTE")
                subtitle.setFont(QFont("Segoe UI", 7))
                subtitle.setStyleSheet("color: #91bed5; background: transparent;")
            callback = getattr(self, "_open_plugin_manager", None)
            if callable(callback) and header.layout() is not None:
                self._native_agents_btn = QPushButton("Agentes", header)
                self._native_agents_btn.setAccessibleName("Abrir agentes e extensões")
                self._native_agents_btn.setToolTip("Agentes e extensões do Jarvis")
                self._native_agents_btn.clicked.connect(callback)
                header.layout().insertWidget(5, self._native_agents_btn)
            return header

        def _refresh_hud_btn(self):
            button = getattr(self, "_hud_btn", None)
            if button is None:
                return
            face = getattr(getattr(self, "hud", None), "hud_style", "core") == "face"
            button.setText("Visual: avatar" if face else "Visual: reator LED")
            button.setToolTip("Alternar entre avatar e reator LED")
            _modernize_controls(self)

        def _toggle_hud_style(self):
            hud = getattr(self, "hud", None)
            if hud is not None:
                hud.hud_style = "core" if hud.hud_style == "face" else "face"
                hud._native_sync_controls()
                hud.update()
                self._refresh_hud_btn()

        def changeEvent(self, event):
            super().changeEvent(event)
            if event.type() == QEvent.Type.WindowStateChange:
                hud = getattr(self, "hud", None)
                if callable(getattr(hud, "_native_timer", None)):
                    hud._native_timer()

    # Reapply only after real state/overlay callbacks. No recursive style event filter.
    wrapped = ("_style_mute_btn", "_refresh_wake_btns", "_refresh_talk_btns",
               "_update_brief_btn", "_update_autostart_btn", "_open_customize",
               "_open_audio_devices", "_open_providers", "_open_memory_panel",
               "_show_confirm_banner", "_open_plugin_manager", "_open_plugin_settings",
               "_show_setup", "_open_remote", "_on_setup_done", "_apply_name_update")
    for method_name in wrapped:
        method = getattr(original_window, method_name, None)
        if not callable(method):
            continue

        def wrap(callback):
            # Qt omits clicked(bool) for a slot that accepts no arguments.
            # Keep that arity instead of forwarding False into legacy methods.
            parameters = tuple(inspect.signature(callback).parameters.values())
            if len(parameters) == 1:
                def styled(self):
                    result = callback(self)
                    _modernize_controls(self)
                    return result
            else:
                def styled(self, *args, **kwargs):
                    result = callback(self, *args, **kwargs)
                    _modernize_controls(self)
                    return result
            return styled

        setattr(NativeMainWindow, method_name, wrap(method))
    legacy_module.HudCanvas = NativeHud
    legacy_module.MainWindow = NativeMainWindow
    setattr(legacy_module, _INSTALLATION, (original_window, original_hud))
    return legacy_module


def __getattr__(name):
    if name != "JarvisUI":
        raise AttributeError(name)
    legacy_module = importlib.import_module("ui")
    instalar(legacy_module)
    # Esta selecao vale somente para este processo iniciado pelo main.py.
    os.environ["JARVIS_INTERFACE_MODE"] = "native"
    return legacy_module.JarvisUI
