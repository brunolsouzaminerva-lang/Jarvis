"""Preparo de integracao em arvores sinteticas; nunca usa a pasta corporativa."""

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "Preparar-IntegracaoJarvis.ps1"
PWSH = os.environ.get("JARVIS_PWSH") or shutil.which("pwsh")
REF = "codex/integracao-etapa4"
CONFIGURATOR = "jarvis_configurar_datas_controladoria.py"


def inventory(root):
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        result[relative] = (
            "directory" if path.is_dir()
            else hashlib.sha256(path.read_bytes()).hexdigest()
        )
    return result


@unittest.skipUnless(PWSH and shutil.which("git"), "Requer PowerShell 7 e Git")
class WindowsPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory(prefix="jarvis-remote-sintetico-")
        cls.remote = Path(cls.shared.name) / "remote"
        cls.env = os.environ.copy()
        cls.env.update({
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        })
        subprocess.run(
            ["git", "init", "--initial-branch=" + REF, str(cls.remote)],
            check=True, capture_output=True, env=cls.env,
        )
        (cls.remote / CONFIGURATOR).write_text(
            '# Arquivo de desenvolvimento inteiramente sintetico.\n'
            'DATA_INICIAL = "01/10/2026"\nDATA_FINAL = "31/10/2026"\n',
            encoding="utf-8",
        )
        (cls.remote / "README.md").write_text("Repositorio sintetico\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(cls.remote), "add", "."],
                       check=True, capture_output=True, env=cls.env)
        subprocess.run(
            ["git", "-C", str(cls.remote), "-c", "user.name=Teste Sintetico",
             "-c", "user.email=sintetico@example.invalid", "commit", "-m", "fixture"],
            check=True, capture_output=True, env=cls.env,
        )

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="Jarvis sintetico acao ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "original"
        self.backups = self.root / "backups"
        self.workspace = self.root / "trabalho"
        self.source.mkdir()
        self.marker = self.root / "CODIGO_NAO_DEVE_EXECUTAR"
        (self.source / CONFIGURATOR).write_text(
            "from pathlib import Path\n"
            f"Path({str(self.marker)!r}).write_text('executado')\n"
            "raise RuntimeError('NAO EXECUTAR O CONFIGURADOR')\n",
            encoding="utf-8",
        )
        (self.source / ".git").mkdir()
        (self.source / ".git" / "metadata").write_bytes(b"METADADOS GIT SINTETICOS\x00")
        (self.source / ".env").write_text("EXEMPLO_SEM_CREDENCIAL=1\n", encoding="utf-8")
        (self.source / ".arquivo_oculto").write_bytes(b"\xef\xbb\xbfSINTETICO\r\n")
        if os.name == "nt":
            subprocess.run(["attrib", "+H", str(self.source / ".arquivo_oculto")],
                           check=True, capture_output=True)
        (self.source / "vazio").mkdir()
        (self.source / "histórico").mkdir()
        (self.source / "histórico" / "dia_sintetico.txt").write_text(
            "Historico preservado\n", encoding="utf-8")
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            # Fixture de preservacao de bytes, nao um teste de calculo do Excel.
            archive.writestr("xl/worksheets/BASE_DUX.xml", "<linha1>Cabecalho sintetico</linha1>")
            archive.writestr("xl/pivotTables/Realizado_Diario.xml", "<pivot>Exemplo</pivot>")
            archive.writestr("historico.txt", "Historico diario sintetico")
        (self.source / "GGO_SINTETICO.xlsx").write_bytes(data.getvalue())
        self.before = inventory(self.source)

    def run_script(self, *, source=None, backups=None, workspace=None, ref=REF,
                   remote=None, authorized=None, synthetic=True, env=None):
        command = [str(PWSH), "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(SCRIPT),
                   "-SourcePath", str(source or self.source),
                   "-BackupRoot", str(backups or self.backups),
                   "-WorkspaceRoot", str(workspace or self.workspace),
                   "-RepositoryUrl", str(remote or self.remote), "-DevelopmentRef", ref]
        if synthetic:
            command.append("-SyntheticTest")
        if authorized is not None:
            command.extend(["-AuthorizedRelativePaths", authorized])
        return subprocess.run(command, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=60,
                              env=env or self.env, cwd=self.root)

    def state(self):
        return json.loads((self.workspace / "preparation-state.json").read_text(encoding="utf-8-sig"))

    def assert_original_preserved(self):
        self.assertEqual(inventory(self.source), self.before)
        self.assertFalse(self.marker.exists(), "O configurador sintetico foi executado")

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_original_preserved()

    def assert_failure(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_original_preserved()

    def test_complete_backup_and_private_comparison_without_importing_source(self):
        result = self.run_script()
        self.assert_success(result)
        state = self.state()
        self.assertEqual(state["Status"], "Ready")
        backup = Path(state["BackupPath"])
        self.assertEqual(inventory(backup / "source"), self.before)
        self.assertTrue((backup / "manifest.json").is_file())
        self.assertTrue((backup / "completed.json").is_file())
        clone = self.workspace / "repository"
        self.assertFalse((clone / "GGO_SINTETICO.xlsx").exists())
        self.assertFalse((clone / ".env").exists())
        self.assertNotIn("NAO EXECUTAR", (clone / CONFIGURATOR).read_text())
        status = subprocess.run(["git", "-C", str(clone), "status", "--porcelain"],
                                capture_output=True, text=True, check=True, env=self.env)
        self.assertEqual(status.stdout, "")
        self.assertTrue((self.workspace / "review" / "comparison.json").is_file())
        diffs = list((self.workspace / "review" / "diffs").glob("*.diff"))
        self.assertEqual(len(diffs), 1)
        self.assertIn("NAO EXECUTAR", diffs[0].read_text(encoding="utf-8-sig"))
        self.assertNotIn("NAO EXECUTAR", result.stdout + result.stderr)

    def test_identical_repeat_reuses_verified_backup_and_commit(self):
        self.assert_success(self.run_script())
        first = self.state()
        backup_files = inventory(self.backups)
        self.assert_success(self.run_script())
        second = self.state()
        self.assertEqual(first["BackupPath"], second["BackupPath"])
        self.assertEqual(first["Commit"], second["Commit"])
        self.assertEqual(backup_files, inventory(self.backups))

    def test_dirty_clone_is_preserved_and_not_reset(self):
        self.assert_success(self.run_script())
        readme = self.workspace / "repository" / "README.md"
        readme.write_text("Edicao manual sintetica\n", encoding="utf-8")
        self.assert_failure(self.run_script())
        self.assertEqual(readme.read_text(), "Edicao manual sintetica\n")

    def test_modified_original_requires_new_workspace(self):
        self.assert_success(self.run_script())
        old_state = self.state()
        (self.source / "novo_sintetico.txt").write_text("Nova versao\n", encoding="utf-8")
        self.before = inventory(self.source)
        self.assert_failure(self.run_script())
        self.assertEqual(self.state()["BackupPath"], old_state["BackupPath"])
        self.assertEqual(inventory(Path(old_state["BackupPath"]) / "source"),
                         {k: v for k, v in self.before.items() if k != "novo_sintetico.txt"})

    def test_corrupted_backup_is_not_silently_replaced(self):
        self.assert_success(self.run_script())
        copied = Path(self.state()["BackupPath"]) / "source" / CONFIGURATOR
        copied.write_text("Backup corrompido sintetico", encoding="utf-8")
        self.assert_failure(self.run_script())
        self.assertEqual(copied.read_text(), "Backup corrompido sintetico")

    def test_existing_foreign_workspace_is_not_overwritten(self):
        self.workspace.mkdir()
        marker = self.workspace / "trabalho_do_usuario.txt"
        marker.write_text("Preservar", encoding="utf-8")
        self.assert_failure(self.run_script())
        self.assertEqual(marker.read_text(), "Preservar")

    def test_overlapping_destinations_refuse_before_writing_source(self):
        for params in ({"backups": self.source / "backup"},
                       {"workspace": self.source / "trabalho"},
                       {"workspace": self.backups / "trabalho"}):
            with self.subTest(params=params):
                self.assert_failure(self.run_script(**params))

    def test_missing_source_does_not_create_a_workspace(self):
        self.assert_failure(self.run_script(source=self.root / "inexistente"))
        self.assertFalse(self.workspace.exists())

    def test_git_worktree_pointer_refuses_incomplete_backup(self):
        shutil.rmtree(self.source / ".git")
        (self.source / ".git").write_text("gitdir: ../metadados_externos", encoding="utf-8")
        self.before = inventory(self.source)
        self.assert_failure(self.run_script())

    def test_symlink_is_not_followed(self):
        outside = self.root / "fora"
        outside.mkdir()
        (outside / "nao_copiar.txt").write_text("Sintetico externo", encoding="utf-8")
        link = self.source / "atalho"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Sem suporte/permissao para symlink: {error}")
        before = (self.source / CONFIGURATOR).read_bytes()
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.source / CONFIGURATOR).read_bytes(), before)
        self.assertFalse(self.marker.exists())
        self.assertFalse(self.workspace.exists())

    def test_comparison_rejects_traversal_and_non_code(self):
        for relative in ("../fora.py", ".env", "GGO_SINTETICO.xlsx", str(self.source / CONFIGURATOR)):
            with self.subTest(relative=relative):
                self.assert_failure(self.run_script(authorized=relative))

    def test_local_remote_requires_explicit_synthetic_switch(self):
        self.assert_failure(self.run_script(synthetic=False))

    def test_missing_development_ref_preserves_source_and_completed_backups(self):
        self.assert_failure(self.run_script(ref="codex/branch-inexistente"))
        for marker in self.backups.glob("*/completed.json"):
            self.assertEqual(inventory(marker.parent / "source"), self.before)

    def test_global_hooks_and_external_diff_are_not_executed(self):
        hooks = self.root / "hooks"
        hooks.mkdir()
        hook_marker = self.root / "HOOK_NAO_DEVE_EXECUTAR"
        hook = hooks / "post-checkout"
        hook.write_text(f"#!/bin/sh\nprintf executado > '{hook_marker.as_posix()}'\n", encoding="utf-8")
        hook.chmod(0o755)
        configuration = self.root / "gitconfig"
        subprocess.run(["git", "config", "--file", str(configuration), "core.hooksPath", str(hooks)],
                       check=True, capture_output=True, env=self.env)
        env = self.env.copy()
        env["GIT_CONFIG_GLOBAL"] = str(configuration)
        env["GIT_EXTERNAL_DIFF"] = str(hook)
        self.assert_success(self.run_script(env=env))
        self.assertFalse(hook_marker.exists())

    def test_configured_git_filters_do_not_execute_during_clone_or_status(self):
        filtered_remote = self.root / "remote-com-atributos"
        subprocess.run(["git", "clone", "--quiet", str(self.remote), str(filtered_remote)],
                       check=True, capture_output=True, env=self.env)
        (filtered_remote / ".gitattributes").write_text("*.py filter=corporativo\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(filtered_remote), "add", ".gitattributes"],
                       check=True, capture_output=True, env=self.env)
        subprocess.run(
            ["git", "-C", str(filtered_remote), "-c", "user.name=Teste Sintetico",
             "-c", "user.email=sintetico@example.invalid", "commit", "-m", "atributos sinteticos"],
            check=True, capture_output=True, env=self.env,
        )
        for kind in ("clean", "smudge", "process"):
            with self.subTest(filter=kind):
                marker = self.root / ("FILTRO_NAO_DEVE_EXECUTAR_" + kind)
                configuration = self.root / ("gitconfig-" + kind)
                command = "printf executado > " + shlex.quote(marker.as_posix()) + "; cat"
                subprocess.run(
                    ["git", "config", "--file", str(configuration), "filter.corporativo." + kind, command],
                    check=True, capture_output=True, env=self.env,
                )
                subprocess.run(
                    ["git", "config", "--file", str(configuration), "filter.corporativo.required", "true"],
                    check=True, capture_output=True, env=self.env,
                )
                env = self.env.copy()
                env["GIT_CONFIG_GLOBAL"] = str(configuration)
                workspace = self.root / ("trabalho-filtro-" + kind)
                self.assert_success(self.run_script(remote=filtered_remote, workspace=workspace, env=env))
                self.assertFalse(marker.exists())
                self.assert_success(self.run_script(remote=filtered_remote, workspace=workspace, env=env))
                self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
