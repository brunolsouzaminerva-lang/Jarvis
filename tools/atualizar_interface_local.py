"""Atualiza somente a interface/ponte da copia preparada; nao executa o Jarvis."""
from __future__ import annotations

import argparse
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
    from .criar_atalho_local import _outside_git, _safe_path, criar
except ImportError:
    import preparar_interface_local as preparacao
    from criar_atalho_local import _outside_git, _safe_path, criar


FILES = ("browser_audio_bridge.py", *("interface-oficial/" + n for n in preparacao.ASSETS))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_atomic(path: Path, data: bytes) -> None:
    fd, name = tempfile.mkstemp(prefix=".interface-", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        temporary.chmod(path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atualizar(pasta: Path) -> Path | None:
    app = _safe_path(pasta)
    _outside_git(app)
    if not app.is_dir() or not _safe_path(app / "main.py").is_file():
        raise RuntimeError("Copia preparada com main.py nao encontrada.")
    marker = _safe_path(app / preparacao.MARKER)
    if not marker.is_file():
        raise RuntimeError("Esta pasta nao e uma copia preparada. A origem nao sera alterada.")
    original_marker = marker.read_bytes()
    try:
        manifest = json.loads(original_marker)
    except (ValueError, UnicodeError):
        raise RuntimeError("Manifesto da copia invalido.") from None
    if (not isinstance(manifest, dict) or manifest.get("version") != 1
            or manifest.get("status") != "preparado"
            or not isinstance(manifest.get("prepared_files"), dict)):
        raise RuntimeError("A copia nao tem uma preparacao concluida e verificavel.")

    repository = preparacao.REPOSITORY_ROOT.resolve()
    old: dict[str, bytes] = {}
    new: dict[str, bytes] = {}
    for relative in FILES:
        path = _safe_path(app / relative)
        if not path.is_file():
            raise RuntimeError("Copia incompleta. Nenhum arquivo alterado.")
        old[relative] = path.read_bytes()
        if manifest["prepared_files"].get(relative) != _sha(old[relative]):
            raise RuntimeError("Arquivo de interface editado fora do preparador. Revise antes de atualizar.")
        package_relative = "integracao/browser_audio_bridge.py" if relative == "browser_audio_bridge.py" else relative
        package = _safe_path(repository / package_relative)
        if not package.is_file():
            raise RuntimeError("Atualizacao baixada incompleta. Nenhum arquivo alterado.")
        new[relative] = package.read_bytes()
    compile(new["browser_audio_bridge.py"].decode("utf-8"), "browser_audio_bridge.py", "exec")
    if old == new:
        return None

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup = app / ("backup_interface_" + stamp + "_" + uuid.uuid4().hex[:8])
    backup.mkdir(exist_ok=False)
    for relative, data in {**old, preparacao.MARKER: original_marker}.items():
        destination = backup / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        if destination.read_bytes() != data:
            raise RuntimeError("Backup nao verificado. A interface nao foi alterada.")

    # A configuracao pessoal e main.py nunca entram na lista de escrita.
    updated = json.loads(original_marker)
    for relative, data in new.items():
        updated["prepared_files"][relative] = _sha(data)
    updated["interface_backup"] = backup.name
    updated_bytes = json.dumps(updated, ensure_ascii=False, indent=2).encode("utf-8")
    written: list[str] = []
    try:
        if marker.read_bytes() != original_marker:
            raise RuntimeError("O manifesto mudou durante a preparacao da atualizacao.")
        for relative, data in new.items():
            path = _safe_path(app / relative)
            if path.read_bytes() != old[relative]:
                raise RuntimeError("A interface mudou durante a atualizacao.")
            _write_atomic(path, data)
            written.append(relative)
        _write_atomic(marker, updated_bytes)
        written.append(preparacao.MARKER)
    except Exception:
        for relative in reversed(written):
            expected = updated_bytes if relative == preparacao.MARKER else new[relative]
            path = _safe_path(app / relative)
            if path.read_bytes() != expected:
                raise RuntimeError("Atualizacao interrompida por edicao concorrente. Revise o backup local.") from None
            restored = original_marker if relative == preparacao.MARKER else old[relative]
            _write_atomic(path, restored)
        raise
    return backup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pasta", required=True, type=Path)
    parser.add_argument("--atalho", action="store_true", help="Cria tambem o iniciador no Desktop.")
    args = parser.parse_args()
    try:
        backup = atualizar(args.pasta)
    except (OSError, RuntimeError, ValueError, SyntaxError) as error:
        print(f"ATUALIZACAO INTERROMPIDA: {error}", file=sys.stderr)
        return 1
    print("INTERFACE ATUALIZADA" if backup else "INTERFACE JA ATUALIZADA")
    if backup:
        print(f"BACKUP LOCAL: {backup}")
    if args.atalho:
        try:
            print(f"ATALHO CRIADO OU JA CONFERIDO: {criar(args.pasta)}")
        except (OSError, RuntimeError, ValueError) as error:
            print(f"INTERFACE PRONTA, MAS ATALHO NAO CRIADO: {error}", file=sys.stderr)
            return 1
    print("MAIN.PY E CONFIGURACOES PESSOAIS PRESERVADOS")
    print("NENHUM APLICATIVO EXECUTADO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
