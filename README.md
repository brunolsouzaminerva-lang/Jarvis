# Projeto GGO — Jarvis

Automação do GGO Diário com Python, Excel e relatórios Dux.

Para testar a versão que reúne interface e preparador, siga o
[roteiro de testes integrados no Windows](docs/TESTES_INTEGRADOS.md), sempre em
uma pasta nova e com dados sintéticos.

## Estado
Estrutura inicial de desenvolvimento. O código operacional permanece no computador corporativo e **não foi importado**.

A [interface demonstrativa do Jarvis](interface/index.html) pode ser aberta
diretamente no navegador. Ela inclui reator LED central, botões 3D e simulações
locais. Consulte [como usar e os limites da interface](docs/INTERFACE.md).

A [proposta da interface oficial da issue #5](docs/INTERFACE_OFICIAL.md) fica em
`interface-oficial/`, com home JARVIS, painel GGO, estados LED e navegação testada.
A interface anterior e a automação existente permanecem preservadas.

## Regras essenciais
- Criar uma única cópia de trabalho do GGO por ciclo, atualizando Engenharia e Controladoria no mesmo arquivo.
- Preservar o arquivo anterior e o histórico diário.
- Ao substituir BASE DUX, preservar o cabeçalho (linha 1), atualizar os intervalos de origem e atualizar as tabelas dinâmicas, especialmente Realizado Diário.
- Validar resultados antes de promover qualquer arquivo a versão oficial.
- Nunca incluir credenciais, relatórios reais, dados corporativos ou arquivos GGO neste repositório sem autorização.

## Desenvolvimento
Alterações devem passar por pull request e testes. A execução do Dux e do Excel corporativo exige computador autorizado.

Para executar a suíte com Python 3.11, sem dependências adicionais:

```sh
python -m unittest discover -s tests -v
```

A [preparação da Etapa 201](docs/ETAPA_201.md) inclui testes com dados sintéticos
para a leitura das datas e para o aplicador proposto. A integração real com o Dux
depende do configurador operacional e de validação no computador autorizado.

A [preparação da integração no Windows](docs/INTEGRACAO_WINDOWS.md) descreve o
backup local verificado, a área separada de desenvolvimento, os comandos manuais
e o rollback da revisão, sem escrita na pasta original.
