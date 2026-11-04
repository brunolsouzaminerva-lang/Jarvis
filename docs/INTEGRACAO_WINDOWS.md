# Preparação da integração — issue #4

O script `tools/Preparar-IntegracaoJarvis.ps1` prepara uma área de revisão local.
Ele deve ser executado **manualmente no Windows corporativo autorizado**. O
Codex em nuvem não acessa a pasta do notebook e não executou este comando nela.

A [preparação da Etapa 201 no PR #2](https://github.com/brunolsouzaminerva-lang/Jarvis/pull/2)
foi revisada: o aplicador e os testes são sintéticos; a leitura Win32, o fluxo de
preenchimento e a validação do intervalo real continuam pendentes. Este PR parte
da branch daquele PR para reutilizar sua documentação e seus testes. A interface
do PR #3 é uma proposta separada, sem integração automática com o DUX/Excel.

## Pré-requisitos

- Autorização corporativa para ler e fazer o backup local da origem.
- PowerShell **7.4 ou superior** (`pwsh`), Git e Python 3 disponíveis.
- Autenticação GitHub do usuário já configurada para leitura HTTPS do repositório
  privado, por exemplo pelo Git Credential Manager ou GitHub CLI. O script usa
  essa autenticação normalmente; não lê, solicita ou salva tokens.
- Espaço para uma cópia completa da árvore de origem e o clone de desenvolvimento.
- Origem sem alterações durante a preparação; feche os processos que a estejam
  modificando. A verificação de hashes não é um snapshot transacional.

O PowerShell 5.1 incluído em instalações antigas do Windows não é suportado.
Não é necessário executar como administrador nem desativar políticas de execução.
Se a política corporativa bloquear o script, siga o procedimento autorizado.

## Obter somente a preparação de desenvolvimento

No PowerShell 7, escolha uma pasta nova fora da origem para o bootstrap:

```powershell
$Preparacao = Join-Path $env:USERPROFILE 'Jarvis-Bootstrap-Issue4'
$Preparador = Join-Path $env:USERPROFILE 'Jarvis-Preparador-Issue4.ps1'
git clone --no-checkout --single-branch --no-tags --no-recurse-submodules `
  --branch codex/integracao-etapa4 `
  'https://github.com/brunolsouzaminerva-lang/Jarvis.git' $Preparacao
if ($LASTEXITCODE -ne 0) { throw 'Clone interrompido; confira acesso e destino. Nenhum original foi alterado.' }
$Conteudo = @(git -C $Preparacao show --no-ext-diff --no-textconv 'HEAD:tools/Preparar-IntegracaoJarvis.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel obter o preparador. Nenhum script foi executado.' }
$Conteudo | Out-File -FilePath $Preparador -Encoding utf8 -NoClobber -ErrorAction Stop
```

Esse comando não deve ser repetido sobre uma pasta existente. Em nova sessão,
reutilize o preparador já extraído após conferir seu conteúdo. Não use
`reset`, `pull` ou exclusão para forçar uma atualização. O clone do bootstrap
contém somente os objetos Git da branch de desenvolvimento, sem checkout. O
script é extraído como texto para fora do checkout, sem sobrescrever um arquivo
existente. Isso evita executar hooks e filtros de checkout durante o bootstrap;
nenhum arquivo corporativo é levado para ele.

## Comando exato de preparação

Após revisar o script, execute:

```powershell
$Preparador = Join-Path $env:USERPROFILE 'Jarvis-Preparador-Issue4.ps1'
pwsh -NoLogo -NoProfile -File $Preparador `
  -SourcePath 'C:\Users\bruno.lsouza\Downloads\Jarvis_Etapa4_Base_Segura\Jarvis' `
  -BackupRoot (Join-Path $env:USERPROFILE 'Jarvis-Backups-Locais') `
  -WorkspaceRoot (Join-Path $env:USERPROFILE 'Jarvis-Trabalho-Issue4') `
  -DevelopmentRef 'codex/integracao-etapa4'
if ($LASTEXITCODE -ne 0) { throw 'Preparação interrompida; preserve os artefatos e confira o diagnóstico.' }
```

A origem acima é a informada na issue. Backup, bootstrap e área de trabalho ficam
em pastas distintas, externas à origem. O script exige caminhos absolutos, sem
sobreposição e sem links/junctions/reparse points, inclusive nos ancestrais. Não
escolha destinos dentro de outro checkout. Uma origem com `.git` apontando para
metadados externos de worktree é recusada porque não permite garantir a cópia
completa só daquela árvore.

O URL de produção aceito pelo preparador é exclusivamente o repositório Jarvis
no GitHub, e a ref deve ser uma branch `codex/...`. A opção `-SyntheticTest`
existe apenas para os testes automatizados: aceita um repositório Git local
fictício, nunca deve ser usada para preparar a pasta corporativa.

## Resultado e idempotência

```text
Jarvis-Backups-Locais/
  <data-UTC-e-id-unico>/
    source/                  árvore completa de arquivos e diretórios
    manifest.json            inventário de caminhos, tamanhos e SHA-256
    completed.json           criado somente após verificar a cópia e a origem

Jarvis-Trabalho-Issue4/
  preparation-state.json     estado, fingerprint, backup e commit selecionado
  .disabled-git-hooks/       diretório vazio para os comandos Git do preparador
  repository/                clone da branch de desenvolvimento, sem a origem
  review/
    comparison.json          resultados por arquivo autorizado
    checklist.md             revisão manual e regras GGO
    diffs/*.diff             diferenças locais, quando há arquivo correspondente
```

O backup inclui arquivos ocultos, o diretório `.git`, arquivos binários e pastas
vazias. Seu conteúdo é verificado com SHA-256 e inventários da origem antes e
depois da cópia. A garantia é da árvore regular e do conteúdo; não abrange ACLs,
proprietário, streams NTFS adicionais ou arquivos externos referenciados.

Repetir o comando de preparação com a mesma origem, configuração e clone limpo
verifica e reutiliza o mesmo backup e commit. Não cria outra cópia GGO de trabalho,
não atualiza a ref remota e não sobrescreve arquivos. Se a origem, o clone ou o
backup tiverem mudado, o script interrompe. Preserve o trabalho anterior e escolha
uma nova `-WorkspaceRoot`; a nova preparação criará outro backup datado sem
substituir o anterior. Um estado parcial também exige nova área, sem limpeza
automática dos artefatos interrompidos.

Se o clone falhar por autenticação ou ref indisponível, a origem e o backup já
verificado permanecem preservados. Corrija o acesso pelo procedimento GitHub
normal do usuário e use uma nova área; não coloque credenciais em parâmetros.

## Comparação e integração manual

Por padrão, apenas `jarvis_configurar_datas_controladoria.py` é selecionado para
comparação. Outros caminhos `.py` relativos precisam de seleção explícita por
`-AuthorizedRelativePaths` e autorização. Caminhos absolutos, traversal, duplicados
e extensões de dados/segredos são recusados.

O preparador não executa o arquivo original nem o importa. Ele compara o código
somente se ambos os arquivos existirem, usando `git diff --no-index` sem drivers
externos ou textconv. O diff é gravado em `review`, nunca impresso no console.
Hooks, fsmonitor e filtros Git `clean`/`smudge`/`process` são neutralizados nos
comandos do preparador, sem alterar a configuração ou autenticação do usuário.
O clone começa sem checkout; os arquivos são populados somente após essa
neutralização, também considerando a configuração local do clone.
Quando houver Git LFS, os ponteiros versionados permanecem como texto; o script
não baixa seus objetos nem aciona filtros para materializá-los.
Os resultados possíveis são `SourceMissing`, `DevelopmentMissing`, `Identical` e
`Different`. O configurador operacional ainda não está na branch; por isso,
**`DevelopmentMissing` é uma pendência esperada**, não autorização para copiá-lo.

Backup, manifestos e relatórios podem conter material privado: permanecem fora
dos repositórios e não devem ser anexados ao GitHub ou ao chat. O script não roda
`git add`, `commit`, `push`, cópia da origem para o clone ou sincronização.

Antes de importar manualmente qualquer código autorizado:

- Revisar o configurador, imports, assinatura de `enviar`, arquitetura de Python
  e do processo, identificação dos controles e chamadores de leitura/preenchimento.
- Conferir que as cinco tentativas repetem apenas a leitura, sem novo preenchimento.
- Confirmar explicitamente inicial **01/10/2026** e final **31/10/2026** antes
  de qualquer processamento da Controladoria.
- Manter uma única cópia de GGO por ciclo para Engenharia e Controladoria,
  preservando arquivo anterior e histórico diário.
- Preservar a linha 1 de BASE DUX, ajustar a fonte e atualizar as tabelas
  dinâmicas, especialmente Realizado Diário, na futura integração autorizada.
- Executar os testes sintéticos no clone de desenvolvimento, nunca descobrir
  ou importar testes da pasta corporativa. Revisar o diff e os arquivos a enviar
  antes de qualquer commit manual autorizado.

Esses itens de DUX/Excel são um checklist de integração futura. Este preparador
não abre planilhas, atualiza pivôs, processa GGO ou torna a Etapa 201 operacional.

## Rollback

A preparação não escreve na origem, portanto não há restauração dela a executar.
Para abandonar a revisão, feche os processos da área de trabalho e preserve o
backup. Opcionalmente, renomeie **somente a área separada**, sem excluir conteúdo:

```powershell
Rename-Item -LiteralPath (Join-Path $env:USERPROFILE 'Jarvis-Trabalho-Issue4') `
  -NewName ('Jarvis-Trabalho-Issue4-abandonado-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
```

Confira os caminhos antes do comando e use outro nome se o destino já existir.
O bootstrap e o backup permanecem disponíveis. Não há cópia de volta, exclusão,
reset, implantação ou restauração automática. Uma eventual restauração após
integração manual futura precisa de confirmação explícita **antes de qualquer
escrita na pasta original**; isso fica fora do escopo deste script.

## Testes e pendências

```sh
python -m unittest discover -s tests -v
```

A suíte executa PowerShell real (`pwsh`) com uma origem e um Git remoto locais
fictícios. Pode-se indicar o executável por `JARVIS_PWSH`. Os testes verificam
backup completo de conteúdo, preservação da origem e de um GGO sintético, ausência
de execução do configurador, reuso idempotente, clone alterado, backup corrompido,
recusas de caminhos e bloqueio de hooks/diff externos. Fixtures são geradas em
diretórios temporários; nenhum arquivo corporativo é incluído no repositório.

A CI usa runners Linux e Windows para os testes. Se `pwsh` estiver ausente numa
execução local, a classe de integração será marcada como pulada; esse resultado
não valida o preparador. A CI verifica a disponibilidade do PowerShell.

Continuam pendentes a autorização e execução no notebook, o código revisado do
configurador, seus contratos Win32 e a validação real no DUX/Excel. Resultados
sintéticos e checklist de pivôs não substituem essa validação.
