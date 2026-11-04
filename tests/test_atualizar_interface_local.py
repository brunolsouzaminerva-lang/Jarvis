"""Atualizacao com backups/rollback em copias inteiramente ficticias."""
import contextlib
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("atualizador_sintetico", ROOT / "tools" / "atualizar_interface_local.py")
atualizador = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = atualizador
with patch.object(sys, "path", [str(ROOT / "tools"), *sys.path]):
    SPEC.loader.exec_module(atualizador)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(root):
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file() and not path.is_symlink()}


class PersonalInterfaceUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jarvis-update-sintetico-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.app = self.root / "Jarvis pessoal ç 100%"
        self.package = self.root / "pacote de desenvolvimento"
        self.app.mkdir()
        (self.package / "integracao").mkdir(parents=True)
        (self.package / "interface-oficial").mkdir()
        (self.app / "interface-oficial").mkdir()
        self.executed = self.root / "NAO_EXECUTAR"
        executable_text = (
            "from pathlib import Path\n"
            f"Path({str(self.executed)!r}).write_text('EXECUTOU')\n"
            "raise RuntimeError('NAO EXECUTAR')\n"
        )
        (self.app / "main.py").write_text(executable_text, encoding="utf-8")
        (self.app / ".env").write_bytes(b"CONFIGURACAO_FICTICIA=PRIVADO_SINTETICO\r\n")
        (self.app / "config").mkdir()
        (self.app / "config" / "api_keys.json").write_bytes(b'{"ficticio":"VALOR_SINTETICO"}\r\n')
        (self.app / "jarvis_ggo_integrado.py").write_text(executable_text, encoding="utf-8")
        (self.app / "relatorio_ficticio.xlsx").write_bytes(b"DADOS FICTICIOS NAO PROCESSAR\x00\x01")
        self.old = {}
        self.new = {}
        for relative in atualizador.FILES:
            if relative == "browser_audio_bridge.py":
                old = ("# ORIGINAL FICTICIO\n" + executable_text).encode("utf-8")
                new = ("# NOVO FICTICIO\n" + executable_text).encode("utf-8")
            else:
                old = ("/* ORIGINAL FICTICIO: " + relative + " */\n").encode("utf-8")
                new = ("/* NOVO FICTICIO: " + relative + " */\n").encode("utf-8")
            (self.app / relative).write_bytes(old)
            self.package_path(relative).write_bytes(new)
            self.old[relative] = old
            self.new[relative] = new
        self.marker = self.app / atualizador.preparacao.MARKER
        prepared = {name: digest(data) for name, data in snapshot(self.app).items()}
        self.manifest = {"version": 1, "status": "preparado", "etapa201": True,
                         "original_files": dict(prepared), "prepared_files": prepared,
                         "preferencia_ficticia": {"preservar": True}}
        self.marker.write_text(json.dumps(self.manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        self.before = snapshot(self.app)
        self.package_before = snapshot(self.package)
        self.patcher = patch.object(atualizador.preparacao, "REPOSITORY_ROOT", self.package)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def package_path(self, relative):
        return self.package / ("integracao/browser_audio_bridge.py"
                               if relative == "browser_audio_bridge.py" else relative)

    def update(self, app=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return atualizador.atualizar(app or self.app)

    def backups(self):
        return sorted(path for path in self.app.iterdir()
                      if path.name.startswith("backup_interface_") and path.is_dir())

    def assert_not_executed(self):
        self.assertFalse(self.executed.exists())

    def assert_refused(self):
        before = snapshot(self.app)
        backups = self.backups()
        with self.assertRaises((OSError, RuntimeError, ValueError, SyntaxError)):
            self.update()
        self.assertEqual(snapshot(self.app), before)
        self.assertEqual(self.backups(), backups)
        self.assert_not_executed()

    def test_updates_only_the_seven_assets_and_manifest_with_exact_backups(self):
        backup = self.update()
        self.assertEqual(backup.parent, self.app)
        self.assertEqual(self.backups(), [backup])
        expected_backup = {**self.old, atualizador.preparacao.MARKER: self.before[atualizador.preparacao.MARKER]}
        self.assertEqual(snapshot(backup), expected_backup)
        for relative, data in self.new.items():
            self.assertEqual((self.app / relative).read_bytes(), data)
        for relative, data in self.before.items():
            if relative not in atualizador.FILES and relative != atualizador.preparacao.MARKER:
                self.assertEqual((self.app / relative).read_bytes(), data)
        actual = json.loads(self.marker.read_bytes())
        for key in ("version", "status", "etapa201", "original_files", "preferencia_ficticia"):
            self.assertEqual(actual[key], self.manifest[key])
        expected = dict(self.manifest["prepared_files"])
        expected.update({name: digest(data) for name, data in self.new.items()})
        self.assertEqual(actual["prepared_files"], expected)
        self.assertEqual(snapshot(self.package), self.package_before)
        self.assert_not_executed()

    def test_exact_repeat_does_not_create_backup_or_rewrite_files(self):
        self.update()
        before = snapshot(self.app)
        mtimes = {path: path.stat().st_mtime_ns for path in self.app.rglob("*") if path.is_file()}
        backups = self.backups()
        self.assertIsNone(self.update())
        self.assertEqual(snapshot(self.app), before)
        self.assertEqual(self.backups(), backups)
        self.assertEqual({path: path.stat().st_mtime_ns for path in mtimes}, mtimes)
        self.assert_not_executed()

    def test_personal_configuration_edits_are_preserved_after_preparation(self):
        (self.app / ".env").write_bytes(b"PREFERENCIA_FICTICIA_ATUALIZADA=preservar\r\n")
        (self.app / "config" / "api_keys.json").write_bytes(b'{"ficticio":"EDICAO_LOCAL"}')
        personal = {name: (self.app / name).read_bytes()
                    for name in (".env", "config/api_keys.json", "main.py", "jarvis_ggo_integrado.py")}
        self.update()
        for name, data in personal.items():
            self.assertEqual((self.app / name).read_bytes(), data)
        self.assert_not_executed()

    def test_manual_interface_edits_and_unknown_hashes_refuse_before_backup(self):
        path = self.app / "interface-oficial/voice.js"
        path.write_bytes(path.read_bytes() + b"/* EDICAO PESSOAL PRESERVAR */")
        self.assert_refused()
        path.write_bytes(self.old["interface-oficial/voice.js"])
        marker = json.loads(self.marker.read_bytes())
        marker["prepared_files"].pop("interface-oficial/voice.js")
        self.marker.write_text(json.dumps(marker), encoding="utf-8")
        self.assert_refused()

    def test_missing_or_unfinished_manifest_refuses_before_backup(self):
        original = self.marker.read_bytes()
        for data in (None, b"invalid json", b"[]", b'{"version":1,"status":"incompleto"}',
                     b'{"version":1,"status":"preparado","prepared_files":[]}'):
            with self.subTest(data=data):
                if data is None:
                    self.marker.unlink()
                else:
                    self.marker.write_bytes(data)
                self.assert_refused()
                self.marker.write_bytes(original)

    def test_missing_application_or_package_asset_refuses_before_backup(self):
        for path in (self.app / "main.py", self.app / "interface-oficial/app.js",
                     self.package_path("browser_audio_bridge.py"), self.package_path("interface-oficial/voice.js")):
            with self.subTest(path=path.name):
                data = path.read_bytes()
                path.unlink()
                try:
                    self.assert_refused()
                finally:
                    path.write_bytes(data)

    def test_invalid_replacement_python_refuses_before_any_write(self):
        self.package_path("browser_audio_bridge.py").write_bytes(b"def nao_compila(:\n")
        self.assert_refused()

    def test_two_updates_in_the_same_second_keep_distinct_backups(self):
        fixed = datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        with patch.object(atualizador, "datetime") as clock:
            clock.now.return_value = fixed
            first = self.update()
            first_content = snapshot(first)
            self.package_path("interface-oficial/voice.js").write_bytes(b"/* TERCEIRA VERSAO FICTICIA */")
            second = self.update()
        self.assertNotEqual(first, second)
        self.assertEqual(snapshot(first), first_content)
        self.assertEqual((second / "interface-oficial/voice.js").read_bytes(), self.new["interface-oficial/voice.js"])
        self.assert_not_executed()

    def test_colliding_backup_is_refused_without_overwriting_existing_content(self):
        fixed = datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        collision = self.app / "backup_interface_20300102_030405_11111111"
        collision.mkdir()
        (collision / "preservar.txt").write_bytes(b"BACKUP FICTICIO EXISTENTE")
        with patch.object(atualizador, "datetime") as clock, patch.object(atualizador.uuid, "uuid4", return_value=SimpleNamespace(hex="1" * 32)):
            clock.now.return_value = fixed
            self.assert_refused()
        self.assertEqual((collision / "preservar.txt").read_bytes(), b"BACKUP FICTICIO EXISTENTE")

    def failure_during_write(self, relative):
        replace = atualizador.os.replace
        failed = False

        def fail_once(source, destination):
            nonlocal failed
            if Path(destination) == self.app / relative and not failed:
                failed = True
                raise OSError("FALHA DE ESCRITA INTEIRAMENTE FICTICIA")
            return replace(source, destination)

        with patch.object(atualizador.os, "replace", side_effect=fail_once):
            with self.assertRaises((OSError, RuntimeError)):
                self.update()
        self.assertTrue(failed)
        backups = self.backups()
        self.assertEqual(len(backups), 1)
        after = {name: data for name, data in snapshot(self.app).items()
                 if not name.startswith(backups[0].name + "/")}
        self.assertEqual(after, self.before)
        self.assertEqual(snapshot(backups[0]), {**self.old, atualizador.preparacao.MARKER: self.before[atualizador.preparacao.MARKER]})
        self.assertEqual(snapshot(self.package), self.package_before)
        self.assert_not_executed()

    def test_failed_asset_write_rolls_back_and_keeps_verified_backup(self):
        self.failure_during_write("interface-oficial/core.js")

    def test_failed_manifest_write_rolls_back_all_assets(self):
        self.failure_during_write(atualizador.preparacao.MARKER)

    def test_application_in_git_or_repository_is_refused(self):
        (self.app / ".git").write_bytes(b"gitdir: FICTICIO")
        try:
            self.assert_refused()
        finally:
            (self.app / ".git").unlink()
        with patch.object(atualizador.preparacao, "REPOSITORY_ROOT", self.root):
            self.assert_refused()

    def test_links_in_app_assets_or_package_are_refused(self):
        outside = self.root / "fora ficticio.txt"
        outside.write_bytes(b"CONTEUDO FORA PRESERVAR")
        linked = self.root / "copia vinculada"
        try:
            linked.symlink_to(self.app, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Sem permissao para criar link sintetico: {error}")
        with self.assertRaises(RuntimeError):
            self.update(linked)
        for path in (self.app / "interface-oficial/voice.js", self.package_path("interface-oficial/voice.js")):
            data = path.read_bytes()
            path.unlink()
            try:
                path.symlink_to(outside)
                self.assert_refused()
            finally:
                path.unlink()
                path.write_bytes(data)
        self.assertEqual(outside.read_bytes(), b"CONTEUDO FORA PRESERVAR")
        self.assert_not_executed()


if __name__ == "__main__":
    unittest.main()
