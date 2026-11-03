"""Testes locais da correcao, sem Windows, DUX ou execucao do configurador."""

import contextlib
import ctypes
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch


HELPER = Path(__file__).resolve().parents[1] / "tools" / "aplicar_etapa201.py"
SPEC = importlib.util.spec_from_file_location("aplicar_etapa201", HELPER)
etapa201 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(etapa201)
TARGET_NAME = "jarvis_configurar_datas_controladoria.py"
BACKUP_NAME = "jarvis_configurar_datas_controladoria_antes_correcao.py"


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix="jarvis-etapa201-test-")
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.target = self.root / TARGET_NAME
        self.backup = self.root / BACKUP_NAME

    def write_target(self, source=None, *, bom=False, crlf=False):
        if source is None:
            source = "import ctypes\nimport time\n\n" + etapa201.ANTIGO
        data = source.replace("\n", "\r\n").encode("utf-8") if crlf else source.encode("utf-8")
        if bom:
            data = b"\xef\xbb\xbf" + data
        self.target.write_bytes(data)
        return data

    def apply(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            backup = etapa201.aplicar(self.target)
        return backup, output.getvalue()

    def assert_refuses_unchanged(self, expected):
        before = self.target.read_bytes() if self.target.exists() else None
        with self.assertRaisesRegex((RuntimeError, SyntaxError, OSError), expected):
            self.apply()
        if before is not None:
            self.assertEqual(self.target.read_bytes(), before)
        self.assertFalse(self.backup.exists())
        self.assertEqual(list(self.root.glob(".etapa201-*")), [])

    def test_applies_once_without_executing_target(self):
        marker = self.root / "NAO_DEVE_EXISTIR"
        preface = "from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('executado')\nraise AssertionError('NAO EXECUTAR')\n\n"
        source = preface + etapa201.ANTIGO + "\n# fim\n"
        original = self.write_target(source)
        backup, output = self.apply()
        self.assertEqual(backup, self.backup)
        self.assertEqual(self.backup.read_bytes(), original)
        self.assertEqual(self.target.read_text(), source.replace(etapa201.ANTIGO, etapa201.NOVO, 1))
        self.assertFalse(marker.exists())
        self.assertIn("LEITURA DAS DATAS CORRIGIDA", output)
        self.assertIn("CODIGO VALIDADO", output)
        self.assertEqual(list(self.root.glob(".etapa201-*")), [])

    def test_backup_preserves_bom_crlf_and_all_original_bytes(self):
        source = "# configuração\nimport ctypes\n\n" + etapa201.ANTIGO
        original = self.write_target(source, bom=True, crlf=True)
        self.apply()
        self.assertEqual(self.backup.read_bytes(), original)
        self.assertEqual(self.target.read_bytes(), source.replace(etapa201.ANTIGO, etapa201.NOVO, 1).encode("utf-8"))

    def test_preserves_synthetic_date_values_and_fill_code(self):
        preface = (
            'DATA_INICIAL = "01/10/2026"\n'
            'DATA_FINAL = "31/10/2026"\n\n'
            'def preencher(hwnd, data):\n'
            '    raise AssertionError("Preenchimento nao deve executar")\n\n'
        )
        source = preface + etapa201.ANTIGO
        self.write_target(source)
        self.apply()
        self.assertEqual(self.target.read_text(), preface + etapa201.NOVO)

    def test_existing_backup_is_never_overwritten(self):
        original = self.write_target()
        existing = b"backup anterior\r\n"
        self.backup.write_bytes(existing)
        with self.assertRaisesRegex(RuntimeError, "Backup ja existe"):
            self.apply()
        self.assertEqual(self.target.read_bytes(), original)
        self.assertEqual(self.backup.read_bytes(), existing)

    def test_missing_old_snippet_refuses_without_changes(self):
        self.write_target("def ler(hwnd):\n    return 'outro codigo'\n")
        self.assert_refuses_unchanged("exatamente uma vez")

    def test_multiple_old_snippets_refuse_without_changes(self):
        self.write_target(etapa201.ANTIGO + "\n" + etapa201.ANTIGO)
        self.assert_refuses_unchanged("exatamente uma vez")

    def test_invalid_syntax_refuses_before_backup(self):
        self.write_target(etapa201.ANTIGO + "\nif !!!\n")
        self.assert_refuses_unchanged("invalid syntax")

    def test_missing_target_refuses_without_creating_files(self):
        self.assert_refuses_unchanged("Configurador nao encontrado")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_wrong_filename_refuses(self):
        other = self.root / "outro.py"
        other.write_text(etapa201.ANTIGO)
        with self.assertRaisesRegex(RuntimeError, "Informe jarvis_"):
            etapa201.aplicar(other)
        self.assertEqual(other.read_text(), etapa201.ANTIGO)

    def test_symlink_target_refuses_without_touching_real_file(self):
        real = self.root / "real.py"
        real.write_text(etapa201.ANTIGO)
        self.target.symlink_to(real)
        with self.assertRaisesRegex(RuntimeError, "configurador e um link"):
            self.apply()
        self.assertEqual(real.read_text(), etapa201.ANTIGO)
        self.assertFalse(self.backup.exists())

    def test_cli_fails_nonzero_for_missing_target(self):
        result = subprocess.run([sys.executable, str(HELPER), str(self.target)], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("ERRO: Configurador nao encontrado", result.stderr)
        self.assertNotIn("CODIGO VALIDADO", result.stdout)

    def test_cli_success_does_not_execute_target(self):
        source = "raise AssertionError('NAO EXECUTAR')\n\n" + etapa201.ANTIGO
        original = self.write_target(source)
        result = subprocess.run([sys.executable, str(HELPER)], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CODIGO VALIDADO", result.stdout)
        self.assertEqual(self.backup.read_bytes(), original)

    def test_repeated_application_refuses_and_preserves_both_files(self):
        self.write_target()
        self.apply()
        target_before = self.target.read_bytes()
        backup_before = self.backup.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "Backup ja existe"):
            self.apply()
        self.assertEqual(self.target.read_bytes(), target_before)
        self.assertEqual(self.backup.read_bytes(), backup_before)

    def test_replace_failure_keeps_target_and_backup_and_removes_temp(self):
        original = self.write_target()
        with patch.object(etapa201.os, "replace", side_effect=PermissionError("arquivo bloqueado")):
            with self.assertRaisesRegex(PermissionError, "arquivo bloqueado"):
                self.apply()
        self.assertEqual(self.target.read_bytes(), original)
        self.assertEqual(self.backup.read_bytes(), original)
        self.assertEqual(list(self.root.glob(".etapa201-*")), [])


class ReadRetryTests(unittest.TestCase):
    def setup_reader(self, replies, exists=None):
        replies = iter(replies)

        def send(hwnd, message, count, pointer, flags, timeout, result):
            self.assertEqual((hwnd, message, count, flags, timeout), (123, 0x000D, 512, 0x0002, 1000))
            ok, value = next(replies)
            data = ctypes.create_unicode_buffer(value)
            ctypes.memmove(pointer, data, ctypes.sizeof(data))
            return ok

        self.send = Mock(side_effect=send)
        self.sleep = Mock()
        self.window = Mock(side_effect=exists) if exists else Mock(return_value=True)
        namespace = {
            "ctypes": ctypes,
            "enviar": self.send,
            "win32gui": types.SimpleNamespace(IsWindow=self.window),
            "time": types.SimpleNamespace(sleep=self.sleep),
            "print": Mock(),
        }
        exec(compile(etapa201.NOVO, "<etapa-201-NOVO>", "exec"), namespace)
        return namespace["ler"]

    def test_first_success_reads_only_once(self):
        read = self.setup_reader([(1, "01/10/2026")])
        self.assertEqual(read(123), "01/10/2026")
        self.assertEqual(self.send.call_count, 1)
        self.sleep.assert_not_called()

    def test_empty_and_timeout_then_success(self):
        read = self.setup_reader([(0, ""), (1, " "), (1, "31/10/2026")])
        self.assertEqual(read(123), "31/10/2026")
        self.assertEqual(self.send.call_count, 3)
        self.assertEqual(self.sleep.call_count, 2)
        self.assertTrue(all(args == ((0.4,), {}) for args in self.sleep.call_args_list))

    def test_timeout_with_nonempty_buffer_is_not_accepted(self):
        read = self.setup_reader([(0, "30/11/2026"), (1, "31/10/2026")])
        self.assertEqual(read(123), "31/10/2026")
        self.assertEqual(self.send.call_count, 2)
        self.sleep.assert_called_once_with(0.4)

    def test_five_empty_successful_responses_raise(self):
        read = self.setup_reader([(1, " ")] * 5)
        with self.assertRaisesRegex(RuntimeError, "apos 5 tentativas"):
            read(123)
        self.assertEqual(self.send.call_count, 5)
        self.assertEqual(self.window.call_count, 5)

    def test_retry_budget_is_independent_for_each_read(self):
        read = self.setup_reader(
            [(0, "")] * 4 + [(1, "01/10/2026"), (1, "31/10/2026")]
        )
        self.assertEqual(read(123), "01/10/2026")
        self.assertEqual(read(123), "31/10/2026")
        self.assertEqual(self.send.call_count, 6)
        self.assertEqual(self.sleep.call_count, 4)

    def test_fifth_attempt_succeeds(self):
        read = self.setup_reader([(0, "")] * 4 + [(1, "31/10/2026")])
        self.assertEqual(read(123), "31/10/2026")
        self.assertEqual(self.send.call_count, 5)
        self.assertEqual(self.sleep.call_count, 4)

    def test_exhaustion_raises_after_five(self):
        read = self.setup_reader([(0, "")] * 5)
        with self.assertRaisesRegex(RuntimeError, "apos 5 tentativas"):
            read(123)
        self.assertEqual(self.send.call_count, 5)
        self.assertEqual(self.sleep.call_count, 5)

    def test_destroyed_control_fails_without_send(self):
        read = self.setup_reader([], [False])
        with self.assertRaisesRegex(RuntimeError, "nao existe mais"):
            read(123)
        self.send.assert_not_called()

    def test_destroyed_after_retry_stops(self):
        read = self.setup_reader([(0, "")], [True, False])
        with self.assertRaisesRegex(RuntimeError, "nao existe mais"):
            read(123)
        self.assertEqual(self.send.call_count, 1)

    def test_trims_read_value(self):
        read = self.setup_reader([(1, " 31/10/2026 ")])
        self.assertEqual(read(123), "31/10/2026")


if __name__ == "__main__":
    unittest.main(verbosity=2)
