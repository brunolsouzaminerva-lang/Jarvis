"""Cria um iniciador no Desktop para a copia preparada do Jarvis pessoal.

O iniciador chama main.py uma vez, na pasta correta. A propria aplicacao abre a
nova tela de voz quando o provedor conecta; nenhuma segunda aba e criada aqui.
Este preparador nao inicia o Jarvis e nao altera nenhum arquivo da aplicacao.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys

try:
    from . import preparar_interface_local as preparacao
except ImportError:
    import preparar_interface_local as preparacao


LAUNCHER_NAME = "Jarvis - Interface nova.cmd"


def _desktop_windows() -> Path:
    """Consulta o Desktop real, inclusive quando redirecionado pelo Windows."""
    if os.name != "nt":
        raise RuntimeError("A descoberta do Desktop requer Windows; informe --desktop nos testes.")
    buffer = ctypes.create_unicode_buffer(32768)
    folder = ctypes.windll.shell32.SHGetFolderPathW
    folder.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.HANDLE,
                       wintypes.DWORD, wintypes.LPWSTR]
    folder.restype = ctypes.c_long
    # CSIDL_DESKTOPDIRECTORY = 0x10; SHGFP_TYPE_CURRENT = 0.
    result = folder(None, 0x10, None, 0, buffer)
    if result != 0 or not buffer.value:
        raise RuntimeError("Nao foi possivel localizar o Desktop do Windows.")
    return Path(buffer.value)


def _safe_path(value: Path | str) -> Path:
    # Quotes/newlines can break the batch command even before filesystem checks.
    text = str(value)
    if any(char in text for char in ('"', "\r", "\n", "\x00")):
        raise RuntimeError("O caminho contem caracteres invalidos para o iniciador.")
    path = preparacao._path(Path(value))
    if any(char in str(path) for char in ('"', "\r", "\n", "\x00")):
        raise RuntimeError("O caminho contem caracteres invalidos para o iniciador.")
    return path


def _outside_git(path: Path) -> None:
    repository = preparacao.REPOSITORY_ROOT.resolve()
    if path == repository or repository in path.parents:
        raise RuntimeError("A copia e o iniciador devem ficar fora do repositorio de desenvolvimento.")
    if any((parent / ".git").exists() or (parent / ".git").is_symlink()
           for parent in (path, *path.parents)):
        raise RuntimeError("A copia e o iniciador devem ficar fora de repositorios Git.")


def _quote_cmd(path: Path) -> str:
    # In a batch file %% is a literal %. ! remains literal with delayed
    # expansion disabled; &, |, ^ and parentheses stay inside the quotes.
    return '"' + str(path).replace("%", "%%") + '"'


def _current_python() -> Path:
    # Preserve the interpreter's venv path: resolving the final symlink to the
    # base executable would discard pyvenv.cfg and its installed dependencies.
    path = Path(sys.executable).expanduser().absolute()
    if any(char in str(path) for char in ('"', "\r", "\n", "\x00")):
        raise RuntimeError("O caminho do Python contem caracteres invalidos.")
    return _safe_path(path.parent) / path.name


def _launcher_bytes(app: Path, python: Path) -> bytes:
    lines = [
        "@echo off",
        "setlocal DisableDelayedExpansion",
        "chcp 65001 >nul",
        "title Jarvis - Interface nova",
        f"cd /d {_quote_cmd(app)}",
        "if errorlevel 1 (",
        "  echo Nao foi possivel abrir a pasta do Jarvis Teste.",
        "  pause",
        "  exit /b 1",
        ")",
        'set "JARVIS_INTERFACE_MODE=app"',
        f'{_quote_cmd(python)} "main.py"',
        "if errorlevel 1 (",
        "  echo O Jarvis encerrou com erro. Confira a mensagem acima.",
        "  pause",
        "  exit /b 1",
        ")",
        "endlocal",
        "",
    ]
    # No BOM: cmd.exe reads the initial ASCII lines before switching to UTF-8.
    return "\r\n".join(lines).encode("utf-8")


def criar(pasta: Path, desktop: Path | None = None, *,
          python_executable: Path | str | None = None) -> Path:
    """Cria somente o .cmd; repeticoes identicas preservam o arquivo existente."""
    app = _safe_path(pasta)
    target_dir = _safe_path(desktop if desktop is not None else _desktop_windows())
    # Only the trusted running interpreter may itself be a symlink. Ancestors
    # and explicitly supplied paths keep the ordinary link/junction checks.
    python = _safe_path(python_executable) if python_executable is not None else _current_python()
    _outside_git(app)
    _outside_git(target_dir)
    if not app.is_dir() or not target_dir.is_dir():
        raise RuntimeError("A pasta preparada e o Desktop precisam existir.")
    if target_dir == app or app in target_dir.parents:
        raise RuntimeError("Escolha uma pasta de atalhos fora da copia do Jarvis.")
    if not python.is_file():
        raise RuntimeError("Executavel Python nao encontrado.")

    required = ("main.py", "browser_audio_bridge.py", preparacao.MARKER,
                *("interface-oficial/" + name for name in preparacao.ASSETS))
    for relative in required:
        path = _safe_path(app / relative)
        if not path.is_file():
            raise RuntimeError("A copia preparada esta incompleta. Execute o preparador primeiro.")
    try:
        manifest = json.loads((app / preparacao.MARKER).read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        raise RuntimeError("O manifesto da copia preparada e invalido.") from None
    if (not isinstance(manifest, dict) or manifest.get("version") != 1
            or manifest.get("status") != "preparado"):
        raise RuntimeError("A pasta nao e uma copia preparada concluida.")

    launcher = _safe_path(target_dir / LAUNCHER_NAME)
    content = _launcher_bytes(app, python)
    if launcher.exists():
        if not launcher.is_file() or launcher.read_bytes() != content:
            raise RuntimeError("O iniciador ja existe com outro conteudo. Nenhum arquivo alterado.")
        return launcher
    with launcher.open("xb") as stream:
        stream.write(content)
    return launcher


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pasta", required=True, type=Path)
    parser.add_argument("--desktop", type=Path,
                        help="Pasta personalizada de atalhos; por padrao usa o Desktop real do Windows.")
    args = parser.parse_args()
    try:
        launcher = criar(args.pasta, args.desktop)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ATALHO NAO CRIADO: {error}", file=sys.stderr)
        return 1
    print(f"ATALHO CRIADO OU JA CONFERIDO: {launcher}")
    print("NENHUM APLICATIVO EXECUTADO")
    print("Feche a instancia anterior antes de clicar duas vezes no iniciador.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
