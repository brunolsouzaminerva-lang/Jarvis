"""Consulta segura de capacidades; nao abre banco, conexao, servidor ou worker."""
from __future__ import annotations

import argparse
import json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status",))
    parser.parse_args()
    from advertser_media.status import readiness

    print(json.dumps(readiness(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
