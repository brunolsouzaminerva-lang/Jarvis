"""Preparacao da interface em copias pessoais inteiramente sinteticas."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "preparador_interface_sintetico", ROOT / "tools" / "preparar_interface_local.py"
)
preparador = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = preparador
with patch.object(sys, "path", [str(ROOT / "tools"), *sys.path]):
    SPEC.loader.exec_module(preparador)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def snapshot(root):
    """Nao segue links; compara conteudo, nomes e diretorios vazios."""
    root = Path(root)
    if root.is_symlink():
        return {".": ("link", os.readlink(root))}
    if not root.exists():
        return None
    if root.is_file():
        return {".": ("file", digest(root.read_bytes()))}
    result = {}
    for directory, child_dirs, child_files in os.walk(root, followlinks=False):
        for name in sorted([*child_dirs, *child_files]):
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                result[relative] = ("link", os.readlink(path))
            elif path.is_dir():
                result[relative] = ("directory",)
            else:
                result[relative] = ("file", digest(path.read_bytes()))
        child_dirs[:] = [name for name in child_dirs if not (Path(directory) / name).is_symlink()]
    return result


class PersonalInterfacePreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jarvis-interface-sintetica-")
        self.addCleanup(self.temp.cleanup)
        # Windows TEMP may use the RUNNER~1 short alias; the builder resolves it.
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "origem pessoal"
        self.target = self.root / "nova copia"
        self.development = self.root / "distribuicao de desenvolvimento"
        self.source.mkdir()
        self.development.mkdir()
        self.marker = self.root / "CODIGO_NAO_DEVE_EXECUTAR"
        self.private_example = "VALOR_FICTICIO_SEM_CREDENCIAL_REAL"
        self.original_bridge = (
            "from pathlib import Path\n"
            f"Path({str(self.marker)!r}).write_text('ponte executada')\n"
            "raise RuntimeError('PONTE ORIGINAL NAO DEVE EXECUTAR')\n"
        ).encode("utf-8")
        (self.source / "main.py").write_text(
            "from pathlib import Path\n"
            f"Path({str(self.marker)!r}).write_text('main executado')\n"
            "raise RuntimeError('MAIN NAO DEVE EXECUTAR')\n",
            encoding="utf-8",
        )
        (self.source / "browser_audio_bridge.py").write_bytes(self.original_bridge)
        (self.source / "config").mkdir()
        (self.source / "config" / "api_keys.json").write_text(
            json.dumps({"fixture": self.private_example}), encoding="utf-8"
        )
        (self.source / ".env").write_text(
            "FIXTURE_LOCAL=" + self.private_example + "\n", encoding="utf-8"
        )
        (self.source / "diretorio vazio").mkdir()
        (self.source / "historico sintetico").mkdir()
        (self.source / "historico sintetico" / "exemplo.bin").write_bytes(bytes(range(256)))

        (self.development / "integracao").mkdir()
        self.replacement_bridge = (
            "raise RuntimeError('OVERLAY NAO DEVE EXECUTAR DURANTE PREPARO')\n"
        ).encode("utf-8")
        (self.development / "integracao" / "browser_audio_bridge.py").write_bytes(
            self.replacement_bridge
        )
        (self.development / "interface-oficial").mkdir()
        for name in preparador.ASSETS:
            (self.development / "interface-oficial" / name).write_text(
                "/* ASSET INTEIRAMENTE SINTETICO: " + name + " */\n", encoding="utf-8"
            )
        self.addCleanup(patch.stopall)
        patch.object(preparador, "ORIGINAL_BRIDGE_SHA256", digest(self.original_bridge)).start()
        patch.object(preparador, "REPOSITORY_ROOT", self.development).start()
        self.before = snapshot(self.source)

    def prepare(self, source=None, target=None, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return preparador.preparar(source or self.source, target or self.target, **kwargs)

    def assert_original_preserved(self):
        self.assertEqual(snapshot(self.source), self.before)
        self.assertFalse(self.marker.exists(), "Codigo sintetico foi executado")

    def assert_refused(self, source=None, target=None, **kwargs):
        source = source or self.source
        target = target or self.target
        source_before = snapshot(source)
        target_before = snapshot(target)
        with self.assertRaises((OSError, RuntimeError, ValueError, SyntaxError)):
            self.prepare(source, target, **kwargs)
        self.assertEqual(snapshot(source), source_before)
        self.assertEqual(snapshot(target), target_before)
        self.assertFalse(self.marker.exists())

    def symlink(self, link, destination, *, directory=True):
        try:
            link.symlink_to(destination, target_is_directory=directory)
        except OSError as error:
            self.skipTest(f"Sem permissao para criar link sintetico: {error}")

    def test_prepares_a_separate_copy_without_executing_any_application(self):
        self.assertEqual(self.prepare(), self.target)
        self.assert_original_preserved()
        self.assertEqual((self.target / "main.py").read_bytes(), (self.source / "main.py").read_bytes())
        self.assertEqual((self.target / "browser_audio_bridge.py").read_bytes(), self.replacement_bridge)
        self.assertEqual((self.target / preparador.BACKUP).read_bytes(), self.original_bridge)
        self.assertTrue((self.target / "diretorio vazio").is_dir())
        self.assertEqual((self.target / "historico sintetico" / "exemplo.bin").read_bytes(), bytes(range(256)))
        manifest = json.loads((self.target / preparador.MARKER).read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "preparado")
        self.assertFalse(manifest["etapa201"])
        self.assertEqual(manifest["original_files"]["browser_audio_bridge.py"], digest(self.original_bridge))
        self.assertEqual(manifest["prepared_files"]["browser_audio_bridge.py"], digest(self.replacement_bridge))

    def test_private_configuration_stays_local_and_outside_the_served_assets(self):
        self.prepare()
        self.assert_original_preserved()
        for relative in (".env", "config/api_keys.json"):
            self.assertEqual((self.target / relative).read_bytes(), (self.source / relative).read_bytes())
        assets = self.target / "interface-oficial"
        self.assertEqual({path.name for path in assets.iterdir()}, set(preparador.ASSETS))
        for path in assets.iterdir():
            self.assertNotIn(self.private_example, path.read_text(encoding="utf-8"))
        manifest = (self.target / preparador.MARKER).read_text(encoding="utf-8")
        self.assertNotIn(self.private_example, manifest)

    def test_repeating_preparation_never_overwrites_the_working_copy(self):
        self.prepare()
        personal_edit = self.target / "minha edicao.txt"
        personal_edit.write_text("Preservar edicao pessoal sintetica", encoding="utf-8")
        self.assert_refused()
        self.assert_original_preserved()

    def test_existing_empty_or_file_destination_is_not_overwritten(self):
        for name, is_file in (("diretorio existente", False), ("arquivo existente", True)):
            with self.subTest(name=name):
                target = self.root / name
                if is_file:
                    target.write_bytes(b"PRESERVAR")
                else:
                    target.mkdir()
                self.assert_refused(target=target)
        self.assert_original_preserved()

    def test_source_and_destination_must_not_overlap(self):
        for target in (self.source, self.source / "dentro", self.root):
            with self.subTest(target=target):
                self.assert_refused(target=target)
        self.assert_original_preserved()

    def test_destination_inside_development_repository_is_refused(self):
        self.assert_refused(target=self.development / "copia privada")
        self.assert_original_preserved()

    def test_destination_inside_another_git_checkout_is_refused(self):
        checkout = self.root / "outro repositorio"
        (checkout / ".git").mkdir(parents=True)
        self.assert_refused(target=checkout / "copia privada")
        self.assert_original_preserved()

    def test_git_metadata_in_source_is_refused_before_copying(self):
        (self.source / ".git").mkdir()
        (self.source / ".git" / "fixture-metadata").write_bytes(b"GIT SINTETICO")
        self.before = snapshot(self.source)
        self.assert_refused()
        self.assert_original_preserved()

    def test_missing_main_or_bridge_is_refused_before_creating_a_destination(self):
        for name in ("main.py", "browser_audio_bridge.py"):
            with self.subTest(name=name):
                source = self.root / ("origem sem " + name)
                shutil.copytree(self.source, source)
                (source / name).unlink()
                self.assert_refused(source=source)
        self.assert_original_preserved()

    def test_unknown_bridge_version_is_refused_before_copying(self):
        with patch.object(preparador, "ORIGINAL_BRIDGE_SHA256", "0" * 64):
            self.assert_refused()
        self.assert_original_preserved()

    def test_reserved_names_in_the_source_are_not_overwritten(self):
        for name in ("interface-oficial", preparador.BACKUP, preparador.MARKER):
            with self.subTest(name=name):
                source = self.root / ("origem reservada " + name)
                shutil.copytree(self.source, source)
                reserved = source / name
                if name == "interface-oficial":
                    reserved.mkdir()
                else:
                    reserved.write_text("PRESERVAR", encoding="utf-8")
                self.assert_refused(source=source)
        self.assert_original_preserved()

    def test_missing_development_assets_are_refused_before_creating_a_copy(self):
        (self.development / "interface-oficial" / "voice.js").unlink()
        self.assert_refused()
        self.assert_original_preserved()

    def test_optional_date_fix_changes_only_the_new_copy_and_preserves_backup(self):
        configurator = self.source / "jarvis_configurar_datas_controladoria.py"
        original = (
            "raise RuntimeError('CONFIGURADOR NAO DEVE EXECUTAR')\n\n" + preparador.ANTIGO
        ).encode("utf-8")
        configurator.write_bytes(original)
        self.before = snapshot(self.source)
        self.prepare(corrigir_datas=True)
        self.assert_original_preserved()
        self.assertEqual(
            (self.target / "jarvis_configurar_datas_controladoria_antes_correcao.py").read_bytes(), original
        )
        self.assertIn(preparador.NOVO, (self.target / configurator.name).read_text(encoding="utf-8"))
        state = json.loads((self.target / preparador.MARKER).read_text(encoding="utf-8"))
        self.assertTrue(state["etapa201"])

    def test_unrecognized_date_configurator_refuses_without_creating_a_copy(self):
        configurator = self.source / "jarvis_configurar_datas_controladoria.py"
        configurator.write_text("def ler(hwnd):\n    return 'OUTRA VERSAO'\n", encoding="utf-8")
        self.before = snapshot(self.source)
        self.assert_refused(corrigir_datas=True)
        self.assert_original_preserved()

    def test_copy_failure_keeps_original_and_marks_the_destination_incomplete(self):
        copy2 = shutil.copy2

        def fail_on_bridge(source, target, *args, **kwargs):
            if Path(source) == self.source / "browser_audio_bridge.py":
                raise OSError("Falha de copia inteiramente sintetica")
            return copy2(source, target, *args, **kwargs)

        with patch.object(preparador.shutil, "copy2", side_effect=fail_on_bridge):
            with self.assertRaises(OSError):
                self.prepare()
        self.assert_original_preserved()
        state = json.loads((self.target / preparador.MARKER).read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "incompleto")

    def test_symlink_source_child_and_source_ancestor_are_refused(self):
        outside = self.root / "fora"
        outside.mkdir()
        (outside / "exemplo.txt").write_text("FORA SINTETICO", encoding="utf-8")
        link = self.source / "atalho externo"
        self.symlink(link, outside)
        self.assert_refused()
        link.unlink()
        source_link = self.root / "origem vinculada"
        self.symlink(source_link, self.source)
        self.assert_refused(source=source_link)
        ancestor = self.root / "ancestral vinculado"
        self.symlink(ancestor, self.root)
        self.assert_refused(source=ancestor / self.source.name)
        self.assert_original_preserved()

    def test_dangling_destination_or_linked_destination_ancestor_is_refused(self):
        dangling = self.root / "destino pendente"
        self.symlink(dangling, self.root / "destino inexistente")
        self.assert_refused(target=dangling)
        ancestor = self.root / "destino com ancestral vinculado"
        self.symlink(ancestor, self.root)
        self.assert_refused(target=ancestor / "copia por link")
        self.assert_original_preserved()


if __name__ == "__main__":
    unittest.main()
