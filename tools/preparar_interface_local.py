"""Prepara outra pasta do Jarvis pessoal, sem importar/executar o aplicativo.

Execute este arquivo a partir da copia de desenvolvimento baixada do GitHub.
As configuracoes pessoais permanecem apenas na nova pasta local.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys

try:
    from .aplicar_etapa201 import ANTIGO, NOVO, aplicar
except ImportError:
    from aplicar_etapa201 import ANTIGO, NOVO, aplicar


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_BRIDGE_SHA256 = "ac081dd3464cab02ba412d9c3b83b190f9d1ccacf5b490c86029de58f3e3b191"
ASSETS = ("index.html", "app.js", "core.js", "styles.css", "home-reference.css", "voice.js")
BACKUP = "browser_audio_bridge_antes_interface.py"
MARKER = ".jarvis-interface.json"


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _check_link(path: Path) -> None:
    """Windows junctions and symlinks must never redirect the copy."""
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise RuntimeError("Link ou ponto de redirecionamento encontrado. Copia interrompida.")


def _path(value: Path) -> Path:
    path = Path(value).expanduser().absolute()
    for node in (path, *path.parents):
        try:
            _check_link(node)
        except FileNotFoundError:
            continue
    return path.resolve()


def _inventory(root: Path) -> tuple[dict[str, str], list[str]]:
    files: dict[str, str] = {}
    dirs: list[str] = []
    def fail(error: OSError) -> None:
        raise error

    for parent, child_dirs, child_files in os.walk(root, followlinks=False, onerror=fail):
        for name in sorted(child_dirs):
            node = Path(parent) / name
            _check_link(node)
            dirs.append(node.relative_to(root).as_posix())
        for name in sorted(child_files):
            node = Path(parent) / name
            _check_link(node)
            if not node.is_file():
                raise RuntimeError("Arquivo especial encontrado. Copia interrompida.")
            files[node.relative_to(root).as_posix()] = _digest(node)
        child_dirs.sort()
    return files, sorted(dirs)


def preparar(origem: Path, destino: Path, *, corrigir_datas: bool = False) -> Path:
    """Copia verificada; nunca inicia main.py, DUX, Excel, voz ou rede."""
    source, target = _path(origem), _path(destino)
    repository = REPOSITORY_ROOT.resolve()
    if source == target or source in target.parents or target in source.parents:
        raise RuntimeError("Origem e destino precisam ser pastas separadas, sem sobreposicao.")
    if target == repository or repository in target.parents:
        raise RuntimeError("O destino deve ficar fora do repositorio GitHub.")
    if any((node / ".git").exists() or (node / ".git").is_symlink()
           for node in (target, *target.parents)):
        raise RuntimeError("O destino deve ficar fora de qualquer repositorio Git.")
    if target.exists():
        raise RuntimeError("Destino ja existe. Escolha uma pasta nova; nada sera sobrescrito.")
    if not source.is_dir() or not (source / "main.py").is_file():
        raise RuntimeError("Pasta original com main.py nao encontrada.")
    before, directories = _inventory(source)
    if any(".git" in Path(name).parts for name in (*before, *directories)):
        raise RuntimeError("A origem contem metadados Git. Use a pasta pessoal extraida do ZIP.")
    if before.get("browser_audio_bridge.py") != ORIGINAL_BRIDGE_SHA256:
        raise RuntimeError("A ponte de voz difere da versao analisada. Nenhum arquivo alterado.")
    if any((source / name).exists() for name in ("interface-oficial", BACKUP, MARKER)):
        raise RuntimeError("A origem ja contem uma integracao. Use a pasta original preservada.")

    bridge = repository / "integracao" / "browser_audio_bridge.py"
    assets = repository / "interface-oficial"
    if not bridge.is_file() or any(not (assets / name).is_file() for name in ASSETS):
        raise RuntimeError("Baixe a copia completa de desenvolvimento antes de preparar.")
    compile(bridge.read_text(encoding="utf-8"), str(bridge), "exec")
    if corrigir_datas:
        configurador = source / "jarvis_configurar_datas_controladoria.py"
        if not configurador.is_file():
            raise RuntimeError("Configurador de datas nao encontrado na origem.")
        if (source / "jarvis_configurar_datas_controladoria_antes_correcao.py").exists():
            raise RuntimeError("Backup da Etapa 201 ja existe. Revise essa versao antes de continuar.")
        text = configurador.read_text(encoding="utf-8-sig")
        if text.count(ANTIGO) != 1:
            raise RuntimeError("Configurador difere da Etapa 201 analisada. Nenhum arquivo alterado.")
        compile(text.replace(ANTIGO, NOVO, 1), str(configurador), "exec")

    # Exclusive creation: a second run never overwrites a personal working copy.
    target.mkdir(parents=True, exist_ok=False)
    marker = target / MARKER
    marker.write_text(json.dumps({"status": "incompleto", "version": 1}), encoding="utf-8")
    for relative in directories:
        (target / relative).mkdir(exist_ok=True)
    for relative, digest in before.items():
        original, copied = source / relative, target / relative
        _check_link(original)
        shutil.copy2(original, copied)
        if _digest(copied) != digest:
            raise RuntimeError("A copia nao passou na verificacao. Nao execute o destino incompleto.")
    if _inventory(source) != (before, directories):
        raise RuntimeError("A origem mudou durante a copia. Nao execute o destino incompleto.")

    shutil.copy2(target / "browser_audio_bridge.py", target / BACKUP)
    shutil.copy2(bridge, target / "browser_audio_bridge.py")
    (target / "interface-oficial").mkdir()
    for name in ASSETS:
        shutil.copy2(assets / name, target / "interface-oficial" / name)
    if corrigir_datas:
        aplicar(target / "jarvis_configurar_datas_controladoria.py")

    # Private manifest stays beside the private working copy, never in GitHub.
    after, _ = _inventory(target)
    after.pop(MARKER, None)
    marker.write_text(json.dumps({
        "version": 1, "status": "preparado", "etapa201": corrigir_datas,
        "original_files": before, "prepared_files": after,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origem", required=True, type=Path)
    parser.add_argument("--destino", required=True, type=Path)
    parser.add_argument("--corrigir-datas", action="store_true",
                        help="Aplica a Etapa 201 somente na copia, sem executar o configurador.")
    args = parser.parse_args()
    try:
        target = preparar(args.origem, args.destino, corrigir_datas=args.corrigir_datas)
    except (OSError, RuntimeError, ValueError, SyntaxError) as error:
        print(f"PREPARACAO INTERROMPIDA: {error}", file=sys.stderr)
        return 1
    print(f"COPIA PREPARADA: {target}")
    print("PASTA ORIGINAL PRESERVADA")
    print("NENHUM APLICATIVO EXECUTADO")
    print("Feche o Jarvis anterior antes de iniciar main.py manualmente na nova pasta.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
