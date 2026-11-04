# Etapa 201 — preparação e validação sintética

Esta proposta usa o trecho da Etapa 201 fornecido na conversa de desenvolvimento.
A issue de acompanhamento é [#1](https://github.com/brunolsouzaminerva-lang/Jarvis/issues/1).
Seus requisitos foram conferidos: propor módulos independentes de DUX/Excel,
testar com dados sintéticos e identificar os arquivos ou contratos necessários
para integração. A CI existente executa somente testes, sem implantação.

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

## Estrutura modular proposta

Os caminhos abaixo são uma proposta para a integração futura, não módulos já
implementados nem cópias do código corporativo. Os arquivos atuais continuam
sendo `tools/aplicar_etapa201.py` e `tests/test_etapa201.py`.

| Caminho proposto | Responsabilidade |
| --- | --- |
| `jarvis/leitura_datas.py` | Política de tentativas, recebendo callbacks de existência do controle, leitura do texto e espera; sem importar Win32. |
| `jarvis/validacao_datas.py` | Interpretar datas e comparar o período esperado com o lido, sem acessar DUX/Excel. |
| `jarvis/adaptadores/win32_datas.py` | Implementar os callbacks usando `IsWindow`, `WM_GETTEXT` e a assinatura nativa correta de `enviar`. |
| `jarvis/controladoria.py` | Coordenar preenchimento e leituras por campo, validar o intervalo e interromper o fluxo quando houver divergência. |
| `jarvis/ciclo_ggo.py` | Compartilhar uma única cópia de trabalho entre Engenharia e Controladoria por ciclo e preservar o histórico. |
| `jarvis/adaptadores/excel.py` | Integrar a cópia de trabalho, preservando a linha 1 de BASE DUX e atualizando fontes e tabelas dinâmicas, incluindo Realizado Diário. |

Os pacotes `jarvis` e `jarvis/adaptadores` deverão ter `__init__.py` sem efeitos
colaterais. A lógica de leitura não deve ter acesso ao preenchimento, ao Excel
ou ao processamento da Controladoria. O adaptador é passado à lógica por
callbacks; os testes substituem esses callbacks por respostas sintéticas.

Os testes futuros de política de leitura, validação de período e contrato do
adaptador deverão acompanhar a criação dos módulos. Eles ainda não foram
implementados ou executados; a cobertura presente é descrita abaixo.

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

## Arquivos e interfaces necessários para concluir a Etapa 201

O material operacional só poderá ser disponibilizado para revisão mediante
autorização, sem credenciais, relatórios, planilhas ou dados corporativos reais.
Esta preparação não importa nem solicita esses dados.

1. **`jarvis_configurar_datas_controladoria.py`**: versão atual revisada do
   configurador. É necessária para confirmar que o trecho anterior corresponde
   exatamente ao arquivo, conferir imports e revisar o fluxo completo antes da
   aplicação real do patch.
2. **Definição de `enviar`**: trecho ou módulo que declara a função Win32 usada,
   incluindo `argtypes`, `restype`, função nativa vinculada e arquitetura de
   Python/processo (32 ou 64 bits). Se estiver no configurador, não é necessário
   outro arquivo. Seu caminho externo, se houver, ainda é desconhecido.
3. **Código chamador de `ler` e código de preenchimento**: as funções e seus
   pontos de chamada, no configurador ou em módulo separado. Precisamos verificar
   se cada campo é preenchido uma vez e se as tentativas repetem apenas leitura.
   O nome de eventual arquivo chamador ainda precisa ser informado.
4. **Contrato de identificação dos dois controles**: como localizar o campo
   inicial e o final e distinguir controles recriados. Fornecer metadados
   técnicos revisados ou um adaptador, sem capturas de dados ou handles reais
   persistidos. Não presumir que controles personalizados aceitam `WM_GETTEXT`.
5. **Procedimento de teste no Windows autorizado**: versão de Python, versão
   de `pywin32`, arquitetura e passos para abrir a tela e ler os dois campos
   sem disparar Controladoria. O teste deverá confirmar o período explicitamente
   e reportar as falhas; nenhum comando operacional foi validado na nuvem.

Para separar a lógica do backend, os contratos propostos são:

| Interface | Resultado esperado |
| --- | --- |
| `controle_existe(identificador: int) -> bool` | Informa se o controle ainda é válido antes de cada tentativa. |
| `ler_texto(identificador: int, timeout_ms: int) -> tuple[bool, str]` | Devolve sucesso e texto; falha ou texto vazio permite nova tentativa. O adaptador encapsula buffers e chamadas Win32. |
| `aguardar(segundos: float) -> None` | Implementa a espera; o teste registra o valor sem dormir. |
| `preencher_data(identificador: int, valor: str) -> None` | Interface exclusiva do coordenador, não fornecida à função de leitura. |

Esses contratos orientam a futura separação; o patch recebido ainda usa
`ctypes`, `win32gui`, `time` e `enviar` diretamente. Um retorno não vazio não
valida uma data nem autoriza processamento. A validação do período é uma etapa
separada, e ainda depende da integração com o código chamador.

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

1. Qual é a versão atual revisada do configurador e onde estão seus chamadores?
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
