"""Ponte local de microfone, compativel com o main.py pessoal do Jarvis.

Protocolo: /jarvis-audio recebe quadros binarios Float32 little-endian, mono,
48.000 Hz. A chamada on_pcm16 recebe PCM16 little-endian, mono, 16.000 Hz.
Nenhum comando de automacao e exposto. A pasta de arquivos pessoais nunca e
servida: somente os arquivos explicitos de interface-oficial abaixo.
"""
from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
import threading
from typing import Awaitable, Callable
import webbrowser

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
import uvicorn


HOST = "127.0.0.1"
PORT = 8765
ORIGIN = f"http://{HOST}:{PORT}"
MAX_FRAME_BYTES = 65536
ASSETS = frozenset({"index.html", "app.js", "core.js", "styles.css",
                    "home-reference.css", "voice.js"})


class PCMConverter:
    """Reduz 48 kHz para 16 kHz, preservando amostras entre os quadros."""

    def __init__(self):
        self.reset()

    def reset(self):
        self._tail = np.empty(0, dtype=np.float32)

    def feed(self, raw: bytes) -> bytes:
        if len(raw) > MAX_FRAME_BYTES or len(raw) % 4:
            raise ValueError("Quadro de audio invalido.")
        values = np.frombuffer(raw, dtype="<f4")
        if not np.isfinite(values).all():
            raise ValueError("Quadro de audio invalido.")
        values = np.concatenate((self._tail, values))
        usable = values.size - values.size % 3
        self._tail = values[usable:].copy()
        if not usable:
            return b""
        # Mantem a mesma media de tres amostras da ponte anterior.
        mono = values[:usable].reshape(-1, 3).mean(axis=1, dtype=np.float64)
        return np.clip(np.rint(mono * 32767.0), -32768, 32767).astype("<i2").tobytes()


class BrowserAudioBridge:
    def __init__(self, on_pcm16: Callable[[bytes], Awaitable[None] | None],
                 is_muted: Callable[[], bool] | None = None, *,
                 ui_root: Path | None = None):
        self.on_pcm16 = on_pcm16
        self.is_muted = is_muted or (lambda: False)
        here = Path(__file__).resolve().parent
        default_ui = here / "interface-oficial"
        if not default_ui.is_dir():
            default_ui = here.parent / "interface-oficial"
        self.ui_root = Path(ui_root or default_ui).resolve()
        self.app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        self.server: uvicorn.Server | None = None
        self.thread: threading.Thread | None = None
        self._connected = threading.Event()
        self._client_lock = threading.Lock()
        self._owner: object | None = None
        self._install_routes()

    @staticmethod
    def _valid_host(headers) -> bool:
        values = headers.getlist("host")
        return values == [f"{HOST}:{PORT}"]

    def _asset(self, name: str) -> Path | None:
        if name not in ASSETS:
            return None
        candidate = self.ui_root / name
        if candidate.is_symlink() or not candidate.is_file():
            return None
        if candidate.resolve().parent != self.ui_root:
            return None
        return candidate

    def _install_routes(self):
        @self.app.middleware("http")
        async def local_only(request, call_next):
            if not self._valid_host(request.headers):
                return Response("Host invalido.", status_code=400)
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            return response

        @self.app.get("/")
        async def home():
            index = self._asset("index.html")
            if index is None or any(self._asset(name) is None for name in ASSETS):
                return HTMLResponse("Interface incompleta. Recrie a copia de teste.", status_code=503)
            html = index.read_text(encoding="utf-8")
            if "</body>" not in html:
                return HTMLResponse("Interface invalida.", status_code=503)
            html = html.replace("</body>", '<script type="module" src="/voice.js"></script></body>', 1)
            return HTMLResponse(html)

        @self.app.get("/bridge-status")
        async def bridge_status():
            return JSONResponse({"available": True, "connected": self._connected.is_set(),
                                 "muted": bool(self.is_muted())})

        @self.app.get("/{name}")
        async def asset(name: str):
            # index.html tambem passa pela injecao; nunca entrega uma segunda home estatica.
            if name == "index.html":
                return await home()
            path = self._asset(name)
            return FileResponse(path) if path else Response(status_code=404)

        @self.app.websocket("/jarvis-audio")
        async def audio(ws: WebSocket):
            if (not self._valid_host(ws.headers)
                    or ws.headers.getlist("origin") != [ORIGIN]):
                await ws.close(code=1008)
                return
            owner = object()
            with self._client_lock:
                busy = self._owner is not None
                if not busy:
                    self._owner = owner
            if busy:
                await ws.close(code=1008)
                return
            converter = PCMConverter()
            try:
                await ws.accept()
                muted = bool(self.is_muted())
                self._connected.set()
                await ws.send_json({"type": "ready", "muted": muted})
                while True:
                    # O navegador deixa de enviar PCM no mudo. Mesmo sem quadros,
                    # avisa quando o usuario desmuta na janela original.
                    try:
                        message = await asyncio.wait_for(ws.receive(), timeout=0.25)
                    except asyncio.TimeoutError:
                        message = None
                    now_muted = bool(self.is_muted())
                    if muted != now_muted:
                        muted = now_muted
                        converter.reset()
                        await ws.send_json({"type": "muted", "value": muted})
                    if message is None:
                        continue
                    if message["type"] == "websocket.disconnect":
                        break
                    raw = message.get("bytes")
                    if raw is None:
                        await ws.close(code=1003)
                        break
                    try:
                        pcm = converter.feed(raw)
                    except ValueError:
                        await ws.close(code=1003)
                        break
                    if muted:
                        converter.reset()
                        continue
                    if pcm:
                        result = self.on_pcm16(pcm)
                        if inspect.isawaitable(result):
                            await result
            except WebSocketDisconnect:
                pass
            except Exception:
                # Nao envia detalhes do processo, configuracoes ou chaves ao navegador.
                try:
                    await ws.send_json({"type": "error", "message": "Falha no processamento do audio."})
                    await ws.close(code=1011)
                except Exception:
                    pass
            finally:
                with self._client_lock:
                    if self._owner is owner:
                        self._owner = None
                        self._connected.clear()

    def start(self, open_browser: bool = True):
        if self.thread and self.thread.is_alive():
            return
        self.server = uvicorn.Server(uvicorn.Config(
            self.app, host=HOST, port=PORT, log_level="warning",
            access_log=False, ws_max_size=MAX_FRAME_BYTES))
        self.thread = threading.Thread(target=self.server.run, daemon=True,
                                       name="jarvis-browser-mic")
        self.thread.start()
        if open_browser:
            timer = threading.Timer(1.2, lambda: webbrowser.open(ORIGIN))
            timer.daemon = True
            timer.start()

    async def wait_connected(self, timeout: float = 30.0) -> bool:
        # threading.Event atravessa os loops do servidor e da sessao de voz.
        return await asyncio.to_thread(self._connected.wait, timeout)

    def stop(self):
        self._connected.clear()
        if self.server:
            self.server.should_exit = True
