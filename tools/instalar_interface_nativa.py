"""Instala a interface Qt moderna somente na copia preparada do Jarvis.

O instalador valida e compila fontes; nunca importa ou executa main.py, ui.py
ou o modulo Qt. A instalacao original, configuracoes e automacoes ficam intactas.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid

try:
    from . import preparar_interface_local as preparacao
    from . import atualizar_interface_local as atualizador_web
    from .criar_atalho_local import _outside_git, _safe_path
except ImportError:
    import preparar_interface_local as preparacao
    import atualizar_interface_local as atualizador_web
    from criar_atalho_local import _outside_git, _safe_path


MAIN_ORIGINAL_SHA256 = "009f1189b5f7cf0ca40931139e2d743f0d382f7752166c957d8a12a28b25e27f"
UI_ORIGINAL_SHA256 = "74e985f3bff1c58e46debbaabde32b88f6fab0d006b566d0a3cf316cbef22302"
PLUGIN_NAME = "jarvis_interface_nativa.py"
ORIGINAL_IMPORT = b"from ui import JarvisUI"
NATIVE_IMPORT = b"from jarvis_interface_nativa import JarvisUI"
BACKUP_PREFIX = "backup_interface_nativa_"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(data: bytes) -> dict:
    try:
        value = json.loads(data)
    except (ValueError, UnicodeError):
        raise RuntimeError("Manifesto da copia invalido.") from None
    if (not isinstance(value, dict) or value.get("version") != 1
            or value.get("status") != "preparado"
            or not isinstance(value.get("original_files"), dict)
            or not isinstance(value.get("prepared_files"), dict)):
        raise RuntimeError("A pasta nao e uma copia preparada e verificavel.")
    return value


def _dump(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")


def _read(app: Path, relative: str) -> bytes | None:
    path = _safe_path(app / relative)
    if not path.exists():
        return None
    if not path.is_file():
        raise RuntimeError("A copia contem um caminho reservado que nao e arquivo.")
    return path.read_bytes()


def _reserved_module(relative: str) -> bool:
    # Check Windows aliases too when validating a copy on another platform.
    first = relative.replace("\\", "/").split("/", 1)[0].rstrip(" .").casefold()
    stem = PLUGIN_NAME.removesuffix(".py")
    return first == stem or first.startswith(stem + ".")


def _valid_backup_name(value: object) -> bool:
    return (isinstance(value, str) and value.startswith(BACKUP_PREFIX)
            and len(value) > len(BACKUP_PREFIX)
            and not any(char in value for char in ('/', '\\', ':', '"', '\r', '\n', '\x00'))
            and value.rstrip(" .") == value)


def _context(pasta: Path) -> tuple[Path, dict, bytes]:
    app = _safe_path(pasta)
    _outside_git(app)
    if not app.is_dir():
        raise RuntimeError("Copia preparada nao encontrada.")
    marker = _read(app, preparacao.MARKER)
    if marker is None:
        raise RuntimeError("A pasta original nao sera alterada. Informe a copia preparada.")
    manifest = _json(marker)
    if (manifest["original_files"].get("main.py") != MAIN_ORIGINAL_SHA256
            or manifest["original_files"].get("ui.py") != UI_ORIGINAL_SHA256):
        raise RuntimeError("A base da copia difere da versao analisada. Nenhum arquivo alterado.")
    if any(_reserved_module(name) for name in manifest["original_files"]):
        raise RuntimeError("A origem contem um modulo reservado. Nenhum arquivo alterado.")
    return app, manifest, marker


def _patched_main(original: bytes) -> bytes:
    if _sha(original) != MAIN_ORIGINAL_SHA256 or original.count(ORIGINAL_IMPORT) != 1:
        raise RuntimeError("main.py difere da versao analisada. Nenhum arquivo alterado.")
    source = original.decode("utf-8-sig")
    tree = ast.parse(source, "main.py")
    imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)
               and node.module == "ui" and node.level == 0
               and len(node.names) == 1 and node.names[0].name == "JarvisUI"
               and node.names[0].asname is None]
    if len(imports) != 1:
        raise RuntimeError("Importacao de JarvisUI nao identificada com seguranca.")
    patched = original.replace(ORIGINAL_IMPORT, NATIVE_IMPORT, 1)
    compile(patched.decode("utf-8-sig"), "main.py", "exec")
    return patched


def _atomic_write(path: Path, data: bytes) -> None:
    fd, name = tempfile.mkstemp(prefix=".interface-nativa-", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        temporary.chmod(path.stat().st_mode & 0o777 if path.exists() else 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _transaction(app: Path, old: dict[str, bytes | None],
                 new: dict[str, bytes | None], *, backup_name: str | None = None) -> Path:
    """Backup verificado e rollback apenas dos arquivos escritos nesta chamada."""
    if backup_name is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_name = BACKUP_PREFIX + stamp + "_" + uuid.uuid4().hex[:8]
    if not _valid_backup_name(backup_name):
        raise RuntimeError("Nome de backup invalido.")
    for relative, content in old.items():
        if _read(app, relative) != content:
            raise RuntimeError("A copia mudou durante a instalacao. Nenhum arquivo alterado.")
    backup = _safe_path(app / backup_name)
    backup.mkdir(mode=0o700, exist_ok=False)
    for relative, content in old.items():
        if content is not None:
            destination = backup / relative
            destination.write_bytes(content)
            if destination.read_bytes() != content:
                raise RuntimeError("Backup da interface nativa nao verificado.")
    written: list[str] = []
    try:
        for relative, data in new.items():
            if _read(app, relative) != old[relative]:
                raise RuntimeError("A copia mudou durante a instalacao. Revise o backup local.")
            if data == old[relative]:
                continue
            path = _safe_path(app / relative)
            if data is None:
                path.unlink()
            else:
                _atomic_write(path, data)
            written.append(relative)
    except Exception:
        conflicts = False
        for relative in reversed(written):
            try:
                if _read(app, relative) != new[relative]:
                    conflicts = True
                    continue
                path = _safe_path(app / relative)
                content = old[relative]
                if content is None:
                    path.unlink()
                else:
                    _atomic_write(path, content)
            except (OSError, RuntimeError):
                conflicts = True
        if conflicts:
            raise RuntimeError("Edicao concorrente ou falha interrompeu a restauracao. Revise o backup local.") from None
        raise
    return backup


def _installed(app: Path, manifest: dict) -> tuple[dict, bytes, bytes, bytes]:
    native = manifest.get("native_interface")
    if (not isinstance(native, dict) or native.get("version") != 1
            or native.get("module") != PLUGIN_NAME):
        raise RuntimeError("Registro da interface nativa invalido.")
    name = native.get("backup_dir")
    if not _valid_backup_name(name):
        raise RuntimeError("Caminho de backup da interface nativa invalido.")
    backup = _safe_path(app / name)
    if backup.parent != app or not backup.is_dir():
        raise RuntimeError("Backup original da interface nativa nao encontrado.")
    original = _read(backup, "main.py")
    if original is None:
        raise RuntimeError("Backup de main.py nao encontrado.")
    patched = _patched_main(original)
    module = _read(app, PLUGIN_NAME)
    current_main = _read(app, "main.py")
    if (current_main != patched or module is None
            or native.get("main_before_sha256") != MAIN_ORIGINAL_SHA256
            or native.get("main_after_sha256") != _sha(patched)
            or native.get("module_sha256") != _sha(module)
            or manifest["prepared_files"].get("main.py") != _sha(patched)
            or manifest["prepared_files"].get(PLUGIN_NAME) != _sha(module)):
        raise RuntimeError("Interface nativa editada fora do instalador. Revise antes de continuar.")
    return native, original, patched, module


def _installation_inputs(pasta: Path):
    """Preflight sem escrita, reutilizado antes da atualizacao opcional da ponte."""
    app, manifest, marker = _context(pasta)
    installed = manifest.get("native_interface") is not None
    for names in (manifest["prepared_files"], (path.name for path in app.iterdir())):
        if any(_reserved_module(name) and (not installed or name != PLUGIN_NAME)
               for name in names):
            raise RuntimeError("O modulo reservado ja existe. Nenhum arquivo alterado.")
    ui = _read(app, "ui.py")
    if (ui is None or _sha(ui) != UI_ORIGINAL_SHA256
            or manifest["prepared_files"].get("ui.py") != UI_ORIGINAL_SHA256):
        raise RuntimeError("ui.py difere da versao analisada. Nenhum arquivo alterado.")
    package = _safe_path(preparacao.REPOSITORY_ROOT.resolve() / "integracao" / PLUGIN_NAME)
    if not package.is_file():
        raise RuntimeError("Baixe a atualizacao completa antes de instalar.")
    module = package.read_bytes()
    compile(module.decode("utf-8-sig"), PLUGIN_NAME, "exec")
    existing = manifest.get("native_interface")
    if existing is not None:
        native, original, patched, old_module = _installed(app, manifest)
        original_backup = native["backup_dir"]
    else:
        original = _read(app, "main.py")
        if original is None or manifest["prepared_files"].get("main.py") != MAIN_ORIGINAL_SHA256:
            raise RuntimeError("main.py da copia nao corresponde ao manifesto.")
        patched = _patched_main(original)
        old_module = _read(app, PLUGIN_NAME)
        if old_module is not None or PLUGIN_NAME in manifest["prepared_files"]:
            raise RuntimeError("O modulo reservado ja existe. Nenhum arquivo alterado.")
        original_backup = None

    previous_main = patched if installed else original
    return app, manifest, marker, module, patched, old_module, original_backup, previous_main


def instalar(pasta: Path) -> Path | None:
    (app, manifest, marker, module, patched, old_module,
     original_backup, previous_main) = _installation_inputs(pasta)
    if manifest.get("native_interface") is not None and module == old_module:
        return None

    # Reserve the backup name before updating metadata. The transaction itself
    # creates it exclusively and verifies every byte before touching the app.
    updated = json.loads(marker)
    old = {PLUGIN_NAME: old_module, "main.py": previous_main, preparacao.MARKER: marker}
    # Select the name once because the final manifest records that directory.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_name = BACKUP_PREFIX + stamp + "_" + uuid.uuid4().hex[:8]
    updated["native_interface"] = {
        "version": 1, "module": PLUGIN_NAME,
        "backup_dir": original_backup or backup_name,
        "last_backup_dir": backup_name,
        "main_before_sha256": MAIN_ORIGINAL_SHA256,
        "main_after_sha256": _sha(patched), "module_sha256": _sha(module),
        "ui_sha256": UI_ORIGINAL_SHA256,
    }
    updated["prepared_files"]["main.py"] = _sha(patched)
    updated["prepared_files"][PLUGIN_NAME] = _sha(module)
    return _transaction(app, old, {
        PLUGIN_NAME: module, "main.py": patched, preparacao.MARKER: _dump(updated),
    }, backup_name=backup_name)


def restaurar(pasta: Path) -> Path:
    app, manifest, marker = _context(pasta)
    _, original, patched, module = _installed(app, manifest)
    updated = json.loads(marker)
    updated.pop("native_interface")
    updated["prepared_files"]["main.py"] = MAIN_ORIGINAL_SHA256
    updated["prepared_files"].pop(PLUGIN_NAME)
    return _transaction(app, {
        "main.py": patched, preparacao.MARKER: marker, PLUGIN_NAME: module,
    }, {
        "main.py": original, preparacao.MARKER: _dump(updated), PLUGIN_NAME: None,
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pasta", required=True, type=Path)
    parser.add_argument("--restaurar", action="store_true",
                        help="Restaura somente main.py e remove o modulo instalado, com verificacao e backup.")
    parser.add_argument("--atualizar-ponte", action="store_true",
                        help="Atualiza a ponte/interface web apos validar a copia; ignorado com --restaurar.")
    args = parser.parse_args()
    try:
        if args.atualizar_ponte and not args.restaurar:
            _installation_inputs(args.pasta)
            web_backup = atualizador_web.atualizar(args.pasta)
            print("PONTE E INTERFACE WEB ATUALIZADAS" if web_backup else "PONTE E INTERFACE WEB JA CONFERIDAS")
            if web_backup:
                print(f"BACKUP LOCAL DA PONTE: {web_backup}")
        backup = restaurar(args.pasta) if args.restaurar else instalar(args.pasta)
    except (OSError, RuntimeError, ValueError, SyntaxError) as error:
        print(f"INTERFACE NATIVA NAO ALTERADA OU RESTAURADA: {error}", file=sys.stderr)
        return 1
    print("INTERFACE NATIVA RESTAURADA" if args.restaurar else "INTERFACE NATIVA INSTALADA OU JA CONFERIDA")
    if backup:
        print(f"BACKUP LOCAL: {backup}")
    print("CONFIGURACOES, UI ORIGINAL E AUTOMACAO PRESERVADAS")
    print("NENHUM APLICATIVO EXECUTADO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
