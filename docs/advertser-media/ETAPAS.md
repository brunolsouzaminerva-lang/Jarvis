# Etapas e criterios de aceite

| Etapa | Entrega | Evidencia para concluir |
| --- | --- | --- |
| 1. Auditoria e fundacao | Branch/worktree aditiva; perfis locais por cliente, contrato de identidade, RBAC basico, auditoria de escrita e status honesto. | Testes sinteticos de dois clientes, acesso negado, integridade do GGO, rollback/retry e importacao sem inicializacao automatica. |
| 2. Servico independente | API Marketing propria, verificador central real, registro de clientes autorizados, migracoes, seguranca e processos isolados. | Testes autenticados de recursos e funcoes, ausencia de fuga entre clientes, timeout/falha sem encerrar Jarvis/GGO. |
| 3. Interface Marketing | Acesso por Agentes e painel proprio no aplicativo; cliente responsivo preparado para mobile. | Navegacao GGO preservada, estados vazios/erro/atraso, acessibilidade e fluxos com servico real de teste. |
| 4. Gestao e conectores | Clientes, tarefas, contratos, calendario, relatorios e Meta/Google Ads inicialmente somente leitura. | Sandbox/contas autorizadas, OAuth, paginacao, limites, renovacao/revogacao e reconciliacao de metricas documentados. |
| 5. Inteligencia e aprovacoes | Agente fundamentado, diagnosticos, recomendacoes e fluxo de aprovacao por revisao. | Respostas com fonte/periodo/moeda/frescor; sem dados ausentes inventados; mudancas invalidam aprovacao. |
| 6. Operacao progressiva | Worker, alertas, agenda e executores expressamente autorizados. | Infraestrutura disponivel, recuperacao, backup/restauracao, isolamento de falhas e aprovacao explicita de operacoes externas. |

As fases nao sao concluidas apenas por uma tela ou um mock. A matriz de
capacidades deve informar se algo e local, visual, conectado de verdade,
indisponivel ou pendente. Nenhum dado real e necessario para a etapa 1.

## Primeiro incremento implementado

Escopo: perfis de clientes com UUID previamente configurado, nome/segmento,
publico/objetivos, responsavel e mensalidade/moeda basicos. O servico consulta e
atualiza somente apos verificacao de identidade, funcao e acesso ao cliente.
Banco e auditoria pertencem exclusivamente ao modulo. Nao ha cadastro de login,
superusuario padrao ou endpoint HTTP exposto.

O bootstrap so oferece `status`: nao cadastra cliente, nao le segredos, nao cria
banco e nao inicia worker ou servidor. Configuracao e verificador confiavel
precisam vir do futuro host. O teste usa verificadores ficticios somente no
diretorio de testes.

Arquivos novos previstos neste incremento:

```text
modules/advertser_media/
  .gitignore
  pyproject.toml
  run.py
  README.md
  advertser_media/{__init__,config,errors,models,service,status,storage}.py
  tests/
docs/advertser-media/{AUDITORIA,ARQUITETURA,ETAPAS}.md
.github/workflows/advertser-media.yml
```

Nenhum arquivo anterior do GGO, das interfaces ou dos instaladores e editado.
Nao ha instalacao no notebook nem publicacao de ambiente. O rollback desta
entrega e simplesmente nao adotar a branch; nao existem migracoes de GGO a reverter.
Runtime de testes e temporario e nao e versionado.

## Pendencias antes de dados e integracoes reais

- Confirmar contrato de extensoes/registro do Jarvis e o provedor central de
  identidade, sessoes, funcoes e clientes autorizados.
- Definir ambiente de hospedagem, cofre, backup, retencao/LGPD, observabilidade
  e identidades de servico. Autorizacao do modulo nao substitui permissoes de SO.
- Validar aplicativos/contas e escopos Meta/Google. As versoes e permissoes
  oficiais ainda nao foram verificadas neste incremento; nao sao declaradas
  integracoes prontas.
- Definir metas por cliente, moedas/fusos, modelo de atribuicao, contratos e
  canais sociais compativeis com APIs aprovadas.
- Validar o GGO operacional separadamente, com sua prioridade e restricoes
  existentes. Marketing nao resolve nem bloqueia a Etapa 201.

## Resultado local deste incremento

- 29 testes novos de Marketing aprovados, usando somente a biblioteca padrao
  e clientes/bancos temporarios sinteticos.
- 172 testes anteriores aprovados: 127 Python, 14 Qt e 31 Node/Chromium.
- Os 56 arquivos anteriormente versionados estao identicos nas duas worktrees.
  O checkout anterior continua limpo, em `a19d180`, na branch da interface nativa.
- O comando `status` informa autenticacao e Meta/Google Ads nao configurados,
  interface/agente planejados, worker dependente de infraestrutura e escritas
  externas desabilitadas. Nao exibe valores de campanhas ou clientes.

Essa evidencia e de regressao sintetica e isolamento de codigo/dados de teste.
Nao equivale a validacao operacional do DUX/Excel, acesso ao notebook ou teste
de integracoes oficiais de Marketing. A CI nova verifica a fundacao em Linux e
Windows, sem credenciais de plataformas.
