"""Previa de desenvolvimento com widgets sinteticos; nao abre o Jarvis privado."""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captura", type=Path, help="Salva um PNG e encerra a previa.")
    args = parser.parse_args()
    if args.captura:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "tests-native"))
    from synthetic_ui import create_legacy_module

    spec = importlib.util.spec_from_file_location(
        "jarvis_native_preview", root / "integracao" / "jarvis_interface_nativa.py")
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    legacy = create_legacy_module()
    native.instalar(legacy)
    window = legacy.MainWindow()
    window.resize(1240, 800)
    window.show()
    app.processEvents()
    if args.captura:
        if not window.grab().save(str(args.captura)):
            raise RuntimeError("Nao foi possivel salvar a previa Qt.")
        window.close()
        app.processEvents()
        return 0
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
