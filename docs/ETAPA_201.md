# Etapa 201 — preparação e validação sintética

Esta proposta usa o trecho da Etapa 201 fornecido na conversa de desenvolvimento.
A issue de acompanhamento é [#1](https://github.com/brunolsouzaminerva-lang/Jarvis/issues/1).
O acesso à API do GitHub está bloqueado no ambiente atual; o conteúdo da issue
ainda precisa ser lido para conferir os requisitos antes de concluir a preparação.

O configurador operacional `jarvis_configurar_datas_controladoria.py` não foi
importado para este repositório. Os testes usam arquivos Python temporários,
identificadores de janela fictícios e respostas simuladas. Não acessam DUX,
Excel, arquivos GGO, relatórios ou dados corporativos.

## Comportamento proposto

A função de leitura tenta consultar o campo no máximo cinco vezes. Cada tentativa
confere se o controle ainda existe e solicita seu texto com `WM_GETTEXT`, timeout
de 1.000 ms. Uma resposta com sucesso e texto não vazio encerra a leitura. Timeout
ou texto vazio permitem a próxima tentativa, com pausa de 0,4 s. Um controle
destruído interrompe imediatamente; cinco falhas geram erro explícito.

A proposta reproduz o trecho recebido, inclusive a pausa após a quinta falha.
A função não envia mensagens de preenchimento. Isso não garante que o código
chamador do configurador deixe de repetir o preenchimento; esse fluxo ainda
precisa ser inspecionado no original.

## Testes

Use Python 3.11, conforme a CI existente, e somente a biblioteca padrão:

```sh
python -m unittest discover -s tests -v
```

A suíte cobre o comportamento de leitura e a aplicação do patch em arquivos
temporários: backup, preservação do conteúdo original, recusa de trechos
incompatíveis ou duplicados, erro de sintaxe, aplicação repetida e falhas de
substituição. O código do configurador sintético nunca deve ser executado pelo
aplicador; os testes incluem um marcador para detectar execução indevida.

O teste estrutural já existente verifica apenas a presença do README. Nenhum
desses testes comprova a leitura dos controles reais do Windows ou o resultado
da Controladoria.

## Aplicador para revisão

`tools/aplicar_etapa201.py` contém os trechos anterior e proposto recebidos na
conversa. Não é importação do configurador corporativo. O aplicador:

- aceita somente o nome `jarvis_configurar_datas_controladoria.py`;
- exige exatamente uma ocorrência do trecho anterior e valida a sintaxe;
- cria `jarvis_configurar_datas_controladoria_antes_correcao.py` sem sobrescrever backup existente;
- preserva todos os bytes originais no backup, incluindo BOM e CRLF;
- grava a versão corrigida em UTF-8 sem BOM e com finais de linha LF;
- não executa o configurador nem inicia o DUX.

Não execute o aplicador sobre um arquivo operacional como parte desta preparação.
Sua aplicação real depende da revisão do código original e de validação no
computador corporativo autorizado. Se o backup já existir, confira o estado dos
dois arquivos antes de qualquer nova ação; não o apague para forçar execução.

## Dúvidas para a revisão e integração

1. A issue #1 acrescenta requisitos ao trecho da Etapa 201 recebido na conversa?
2. O configurador original importa `ctypes`, `time` e `win32gui` e configura a
   assinatura de `enviar` corretamente para a arquitetura do processo?
3. Os controles reais devolvem suas datas por `WM_GETTEXT`?
4. O fluxo chamador evita repetir preenchimento quando apenas a leitura falha?
5. Qual procedimento aprovado permite testar os dois campos no Windows sem
   iniciar o processamento da Controladoria?

O intervalo solicitado na conversa é **01/10/2026 a 31/10/2026**; os testes usam
essas strings como exemplos sintéticos. Nenhuma data foi alterada no DUX. Antes
de qualquer processamento futuro, é necessário confirmar a leitura explícita de
ambos os campos. Manter a Controladoria sem processamento enquanto as datas
divergirem.
