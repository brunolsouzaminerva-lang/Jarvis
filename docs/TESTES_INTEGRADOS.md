# Como testar o Jarvis

Esta branch (`codex/testes-integrados`) reúne a preparação da Etapa 201 e do
Windows dos PRs #2/#6 com as interfaces dos PRs #3/#7. As branches anteriores e
`main` foram preservadas. A consolidação serve para validar o mesmo checkout;
não conecta serviços reais nem implica que a Etapa 201 esteja operacional.

## 1. Conferir os programas no Windows

Abra o PowerShell e execute:

```powershell
git --version
node --version
npm.cmd --version
python --version
pwsh --version
```

Precisamos de Git, Node **22+**, Python **3.11+** e PowerShell **7.4+**. Se algum
comando não for reconhecido ou a versão for inferior, pare nessa etapa e ajuste
o programa pelo procedimento autorizado do notebook. Não é necessário desativar
a política de execução do PowerShell. Usamos `npm.cmd`/`npx.cmd` para evitar os
wrappers `.ps1` eventualmente bloqueados.

## 2. Obter uma cópia nova somente para testes

O GitHub deve estar autenticado para ler o repositório privado, usando a sessão
normal do usuário. Não coloque tokens nos comandos.

O bloco abaixo cria uma pasta nova no perfil do usuário, fora da pasta original.
O bootstrap não faz checkout, evitando hooks/filtros de checkout. O ZIP é gerado
diretamente por Git; não se deve redirecionar um stream binário em PowerShell.

```powershell
$ErrorActionPreference = 'Stop'
$RaizTeste = Join-Path $env:USERPROFILE ('Jarvis-Testes-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
if (Test-Path -LiteralPath $RaizTeste) { throw 'Destino ja existe. Nenhum arquivo sera sobrescrito.' }
New-Item -ItemType Directory -Path $RaizTeste | Out-Null
$Bootstrap = Join-Path $RaizTeste 'bootstrap'
$ArquivoZip = Join-Path $RaizTeste 'codigo.zip'
$Codigo = Join-Path $RaizTeste 'codigo'

git clone --no-checkout --single-branch --no-tags --no-recurse-submodules `
  --branch codex/testes-integrados `
  'https://github.com/brunolsouzaminerva-lang/Jarvis.git' $Bootstrap
if ($LASTEXITCODE -ne 0) { throw 'Falha ao obter a branch. Confira a autenticacao e preserve a pasta criada.' }
git -C $Bootstrap archive --format=zip --output=$ArquivoZip HEAD
if ($LASTEXITCODE -ne 0) { throw 'Falha ao extrair o codigo. Nenhum teste foi iniciado.' }
Expand-Archive -LiteralPath $ArquivoZip -DestinationPath $Codigo
Set-Location -LiteralPath $Codigo
```

A pasta extraída não precisa de `.git`: os testes criam seus próprios repositórios
fictícios em diretórios temporários. A pasta corporativa original não participa
dessa rodada. Em outra sessão, volte somente à pasta `codigo` já criada; não
repita a extração sobre arquivos existentes nem use a pasta corporativa.

## 3. Executar os testes sintéticos

Na pasta `codigo`, após conferir as versões do passo 1:

```powershell
$env:PYTHONUTF8 = '1'
python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'A suite Python falhou. Pare e confira o resumo.' }

npm.cmd ci --ignore-scripts
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar as ferramentas de teste.' }
npx.cmd --no-install playwright install chromium
if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar o navegador de testes.' }
npm.cmd test
if ($LASTEXITCODE -ne 0) { throw 'A suite da interface falhou. Pare e confira o resumo.' }
```

Resultado esperado:

| Suíte | Resultado esperado | O que demonstra |
| --- | --- | --- |
| Python/PowerShell | `Ran 40 tests` e `OK` | Aplicador, retries simulados, backup, idempotência, caminhos e clone sintéticos. |
| Node | `tests 5`, `pass 5`, `fail 0` | Rotas, títulos e estados válidos. |
| Playwright | `15 passed` | Navegação, menu, CTA GGO, estados, foco, microfone sem captura, resoluções e movimento reduzido. |

Os **60 testes** foram executados com sucesso neste mesmo checkout na nuvem.
Isso valida a convivência dos módulos, não uma automação real de DUX/Excel.

Confira também `skipped`/`SKIP`: PowerShell ou Git ausentes podem fazer a classe
de integração ser pulada e ainda resultar em `OK`. Uma restrição de symlinks no
Windows pode impedir os casos correspondentes. Não conte esses casos como
aprovados e não eleve privilégios para contornar políticas; registre o resultado
para diagnóstico. Os testes não usam dados, credenciais ou planilhas corporativas.

## 4. Conferir a tela com os próprios olhos

```powershell
npm.cmd run serve
```

No Edge do **mesmo notebook**, acesse o servidor local da porta **8790**. A janela
PowerShell deve permanecer aberta durante essa revisão. Ao terminar, `Ctrl+C`
encerra o servidor.

Confira:

1. A home mostra moldura azul, núcleo luminoso, microfone e GGO principal.
2. GGO abre o painel secundário; o menu alcança as seis áreas e Escape o fecha.
3. Configurações permite alternar as seis prévias LED; movimento reduzido é respeitado.
4. Microfone abre Configurações sem solicitar captura. Serviços ausentes mostram
   “Não configurado” — esse é o comportamento esperado nesta versão.
5. Nada abre DUX/Excel, processa GGO ou altera arquivos da pasta original.

O retorno útil é o resumo de contagens/erros dessas suítes e a avaliação visual.
Não envie backups, diffs privados, logs corporativos, tokens ou planilhas.

## 5. Testar DUX/Excel somente na etapa autorizada

Depois desta rodada, a preparação do notebook segue
[INTEGRACAO_WINDOWS.md](INTEGRACAO_WINDOWS.md). É outra etapa: requer autorização,
backup verificado e revisão local do configurador/chamadores. Não execute
`Preparar-IntegracaoJarvis.ps1` sobre a pasta corporativa nesta primeira rodada.

A validação real deve conferir o período **01/10/2026 a 31/10/2026** e as cinco
tentativas de leitura sem repetir preenchimento. O ciclo posterior deve preservar
um GGO de trabalho por ciclo, linha 1 da BASE DUX, fontes, pivôs/Realizado Diário
e histórico. Nenhum desses resultados reais foi comprovado pelos testes sintéticos.
