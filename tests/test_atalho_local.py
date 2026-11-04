"""Iniciador de Desktop, somente com pastas e programas ficticios."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("atalho_sintetico", ROOT / "tools" / "criar_atalho_local.py")
atalho = importlib.util.module_from_spec(SPEC)
with patch.object(sys, "path", [str(ROOT / "tools"), *sys.path]):
    SPEC.loader.exec_module(atalho)


def snapshot(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file() and not path.is_symlink()}


class DesktopLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jarvis-atalho-sintetico-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.app = self.root / "Jarvis pessoal ç 100% & (teste)!"
        self.desktop = self.root / "Desktop redirecionado ç"
        self.app.mkdir()
        self.desktop.mkdir()
        self.executed = self.root / "NAO_EXECUTAR"
        (self.app / "main.py").write_text(
            f"from pathlib import Path\nPath({str(self.executed)!r}).write_text('EXECUTOU')\nraise RuntimeError('NAO EXECUTAR')\n",
            encoding="utf-8",
        )
        (self.app / "browser_audio_bridge.py").write_text("raise RuntimeError('NAO IMPORTAR')\n", encoding="utf-8")
        (self.app / atalho.preparacao.MARKER).write_text(json.dumps({"version": 1, "status": "preparado"}), encoding="utf-8")
        (self.app / ".env").write_text("EXEMPLO_LOCAL=VALOR_SINTETICO\n", encoding="utf-8")
        (self.app / "interface-oficial").mkdir()
        for name in atalho.preparacao.ASSETS:
            (self.app / "interface-oficial" / name).write_text("/* FICTICIO */\n", encoding="utf-8")
        self.python = self.root / "Python ç 100% & (teste)!" / "python.exe"
        self.python.parent.mkdir()
        self.python.write_bytes(b"EXECUTAVEL FICTICIO NAO EXECUTAR")
        self.before = snapshot(self.app)

    def create(self, app=None, desktop=None, python=None):
        return atalho.criar(app or self.app, desktop or self.desktop,
                            python_executable=python or self.python)

    def preserved(self):
        self.assertEqual(snapshot(self.app), self.before)
        self.assertFalse(self.executed.exists())

    def test_creates_one_quoted_python_invocation_without_running_or_opening_browser(self):
        launcher = self.create()
        self.assertEqual(launcher, self.desktop / atalho.LAUNCHER_NAME)
        raw = launcher.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        text = raw.decode("utf-8")
        self.assertIn("setlocal DisableDelayedExpansion\r\nchcp 65001 >nul", text)
        self.assertIn(f'cd /d "{str(self.app).replace("%", "%%")}"\r\n', text)
        command = f'"{str(self.python).replace("%", "%%")}" "main.py"'
        self.assertEqual(text.count(command), 1)
        self.assertEqual(text.count('"main.py"'), 1)
        self.assertIn('set "JARVIS_INTERFACE_MODE=app"\r\n' + command, text)
        self.assertEqual(launcher.name, "Jarvis - Interface nova.cmd")
        self.assertNotIn("webbrowser", text)
        self.assertNotIn("http://", text)
        self.assertNotIn("start ", text.lower())
        self.assertIn("pause", text)
        self.assertNotIn("VALOR_SINTETICO", text)
        self.preserved()

    def test_exact_repeat_is_idempotent_and_preserves_mtime(self):
        launcher = self.create()
        before = (launcher.read_bytes(), launcher.stat().st_mtime_ns)
        self.assertEqual(self.create(), launcher)
        self.assertEqual((launcher.read_bytes(), launcher.stat().st_mtime_ns), before)
        self.preserved()

    def test_existing_launcher_with_other_content_is_never_overwritten(self):
        launcher = self.desktop / atalho.LAUNCHER_NAME
        launcher.write_bytes(b"PRESERVAR INICIADOR PESSOAL")
        with self.assertRaises(RuntimeError):
            self.create()
        self.assertEqual(launcher.read_bytes(), b"PRESERVAR INICIADOR PESSOAL")
        self.preserved()

    def test_existing_directory_with_launcher_name_is_never_overwritten(self):
        launcher = self.desktop / atalho.LAUNCHER_NAME
        launcher.mkdir()
        with self.assertRaises(RuntimeError):
            self.create()
        self.assertTrue(launcher.is_dir())
        self.preserved()

    def test_default_uses_windows_desktop_resolver(self):
        with patch.object(atalho, "_desktop_windows", return_value=self.desktop) as finder:
            launcher = atalho.criar(self.app, python_executable=self.python)
        finder.assert_called_once_with()
        self.assertEqual(launcher.parent, self.desktop)
        self.preserved()

    def test_default_uses_current_python_without_starting_it(self):
        launcher = atalho.criar(self.app, self.desktop)
        interpreter = Path(sys.executable).absolute()
        expected_path = interpreter.parent.resolve() / interpreter.name
        expected = '"' + str(expected_path).replace("%", "%%") + '" "main.py"'
        self.assertIn(expected, launcher.read_text(encoding="utf-8"))
        self.preserved()

    def test_current_python_keeps_venv_symlink_in_the_launcher(self):
        venv = self.root / "venv sintetica" / "bin"
        venv.mkdir(parents=True)
        interpreter = venv / "python"
        try:
            interpreter.symlink_to(self.python)
        except OSError as error:
            self.skipTest(f"Sem permissao para criar link sintetico: {error}")
        with patch.object(sys, "executable", str(interpreter)):
            launcher = atalho.criar(self.app, self.desktop)
        text = launcher.read_text(encoding="utf-8")
        expected = '"' + str(interpreter).replace("%", "%%") + '" "main.py"'
        self.assertIn(expected, text)
        self.assertNotIn('"' + str(self.python).replace("%", "%%") + '" "main.py"', text)
        self.preserved()

    def test_missing_or_incomplete_copy_is_refused(self):
        for relative in ("main.py", "browser_audio_bridge.py", atalho.preparacao.MARKER,
                         "interface-oficial/voice.js"):
            with self.subTest(relative=relative):
                path = self.app / relative
                content = path.read_bytes()
                path.unlink()
                try:
                    with self.assertRaises(RuntimeError):
                        self.create()
                    self.assertFalse((self.desktop / atalho.LAUNCHER_NAME).exists())
                finally:
                    path.write_bytes(content)
        self.preserved()

    def test_invalid_or_unfinished_manifest_is_refused(self):
        marker = self.app / atalho.preparacao.MARKER
        original = marker.read_bytes()
        for content in (b"not json", b"[]", b'{"version":1,"status":"incompleto"}',
                        b'{"version":2,"status":"preparado"}'):
            with self.subTest(content=content):
                marker.write_bytes(content)
                with self.assertRaises(RuntimeError):
                    self.create()
                self.assertFalse((self.desktop / atalho.LAUNCHER_NAME).exists())
        marker.write_bytes(original)
        self.preserved()

    def test_original_without_preparation_manifest_is_refused(self):
        original = self.root / "origem pessoal"
        original.mkdir()
        (original / "main.py").write_text("raise RuntimeError('ORIGINAL NAO EXECUTAR')", encoding="utf-8")
        before = snapshot(original)
        with self.assertRaises(RuntimeError):
            self.create(app=original)
        self.assertEqual(snapshot(original), before)
        self.assertFalse((self.desktop / atalho.LAUNCHER_NAME).exists())
        self.preserved()

    def test_app_or_desktop_inside_git_is_refused(self):
        for path in (self.app, self.desktop):
            with self.subTest(path=path):
                marker = path / ".git"
                marker.write_text("gitdir: SINTETICO", encoding="utf-8")
                try:
                    with self.assertRaises(RuntimeError):
                        self.create()
                finally:
                    marker.unlink()
        checkout = self.root / "outro checkout"
        (checkout / ".git").mkdir(parents=True)
        desktop = checkout / "Desktop"
        desktop.mkdir()
        with self.assertRaises(RuntimeError):
            self.create(desktop=desktop)
        self.preserved()

    def test_explicit_repository_root_is_refused_even_without_git_metadata(self):
        with patch.object(atalho.preparacao, "REPOSITORY_ROOT", self.root):
            with self.assertRaises(RuntimeError):
                self.create()
        self.preserved()

    def test_desktop_inside_app_and_missing_python_are_refused(self):
        with self.assertRaises(RuntimeError):
            self.create(desktop=self.app)
        with self.assertRaises(RuntimeError):
            self.create(python=self.root / "python ausente.exe")
        self.preserved()

    def test_shell_control_characters_are_rejected_before_writing(self):
        for char in ('"', "\r", "\n", "\x00"):
            with self.subTest(char=repr(char)):
                with self.assertRaises(RuntimeError):
                    self.create(app=Path(str(self.app) + char + "invalido"))
        self.assertFalse((self.desktop / atalho.LAUNCHER_NAME).exists())
        self.preserved()

    def test_symlink_app_asset_desktop_and_launcher_are_refused(self):
        linked = self.root / "Desktop vinculado"
        try:
            linked.symlink_to(self.desktop, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Sem permissao para criar link sintetico: {error}")
        with self.assertRaises(RuntimeError):
            self.create(desktop=linked)
        linked.unlink()
        linked.symlink_to(self.app, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            self.create(app=linked)
        linked.unlink()
        launcher = self.desktop / atalho.LAUNCHER_NAME
        launcher.symlink_to(self.root / "arquivo inexistente")
        with self.assertRaises(RuntimeError):
            self.create()
        launcher.unlink()
        asset = self.app / "interface-oficial" / "voice.js"
        content = asset.read_bytes()
        asset.unlink()
        try:
            asset.symlink_to(self.root / "arquivo inexistente")
            with self.assertRaises(RuntimeError):
                self.create()
        finally:
            asset.unlink()
            asset.write_bytes(content)
        self.preserved()


if __name__ == "__main__":
    unittest.main()
