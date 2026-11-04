"""Instalacao/restauracao nativa em fontes inteiramente sinteticas, sem Qt."""
import hashlib
import contextlib
import importlib.util
import json
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    with patch.object(sys, "path", [str(ROOT / "tools"), *sys.path]):
        spec.loader.exec_module(module)
    return module


installer = load("instalador_nativo_sintetico", "instalar_interface_nativa.py")
web_updater = load("atualizador_web_compativel_sintetico", "atualizar_interface_local.py")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(root):
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file() and not path.is_symlink()}


class NativeInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jarvis-nativo-sintetico-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.app = self.root / "Jarvis pessoal ç 100%"
        self.package = self.root / "pacote publico de desenvolvimento"
        self.app.mkdir()
        (self.app / "config").mkdir()
        (self.app / "interface-oficial").mkdir()
        (self.package / "integracao").mkdir(parents=True)
        (self.package / "interface-oficial").mkdir()
        self.executed = self.root / "NAO_EXECUTAR"
        fail = ("from pathlib import Path\n"
                f"Path({str(self.executed)!r}).write_text('EXECUTOU')\n"
                "raise RuntimeError('CODIGO SINTETICO NAO DEVE EXECUTAR')\n")
        self.original_main = b"\xef\xbb\xbf" + ("# MAIN FICTICIO\nfrom ui import JarvisUI\n" + fail).replace("\n", "\r\n").encode("utf-8")
        self.original_ui = ("# UI FICTICIA\n" + fail).encode("utf-8")
        self.plugin = ("# MODULO NATIVO FICTICIO\n" + fail).encode("utf-8")
        (self.app / "main.py").write_bytes(self.original_main)
        (self.app / "ui.py").write_bytes(self.original_ui)
        (self.app / ".env").write_bytes(b"FICTICIO=SEM_CREDENCIAL_REAL\r\n")
        (self.app / "config" / "api_keys.json").write_bytes(b'{"exemplo":"DADO FICTICIO PRIVADO"}')
        (self.app / "jarvis_ggo_integrado.py").write_bytes(fail.encode("utf-8"))
        for name in web_updater.FILES:
            old = ("# PONTE FICTICIA\n" + fail).encode("utf-8") if name == "browser_audio_bridge.py" else ("/* antigo " + name + " */\n").encode("utf-8")
            new = ("# PONTE NOVA FICTICIA\n" + fail).encode("utf-8") if name == "browser_audio_bridge.py" else ("/* novo " + name + " */\n").encode("utf-8")
            (self.app / name).write_bytes(old)
            package_name = "integracao/browser_audio_bridge.py" if name == "browser_audio_bridge.py" else name
            (self.package / package_name).write_bytes(new)
        (self.package / "integracao" / installer.PLUGIN_NAME).write_bytes(self.plugin)
        self.marker = self.app / installer.preparacao.MARKER
        hashes = {name: sha(data) for name, data in snapshot(self.app).items()}
        self.manifest = {"version": 1, "status": "preparado", "original_files": dict(hashes),
                         "prepared_files": dict(hashes), "etapa201": True,
                         "preferencias_ficticias": {"preservar": "SIM"}}
        self.marker.write_text(json.dumps(self.manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        self.before = snapshot(self.app)
        self.package_before = snapshot(self.package)
        for target, name, value in [
            (installer, "MAIN_ORIGINAL_SHA256", sha(self.original_main)),
            (installer, "UI_ORIGINAL_SHA256", sha(self.original_ui)),
            (installer.preparacao, "REPOSITORY_ROOT", self.package),
        ]:
            patcher = patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def backups(self):
        return sorted(p for p in self.app.iterdir() if p.name.startswith(installer.BACKUP_PREFIX) and p.is_dir())

    def state(self):
        return json.loads(self.marker.read_bytes())

    def app_without_backups(self):
        return {name: data for name, data in snapshot(self.app).items()
                if not name.split("/", 1)[0].startswith("backup_")}

    def assert_not_executed(self):
        self.assertFalse(self.executed.exists())
        self.assertEqual(snapshot(self.package), self.package_before)

    def assert_private_preserved(self):
        for relative in (".env", "config/api_keys.json", "jarvis_ggo_integrado.py", "ui.py"):
            self.assertEqual((self.app / relative).read_bytes(), self.before[relative])
        self.assert_not_executed()

    def assert_refused(self, action=None):
        before = snapshot(self.app)
        backups = self.backups()
        with self.assertRaises((OSError, RuntimeError, ValueError, SyntaxError)):
            (action or installer.instalar)(self.app)
        self.assertEqual(snapshot(self.app), before)
        self.assertEqual(self.backups(), backups)
        self.assert_not_executed()

    def test_installs_one_import_preserving_bom_crlf_and_all_other_bytes(self):
        backup = installer.instalar(self.app)
        expected = self.original_main.replace(installer.ORIGINAL_IMPORT, installer.NATIVE_IMPORT)
        self.assertEqual((self.app / "main.py").read_bytes(), expected)
        self.assertTrue(expected.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\n", expected.replace(b"\r\n", b""))
        self.assertEqual((self.app / installer.PLUGIN_NAME).read_bytes(), self.plugin)
        self.assertEqual((backup / "main.py").read_bytes(), self.original_main)
        self.assertEqual((backup / installer.preparacao.MARKER).read_bytes(), self.before[installer.preparacao.MARKER])
        self.assertEqual(set(snapshot(backup)), {"main.py", installer.preparacao.MARKER})
        state = self.state()
        self.assertEqual(state["original_files"], self.manifest["original_files"])
        self.assertEqual(state["prepared_files"]["main.py"], sha(expected))
        self.assertEqual(state["prepared_files"][installer.PLUGIN_NAME], sha(self.plugin))
        self.assertEqual(state["native_interface"]["backup_dir"], backup.name)
        self.assertEqual(state["preferencias_ficticias"], self.manifest["preferencias_ficticias"])
        self.assert_private_preserved()

    def test_exact_repeat_does_not_rewrite_or_create_another_backup(self):
        installer.instalar(self.app)
        before = snapshot(self.app)
        mtimes = {name: (self.app / name).stat().st_mtime_ns for name in ("main.py", installer.PLUGIN_NAME, installer.preparacao.MARKER)}
        self.assertIsNone(installer.instalar(self.app))
        self.assertEqual(snapshot(self.app), before)
        self.assertEqual(len(self.backups()), 1)
        for name, value in mtimes.items():
            self.assertEqual((self.app / name).stat().st_mtime_ns, value)
        self.assert_private_preserved()

    def test_unknown_main_or_ui_and_reserved_module_are_refused(self):
        for name in ("main.py", "ui.py", installer.PLUGIN_NAME):
            with self.subTest(name=name):
                path = self.app / name
                original = path.read_bytes() if path.exists() else None
                path.write_bytes(b"# EDICAO PESSOAL FICTICIA\n")
                self.assert_refused()
                path.write_bytes(original) if original is not None else path.unlink()

    def test_personal_packages_and_module_aliases_are_refused(self):
        for name in ("jarvis_interface_nativa", "jarvis_interface_nativa.pyc",
                     "jarvis_interface_nativa.pyd", "jarvis_interface_nativa.cpython-313.so",
                     "Jarvis_Interface_Nativa.py", "jarvis_interface_nativa.py "):
            with self.subTest(name=name):
                path = self.app / name
                if name == "jarvis_interface_nativa":
                    path.mkdir()
                    (path / "__init__.py").write_bytes(self.plugin)
                else:
                    path.write_bytes(self.plugin)
                self.assert_refused()
                if path.is_dir():
                    (path / "__init__.py").unlink()
                    path.rmdir()
                else:
                    path.unlink()

    def test_manifest_cannot_claim_a_personal_module_was_part_of_the_origin(self):
        original = self.marker.read_bytes()
        for field in ("original_files", "prepared_files"):
            for name in (installer.PLUGIN_NAME, "jarvis_interface_nativa/__init__.py",
                         "Jarvis_Interface_Nativa.PY"):
                with self.subTest(field=field, name=name):
                    state = json.loads(original)
                    state[field][name] = sha(self.plugin)
                    self.marker.write_bytes(installer._dump(state))
                    self.assert_refused()
        self.marker.write_bytes(original)

    def test_original_folder_without_completed_marker_is_refused(self):
        self.marker.unlink()
        self.assert_refused()

    def test_incomplete_or_unrecognized_manifest_is_refused(self):
        original = self.marker.read_bytes()
        for value in (b"invalid json", b"[]", b'{"version":1,"status":"incompleto"}',
                      json.dumps({**self.manifest, "original_files": {}}).encode("utf-8")):
            with self.subTest(value=value[:40]):
                self.marker.write_bytes(value)
                self.assert_refused()
        self.marker.write_bytes(original)

    def test_invalid_new_module_is_compiled_without_executing_any_source(self):
        source = self.package / "integracao" / installer.PLUGIN_NAME
        source.write_bytes(b"def broken(:\n")
        self.package_before = snapshot(self.package)
        self.assert_refused()

    def test_duplicate_or_nested_import_is_refused_before_any_write(self):
        for original in (b"from ui import JarvisUI\nfrom ui import JarvisUI\n",
                         b"def nested():\n    from ui import JarvisUI\n"):
            with self.subTest(original=original):
                (self.app / "main.py").write_bytes(original)
                state = self.state()
                state["prepared_files"]["main.py"] = sha(original)
                state["original_files"]["main.py"] = sha(original)
                self.marker.write_bytes(installer._dump(state))
                with patch.object(installer, "MAIN_ORIGINAL_SHA256", sha(original)):
                    self.assert_refused()

    def test_restores_main_without_reverting_personal_settings(self):
        installer.instalar(self.app)
        new_config = b'{"exemplo":"PREFERENCIA FICTICIA EDITADA PELO USUARIO"}'
        (self.app / "config/api_keys.json").write_bytes(new_config)
        before_restore = snapshot(self.app)
        backup = installer.restaurar(self.app)
        self.assertEqual((self.app / "main.py").read_bytes(), self.original_main)
        self.assertFalse((self.app / installer.PLUGIN_NAME).exists())
        self.assertEqual((self.app / "config/api_keys.json").read_bytes(), new_config)
        self.assertEqual((backup / "main.py").read_bytes(), before_restore["main.py"])
        self.assertEqual((backup / installer.PLUGIN_NAME).read_bytes(), self.plugin)
        state = self.state()
        self.assertNotIn("native_interface", state)
        self.assertNotIn(installer.PLUGIN_NAME, state["prepared_files"])
        self.assertEqual(state["prepared_files"]["main.py"], sha(self.original_main))
        self.assertEqual(state["original_files"], self.manifest["original_files"])
        self.assert_not_executed()

    def test_theme_update_retains_original_backup_for_later_restore(self):
        first = installer.instalar(self.app)
        new_module = b"# NOVA REVISAO FICTICIA\n" + self.plugin
        (self.package / "integracao" / installer.PLUGIN_NAME).write_bytes(new_module)
        self.package_before = snapshot(self.package)
        second = installer.instalar(self.app)
        self.assertNotEqual(first, second)
        self.assertEqual((second / installer.PLUGIN_NAME).read_bytes(), self.plugin)
        self.assertEqual(self.state()["native_interface"]["backup_dir"], first.name)
        self.assertEqual(self.state()["native_interface"]["last_backup_dir"], second.name)
        installer.restaurar(self.app)
        self.assertEqual((self.app / "main.py").read_bytes(), self.original_main)
        self.assertFalse((self.app / installer.PLUGIN_NAME).exists())
        self.assert_private_preserved()

    def test_web_update_and_native_restore_preserve_each_others_files(self):
        installer.instalar(self.app)
        native = (self.app / installer.PLUGIN_NAME).read_bytes()
        patched_main = (self.app / "main.py").read_bytes()
        web_updater.atualizar(self.app)
        self.assertEqual((self.app / installer.PLUGIN_NAME).read_bytes(), native)
        self.assertEqual((self.app / "main.py").read_bytes(), patched_main)
        latest = self.state()
        self.assertIsNone(installer.instalar(self.app))
        installer.restaurar(self.app)
        state = self.state()
        for relative in web_updater.FILES:
            self.assertEqual(state["prepared_files"][relative], latest["prepared_files"][relative])
            self.assertEqual(sha((self.app / relative).read_bytes()), latest["prepared_files"][relative])
        self.assertEqual(state["interface_backup"], latest["interface_backup"])
        self.assert_private_preserved()

    def test_cli_updates_bridge_after_native_preflight_then_installs(self):
        def update(app):
            self.assertEqual((self.app / "main.py").read_bytes(), self.original_main)
            self.assertFalse((self.app / installer.PLUGIN_NAME).exists())
            return web_updater.atualizar(app)

        with patch.object(sys, "argv", ["instalar_interface_nativa.py", "--pasta", str(self.app), "--atualizar-ponte"]), \
                patch.object(installer.atualizador_web, "atualizar", side_effect=update) as web, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(installer.main(), 0)
        web.assert_called_once_with(self.app)
        self.assertIn(installer.NATIVE_IMPORT, (self.app / "main.py").read_bytes())
        self.assertIn("native_interface", self.state())
        for name in web_updater.FILES:
            self.assertEqual(sha((self.app / name).read_bytes()), self.state()["prepared_files"][name])
        self.assert_private_preserved()

    def test_cli_does_not_update_bridge_when_native_preflight_refuses(self):
        (self.app / "main.py").write_bytes(self.original_main + b"\r\n# EDICAO PESSOAL\r\n")
        before = snapshot(self.app)
        with patch.object(sys, "argv", ["instalar_interface_nativa.py", "--pasta", str(self.app), "--atualizar-ponte"]), \
                patch.object(installer.atualizador_web, "atualizar") as web, \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(installer.main(), 1)
        web.assert_not_called()
        self.assertEqual(snapshot(self.app), before)
        self.assert_not_executed()

    def test_cli_restore_skips_optional_web_update(self):
        installer.instalar(self.app)
        with patch.object(sys, "argv", ["instalar_interface_nativa.py", "--pasta", str(self.app), "--restaurar", "--atualizar-ponte"]), \
                patch.object(installer.atualizador_web, "atualizar") as web, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(installer.main(), 0)
        web.assert_not_called()
        self.assertEqual((self.app / "main.py").read_bytes(), self.original_main)
        self.assert_private_preserved()

    def test_modified_native_files_or_backup_refuse_restore_without_changes(self):
        original_backup = installer.instalar(self.app)
        for path in (self.app / "main.py", self.app / installer.PLUGIN_NAME,
                     original_backup / "main.py"):
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_bytes(original + b"\n# EDICAO PESSOAL FICTICIA\n")
                self.assert_refused(installer.restaurar)
                path.write_bytes(original)
        for name in ("../fora", original_backup.name + "\\..", original_backup.name + ":stream",
                     original_backup.name + ".", original_backup.name + " "):
            with self.subTest(backup_name=name):
                state = self.state()
                state["native_interface"]["backup_dir"] = name
                self.marker.write_bytes(installer._dump(state))
                self.assert_refused(installer.restaurar)

    def test_personal_edit_after_preflight_is_preserved_without_writes(self):
        preflight = installer._installation_inputs
        personal_main = self.original_main + b"\r\n# EDICAO CONCORRENTE FICTICIA\r\n"

        def edit_after_preflight(app):
            inputs = preflight(app)
            (self.app / "main.py").write_bytes(personal_main)
            return inputs

        with patch.object(installer, "_installation_inputs", side_effect=edit_after_preflight):
            with self.assertRaisesRegex(RuntimeError, "mudou"):
                installer.instalar(self.app)
        self.assertEqual((self.app / "main.py").read_bytes(), personal_main)
        self.assertEqual(self.marker.read_bytes(), self.before[installer.preparacao.MARKER])
        self.assertFalse((self.app / installer.PLUGIN_NAME).exists())
        self.assertEqual(self.backups(), [])
        self.assert_not_executed()

    def test_rollback_preserves_concurrent_edits_and_restores_other_owned_files(self):
        for edited, failed in (("main.py", installer.preparacao.MARKER),
                               (installer.PLUGIN_NAME, "main.py")):
            with self.subTest(edited=edited):
                personal = b"# EDICAO CONCORRENTE FICTICIA\n"
                replace = installer.os.replace

                def fail(source, destination):
                    if Path(destination) == self.app / failed:
                        (self.app / edited).write_bytes(personal)
                        raise OSError("FALHA FICTICIA APOS EDICAO CONCORRENTE")
                    return replace(source, destination)

                with patch.object(installer.os, "replace", side_effect=fail):
                    with self.assertRaisesRegex(RuntimeError, "concorrente"):
                        installer.instalar(self.app)
                self.assertEqual((self.app / edited).read_bytes(), personal)
                self.assertEqual(self.marker.read_bytes(), self.before[installer.preparacao.MARKER])
                if edited == "main.py":
                    self.assertFalse((self.app / installer.PLUGIN_NAME).exists())
                    (self.app / "main.py").write_bytes(self.original_main)
                else:
                    self.assertEqual((self.app / "main.py").read_bytes(), self.original_main)
                    (self.app / installer.PLUGIN_NAME).unlink()
                self.assert_not_executed()

    def failure_once(self, relative, action):
        before = snapshot(self.app)
        backups = self.backups()
        replace = installer.os.replace
        failed = False

        def fail(source, destination):
            nonlocal failed
            if Path(destination) == self.app / relative and not failed:
                failed = True
                raise OSError("FALHA FICTICIA DE ESCRITA")
            return replace(source, destination)

        with patch.object(installer.os, "replace", side_effect=fail):
            with self.assertRaises(OSError):
                action(self.app)
        self.assertTrue(failed)
        added = set(self.backups()) - set(backups)
        self.assertEqual(len(added), 1)
        added_name = next(iter(added)).name
        after = {name: data for name, data in snapshot(self.app).items()
                 if not name.startswith(added_name + "/")}
        self.assertEqual(after, before)
        self.assert_not_executed()

    def test_failed_new_module_write_keeps_every_original_file(self):
        self.failure_once(installer.PLUGIN_NAME, installer.instalar)

    def test_failed_main_write_removes_only_the_module_created_by_installer(self):
        self.failure_once("main.py", installer.instalar)

    def test_failed_manifest_write_rolls_back_main_and_new_module(self):
        self.failure_once(installer.preparacao.MARKER, installer.instalar)

    def test_failed_restore_manifest_keeps_installed_main_and_module(self):
        installer.instalar(self.app)
        self.failure_once(installer.preparacao.MARKER, installer.restaurar)

    def test_git_and_link_paths_are_refused(self):
        (self.app / ".git").write_bytes(b"gitdir: FICTICIO")
        self.assert_refused()
        (self.app / ".git").unlink()
        with patch.object(installer.preparacao, "REPOSITORY_ROOT", self.root):
            self.assert_refused()
        ui = self.app / "ui.py"
        ui.unlink()
        outside = self.root / "ui fora ficticia.py"
        outside.write_bytes(self.original_ui)
        try:
            ui.symlink_to(outside)
        except OSError as error:
            ui.write_bytes(self.original_ui)
            self.skipTest(f"Sem permissao para link sintetico: {error}")
        before = snapshot(self.app)
        with self.assertRaises((OSError, RuntimeError)):
            installer.instalar(self.app)
        self.assertEqual(snapshot(self.app), before)
        self.assertTrue(ui.is_symlink())
        self.assertEqual(outside.read_bytes(), self.original_ui)
        self.assert_not_executed()


if __name__ == "__main__":
    unittest.main()
