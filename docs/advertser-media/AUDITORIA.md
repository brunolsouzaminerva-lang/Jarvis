# Auditoria tecnica — Advertser Media

Base inspecionada: `a19d180bddd2f475dc2bae45c017152c99e05a42`, branch
`codex/interface-nativa-jarvis`. O checkout `/workspace/Jarvis` estava limpo.
O novo trabalho fica em `codex/advertser-media-fase1`, na worktree separada
`/workspace/Jarvis-advertser-media`. A arvore de trabalho anterior nao foi trocada.

## Trabalho existente e pendencias

| Trabalho | Situacao encontrada |
| --- | --- |
| PR #2 — Etapa 201 | Rascunho aberto; leitura com retentativas e aplicador testados com fontes sinteticas. |
| PR #6 — preparacao Windows | Rascunho aberto; backup, clone e comparacao locais. |
| PR #8 — testes integrados | Rascunho aberto; combinacao de preparador e interfaces. |
| PR #9 — interface e voz | Rascunho aberto; iniciador e reativacao de voz confirmados pelo proprietario no Windows. |
| PR #10 — interface nativa | Rascunho aberto, CI aprovada; aplicacao da nova janela no notebook ainda pendente. |
| GGO operacional | Periodo, controles reais, DUX, Excel e resultado do ciclo ainda precisam de validacao autorizada. |

Nenhum desses PRs estava mesclado. Nao foi realizado merge, rebase, reset,
restauracao ou instalacao para iniciar o Marketing. Nao e possivel observar o
notebook do usuario a partir desta auditoria; nao se presume que esteja ligado
ou que o GGO esteja parado nele.

## O que existe no repositorio

- `interface/` e `interface-oficial/`: interfaces web. O catalogo web tem um
  cartao GGO; DUX/Excel e execucao operacional aparecem como nao configurados.
- `integracao/browser_audio_bridge.py`: servidor local de arquivos permitidos,
  estado e audio WebSocket. Nao e uma API de negocios nem um sistema de login.
- `integracao/jarvis_interface_nativa.py`: adaptador visual PyQt6. Reutiliza a
  facade privada e o gestor de extensoes original; nao fornece um novo backend.
- `tools/`: preparadores, instaladores e backups para copias locais verificadas.
- `tests/`, `tests-native/`, `tests-ui/`: testes sinteticos de integridade,
  preparacao, callbacks Qt, navegacao e captura de voz.

O `main.py`, o `ui.py`, os scripts operacionais completos, as memorias e as
configuracoes pessoais permanecem fora do Git. A auditoria deste incremento nao
leu `.env`, chaves, memorias, logs, planilhas ou dados corporativos.

Nao foi encontrado um servico central implementado de autenticacao/OAuth,
autorizacao entre modulos, persistencia de negocios, fila de tarefas ou memoria
compartilhavel. Nomes de callbacks da UI privada nao comprovam esses servicos.

## Riscos que determinam o isolamento

1. Os instaladores aceitam hashes e importacoes exatos. Alterar o main, a UI ou
   seus contratos de instalacao durante outra tarefa pode bloquear atualizacoes.
2. As rotas web sao explicitamente limitadas. Servidor, preparador e atualizador
   permitem somente os seis assets existentes. Um arquivo de Marketing novo nao
   fica automaticamente servido, instalado ou visivel dentro do Jarvis.
3. O botao Agentes nativo chama o gestor privado de extensoes. Esse contrato deve
   ser confirmado antes de registrar o novo agente; nao se presume equivalencia
   com o catalogo web.
4. Reaproveitar a porta/processo da voz como backend de Marketing criaria
   acoplamento de falhas, identidade e dependencias.
5. Credenciais da agencia e memoria por cliente nao devem vir da configuracao
   pessoal ou operacional existente. Um cliente nao pode escolher um caminho de
   banco nem informar sua propria funcao como prova de identidade.

## Limite da primeira entrega

Somente arquivos novos em `modules/advertser_media/`,
`docs/advertser-media/` e `.github/workflows/advertser-media.yml`.
README, interfaces, ponte de voz, instaladores, dependencias e testes existentes
permanecem iguais ao commit base. Os fontes e diretorios privados nao sao tocados.

A fundacao local cadastra/consulta um perfil para um UUID de cliente previamente
autorizado, em banco SQLite proprio, e registra criacoes/atualizacoes de perfil.
Uma identidade precisa vir de um verificador confiavel injetado. Nao existe
verificador de producao: por padrao, operacoes protegidas sao negadas antes de
acessar armazenamento. Os verificadores ficticios existem somente nos testes.

Isso nao e autenticacao central pronta, CRM completo, dashboard integrado,
integracao real de anuncios, agente autonomo ou execucao continua. Os estados
publicos diferenciam implementacao local, planejamento e integracoes ausentes.
