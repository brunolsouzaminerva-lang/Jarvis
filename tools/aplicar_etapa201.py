"""Aplica somente a correcao da Etapa 201; nao executa o configurador ou o DUX.

No Windows, na pasta do projeto:
    python caminho/para/aplicar_etapa201.py
Ou informe o arquivo original como primeiro argumento.
"""

from pathlib import Path
import os
import sys
import tempfile


ANTIGO = '''def ler(hwnd):
    buffer = ctypes.create_unicode_buffer(512)
    resultado = ctypes.c_size_t()

    ok = enviar(
        hwnd, 0x000D, len(buffer),
        ctypes.cast(buffer, ctypes.c_void_p),
        0x0002, 500, ctypes.byref(resultado)
    )

    if not ok:
        raise RuntimeError("Falha na leitura da data.")

    return buffer.value.strip()
'''

NOVO = '''def ler(hwnd):
    for tentativa in range(1, 6):
        if not win32gui.IsWindow(hwnd):
            raise RuntimeError("Controle de data nao existe mais.")

        buffer = ctypes.create_unicode_buffer(512)
        resultado = ctypes.c_size_t()

        ok = enviar(
            hwnd, 0x000D, len(buffer),
            ctypes.cast(buffer, ctypes.c_void_p),
            0x0002, 1000, ctypes.byref(resultado)
        )

        if ok and buffer.value.strip():
            return buffer.value.strip()

        print(
            "AGUARDANDO CONTROLE DE DATA:",
            tentativa,
            flush=True
        )
        time.sleep(0.4)

    raise RuntimeError(
        "Falha na leitura apos 5 tentativas."
    )
'''


def aplicar(arquivo):
    arquivo = Path(arquivo)
    if arquivo.name != "jarvis_configurar_datas_controladoria.py":
        raise RuntimeError("Informe jarvis_configurar_datas_controladoria.py.")
    backup = arquivo.with_name("jarvis_configurar_datas_controladoria_antes_correcao.py")
    if not arquivo.is_file():
        raise RuntimeError("Configurador nao encontrado.")
    if arquivo.is_symlink():
        raise RuntimeError("O configurador e um link. Nenhum arquivo alterado.")
    if backup.exists():
        raise RuntimeError("Backup ja existe. Nenhum arquivo alterado.")

    original_bytes = arquivo.read_bytes()
    original = original_bytes.decode("utf-8-sig").replace("\r\n", "\n")
    if original.count(ANTIGO) != 1:
        raise RuntimeError("Trecho original nao encontrado exatamente uma vez. Nenhum arquivo alterado.")
    corrigido = original.replace(ANTIGO, NOVO, 1)
    compile(corrigido, str(arquivo), "exec")

    # Prepare a substituicao antes de criar o backup. Nunca execute o script alvo.
    fd, nome_temporario = tempfile.mkstemp(prefix=".etapa201-", suffix=".tmp", dir=arquivo.parent)
    temporario = Path(nome_temporario)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as saida:
            saida.write(corrigido)
        temporario.chmod(arquivo.stat().st_mode & 0o777)
        if arquivo.read_bytes() != original_bytes:
            raise RuntimeError("O configurador mudou durante a correcao. Nenhum arquivo alterado.")
        # Modo exclusivo: nunca sobrescreva um backup existente.
        with backup.open("xb") as saida:
            saida.write(original_bytes)
        os.replace(temporario, arquivo)
    finally:
        temporario.unlink(missing_ok=True)

    print("LEITURA DAS DATAS CORRIGIDA")
    print("5 TENTATIVAS CONFIGURADAS")
    print("BACKUP CRIADO")
    print("CODIGO VALIDADO")
    print("NENHUMA DATA ALTERADA")
    print("NENHUM GGO ALTERADO")
    return backup


if __name__ == "__main__":
    try:
        if len(sys.argv) > 2:
            raise RuntimeError("Uso: python aplicar_etapa201.py [caminho_do_configurador]")
        aplicar(sys.argv[1] if len(sys.argv) == 2 else "jarvis_configurar_datas_controladoria.py")
    except (OSError, UnicodeError, SyntaxError, RuntimeError) as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        sys.exit(1)
