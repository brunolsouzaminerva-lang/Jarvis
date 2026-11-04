# ADVERTSER MEDIA — MARKETING INTELLIGENCE

Fundacao local independente do Jarvis. Nesta etapa nao ha dashboard integrado,
OAuth, sincronizacao real, agente de linguagem natural, publicacao ou worker.

Implementado: perfis por cliente em SQLite separado, identidade por contrato de
verificador confiavel, permissoes basicas e auditoria atomica de criacao/edicao.
Sem verificador de producao, as operacoes protegidas sao recusadas antes de
acessar dados. Nenhum usuario administrador ou token ficticio e habilitado no
produto. Os exemplos e testes usam somente clientes sinteticos.

## Consultar capacidades

Na raiz do repositorio, com Python 3.11 ou superior:

```sh
python modules/advertser_media/run.py status
```

O comando nao inicia o modulo no Jarvis, nao abre banco, nao busca credenciais,
nao faz chamadas externas e nao agenda tarefas. A biblioteca inicial nao tem
dependencias de execucao fora da biblioteca padrao; nao e preciso instalar o
pacote para esse comando.

## Contrato local

O host futuro fornece `ModuleConfig(data_root, allowed_clients, protected_roots)`
e um `IdentityVerifier` central confiavel. A partir dele, `MarketingService`
oferece `upsert_client`, `get_client` e `list_audit`. Credenciais nao sao
armazenadas ou incluidas em eventos. Cliente, funcao e acesso sao verificados
antes do armazenamento. Ate admin precisa de acesso explicito ao cliente.

Os diretorios GGO devem ser declarados pelo host em `protected_roots`; o modulo
nao le sua configuracao para descobri-los. O namespace fixo e
`<data_root>/advertser_media/clients/<UUID>/marketing.sqlite3`. Nao use arquivos
ou diretorios reais nos testes, nem copie configuracoes antigas para o modulo.

Ha controles de aplicacao sobre arquivos e dados por cliente, mas SQLite nao
e um cofre criptografado ou uma barreira contra codigo com o mesmo usuario do
sistema operacional. Autenticacao de producao, APIs, processo de servico,
retencao/LGPD e auditoria de leitura/negacoes permanecem pendentes.

## Testar

```sh
python -m unittest discover -s modules/advertser_media/tests -v
```

Os testes criam bancos temporarios e verificam isolamento, permissoes, falhas e
preservacao de uma arvore GGO inteiramente ficticia. Nunca executam DUX/Excel ou
servicos externos. A CI do modulo e separada; os workflows existentes nao foram
modificados.

Auditoria, arquitetura completa e proximos criterios de aceite estao em
[`docs/advertser-media`](../../docs/advertser-media/ARQUITETURA.md).
