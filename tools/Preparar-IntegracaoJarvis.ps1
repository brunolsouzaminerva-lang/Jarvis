#requires -Version 7.4
<#
.SYNOPSIS
Prepara backup local e clone de desenvolvimento, sem escrever na origem.
.DESCRIPTION
Executar manualmente no Windows autorizado. Não executa código corporativo,
não copia a origem para o clone e não faz commit, push ou implantação.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$SourcePath,
    [Parameter(Mandatory)][string]$BackupRoot,
    [Parameter(Mandatory)][string]$WorkspaceRoot,
    [string]$RepositoryUrl = 'https://github.com/brunolsouzaminerva-lang/Jarvis.git',
    [string]$DevelopmentRef = 'codex/integracao-etapa4',
    [string[]]$AuthorizedRelativePaths = @('jarvis_configurar_datas_controladoria.py'),
    [switch]$SyntheticTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$comparison = if ($IsWindows) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
$kind = 'JarvisIntegrationPreparation'
$gitExecutable = $null
$hooksPath = $null

function Get-AbsolutePath([string]$Value) {
    if (-not [IO.Path]::IsPathFullyQualified($Value)) { throw 'Todos os caminhos devem ser absolutos.' }
    $full = [IO.Path]::GetFullPath($Value).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    $root = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($Value)).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    if ($full -eq $root) { throw 'Nao use a raiz de um volume como origem ou destino.' }
    return $full
}

function Test-Contained([string]$Child, [string]$Parent) {
    return $Child.Equals($Parent, $comparison) -or $Child.StartsWith($Parent + [IO.Path]::DirectorySeparatorChar, $comparison)
}

function Assert-NoLinks([string]$Path) {
    $current = $Path
    while ($current) {
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Link, junction ou reparse point nao permitido.' }
        }
        # Get-Item also detects dangling symbolic links on supported filesystems.
        elseif ($null -ne (Get-Item -LiteralPath $current -Force -ErrorAction SilentlyContinue)) {
            throw 'Link ou caminho inacessivel nao permitido.'
        }
        $parent = [IO.Path]::GetDirectoryName($current)
        if (-not $parent -or $parent -eq $current) { break }
        $current = $parent
    }
}

function Assert-OutsideRepository([string]$Path) {
    $current = $Path
    while ($current) {
        if (Test-Path -LiteralPath (Join-Path $current '.git')) { throw 'Backup e area de trabalho devem ficar fora de repositorios existentes.' }
        $parent = [IO.Path]::GetDirectoryName($current)
        if (-not $parent -or $parent -eq $current) { break }
        $current = $parent
    }
}

function Get-Sha256Text([string]$Text) {
    return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($Text))).ToLowerInvariant()
}

function Get-Inventory([string]$Root) {
    Assert-NoLinks $Root
    $directories = [Collections.Generic.List[string]]::new()
    $files = [Collections.Generic.List[object]]::new()
    $pending = [Collections.Generic.Stack[string]]::new()
    $pending.Push($Root)
    while ($pending.Count -gt 0) {
        $directory = $pending.Pop()
        foreach ($item in @(Get-ChildItem -LiteralPath $directory -Force)) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'A arvore contem link, junction ou reparse point.' }
            $relative = [IO.Path]::GetRelativePath($Root, $item.FullName).Replace('\', '/')
            if ($item.PSIsContainer) {
                $directories.Add($relative)
                $pending.Push($item.FullName)
            }
            else {
                $files.Add([ordered]@{ Path = $relative; Length = [long]$item.Length; SHA256 = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant() })
            }
        }
    }
    $data = [ordered]@{ Directories = @($directories | Sort-Object); Files = @($files | Sort-Object { $_.Path }) }
    return [pscustomobject]@{ Directories = $data.Directories; Files = $data.Files; Fingerprint = Get-Sha256Text ($data | ConvertTo-Json -Depth 10 -Compress) }
}

function Write-NewText([string]$Path, [string]$Text) {
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $bytes = [Text.UTF8Encoding]::new($false).GetBytes($Text)
        $stream.Write($bytes, 0, $bytes.Length)
    }
    finally { $stream.Dispose() }
}

function Write-NewJson([string]$Path, $Value) { Write-NewText $Path ($Value | ConvertTo-Json -Depth 20) }

function Save-State($State) {
    $temporary = Join-Path $WorkspaceRoot ('.state-' + [guid]::NewGuid().ToString('N') + '.tmp')
    Write-NewJson $temporary $State
    [IO.File]::Move($temporary, (Join-Path $WorkspaceRoot 'preparation-state.json'), $true)
}

function Invoke-Process([string]$Executable, [string[]]$Arguments, [string]$WorkingDirectory) {
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $Executable
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.WorkingDirectory = $WorkingDirectory
    foreach ($argument in $Arguments) { $start.ArgumentList.Add($argument) }
    $start.Environment['GIT_TERMINAL_PROMPT'] = '0'
    $start.Environment['GCM_INTERACTIVE'] = 'Never'
    $start.Environment['GIT_OPTIONAL_LOCKS'] = '0'
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $start
    try {
        if (-not $process.Start()) { throw 'Nao foi possivel iniciar uma ferramenta obrigatoria.' }
        $output = $process.StandardOutput.ReadToEndAsync()
        $errors = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        return [pscustomobject]@{ ExitCode = $process.ExitCode; Output = $output.GetAwaiter().GetResult(); Errors = $errors.GetAwaiter().GetResult() }
    }
    finally { $process.Dispose() }
}

function Invoke-Git([string[]]$Arguments, [string]$WorkingDirectory = $WorkspaceRoot, [int[]]$AllowedExitCodes = @(0)) {
    $baseArguments = @('--no-pager', '-c', ('core.hooksPath=' + $hooksPath), '-c', 'core.fsmonitor=false')
    # Discover names only, never filter command values. Respect the same -C
    # context so local and conditional configuration are covered as well.
    $context = @()
    for ($index = 0; $index + 1 -lt $Arguments.Count -and $Arguments[$index] -eq '-C'; $index += 2) {
        $context += @('-C', $Arguments[$index + 1])
    }
    $queryArguments = $baseArguments + $context + @('config', '--null', '--name-only', '--get-regexp', '^filter\..*\.(clean|smudge|process|required)$')
    $configuration = Invoke-Process $gitExecutable $queryArguments $WorkingDirectory
    if ($configuration.ExitCode -notin @(0, 1)) { throw 'Nao foi possivel inspecionar os nomes dos filtros Git com seguranca.' }
    $filterNames = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($key in $configuration.Output.Split([char[]]@([char]0), [StringSplitOptions]::RemoveEmptyEntries)) {
        $separator = $key.LastIndexOf('.')
        if ($separator -lt 7) { throw 'Nome de filtro Git invalido.' }
        $name = $key.Substring(0, $separator)
        if ($name -match '[\x00-\x1f\x7f=]') { throw 'Nome de filtro Git nao pode ser neutralizado com seguranca.' }
        $null = $filterNames.Add($name)
    }
    $filterArguments = @()
    foreach ($name in $filterNames) {
        foreach ($operation in @('clean', 'smudge', 'process')) {
            $filterArguments += @('-c', ($name + '.' + $operation + '='))
        }
        $filterArguments += @('-c', ($name + '.required=false'))
    }
    $gitArguments = $baseArguments + $filterArguments + $Arguments
    $result = Invoke-Process $gitExecutable $gitArguments $WorkingDirectory
    if ($result.ExitCode -notin $AllowedExitCodes) { throw ('Git falhou (codigo ' + $result.ExitCode + '). Verifique autenticacao, ref e caminhos; nenhum conteudo de erro foi publicado.') }
    return $result
}

function Assert-Clone([string]$ClonePath, [string]$ExpectedCommit = '') {
    if (-not (Test-Path -LiteralPath (Join-Path $ClonePath '.git') -PathType Container)) { throw 'Clone de desenvolvimento ausente ou invalido.' }
    Assert-NoLinks $ClonePath
    $null = Get-Inventory $ClonePath
    $remote = (Invoke-Git @('-C', $ClonePath, 'config', '--get', 'remote.origin.url')).Output.Trim()
    if (-not $remote.Equals($RepositoryUrl, $comparison)) { throw 'Origin do clone diverge da configuracao.' }
    $branch = (Invoke-Git @('-C', $ClonePath, 'symbolic-ref', '--short', 'HEAD')).Output.Trim()
    if ($branch -cne $DevelopmentRef) { throw 'A branch do clone foi alterada. Preserve o trabalho e use nova area.' }
    $commit = (Invoke-Git @('-C', $ClonePath, 'rev-parse', '--verify', 'HEAD^{commit}')).Output.Trim()
    if ($ExpectedCommit -and $commit -cne $ExpectedCommit) { throw 'O commit do clone foi alterado. Preserve o trabalho e use nova area.' }
    $status = (Invoke-Git @('-C', $ClonePath, 'status', '--porcelain=v1', '--untracked-files=all', '--ignored=matching')).Output
    if ($status.Trim()) { throw 'O clone contem alteracoes ou arquivos locais. Nada foi sobrescrito.' }
    return $commit
}

function Assert-Backup($State, [string]$SourceFingerprint) {
    $backup = Get-AbsolutePath $State.BackupPath
    if (-not (Test-Contained $backup $BackupRoot) -or $backup.Equals($BackupRoot, $comparison)) { throw 'Caminho do backup no estado e invalido.' }
    Assert-NoLinks $backup
    $markerPath = Join-Path $backup 'completed.json'
    if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) { throw 'Backup incompleto. Preserve-o para diagnostico e use nova area.' }
    $marker = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json
    $manifest = Get-Content -LiteralPath (Join-Path $backup 'manifest.json') -Raw | ConvertFrom-Json
    if ($marker.Kind -ne $kind -or $marker.SourceFingerprint -cne $SourceFingerprint -or $manifest.SourceFingerprint -cne $SourceFingerprint) { throw 'Manifesto ou marcador do backup diverge da origem.' }
    $copy = Get-Inventory (Join-Path $backup 'source')
    if ($copy.Fingerprint -cne $SourceFingerprint) { throw 'Backup diverge dos hashes esperados. Nenhum original foi alterado.' }
}

function New-Review([string]$ClonePath, $State) {
    $review = Join-Path $WorkspaceRoot 'review'
    $diffs = Join-Path $review 'diffs'
    $null = New-Item -ItemType Directory -Path $diffs
    $results = [Collections.Generic.List[object]]::new()
    $index = 0
    foreach ($relative in $AuthorizedRelativePaths) {
        $index++
        $native = $relative.Replace('/', [IO.Path]::DirectorySeparatorChar)
        $original = Join-Path $SourcePath $native
        $candidate = Join-Path $ClonePath $native
        if (-not (Test-Path -LiteralPath $original -PathType Leaf)) {
            $results.Add([ordered]@{ Path = $relative; Status = 'SourceMissing'; Diff = $null })
            continue
        }
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            $results.Add([ordered]@{ Path = $relative; Status = 'DevelopmentMissing'; Diff = $null })
            continue
        }
        Assert-NoLinks $original
        Assert-NoLinks $candidate
        $result = Invoke-Git @('diff', '--no-index', '--no-ext-diff', '--no-textconv', '--', $original, $candidate) -AllowedExitCodes @(0, 1)
        $diffName = '{0:D4}.diff' -f $index
        Write-NewText (Join-Path $diffs $diffName) $result.Output
        $status = if ($result.ExitCode -eq 0) { 'Identical' } else { 'Different' }
        $results.Add([ordered]@{ Path = $relative; Status = $status; Diff = ('diffs/' + $diffName) })
    }
    Write-NewJson (Join-Path $review 'comparison.json') ([ordered]@{ Kind = $kind; SourceFingerprint = $State.SourceFingerprint; DevelopmentCommit = $State.Commit; Files = @($results) })
    $checklist = @'
# Revisao manual local - nao publicar este diretorio

- [ ] Confirmar autorizacao corporativa para revisar cada arquivo selecionado.
- [ ] Manter origem e backup completos intactos. A copia de desenvolvimento nao recebe arquivos da origem automaticamente.
- [ ] Revisar comparison.json e os diffs localmente; podem conter codigo ou segredos. Nao enviar diffs, backups, logs ou manifestos para GitHub/chat.
- [ ] Se DevelopmentMissing, obter autorizacao e revisar o codigo antes de qualquer importacao manual; nao assumir que o configurador existe no repositorio.
- [ ] Conferir imports, assinatura/arquitetura Win32 de enviar, identificacao dos controles e chamadas de ler/preencher.
- [ ] Validar cinco tentativas apenas de leitura, sem preencher novamente por falha transitoria.
- [ ] Confirmar ambas as datas antes do processamento; a Etapa 201 operacional continua pendente.
- [ ] Preservar um unico GGO por ciclo para Engenharia e Controladoria, o arquivo anterior e o historico diario.
- [ ] Preservar BASE DUX linha 1; ajustar origem e atualizar tabelas dinamicas, especialmente Realizado Diario.
- [ ] Executar testes sinteticos separadamente, sem abrir DUX/Excel nem executar scripts corporativos.
- [ ] Antes de qualquer escrita na pasta original, solicitar confirmacao explicita ao proprietario.

## Rollback

Esta preparacao nao alterou a origem: para abandona-la, feche a area de trabalho
sem copiar arquivos de volta. Preserve backup, manifestos e trabalho local.
Se uma integracao manual futura exigir restauracao, compare o backup verificado
e solicite confirmacao antes de qualquer escrita na origem. Nao ha restauracao,
exclusao, reset ou sincronizacao automatica neste script.
'@
    Write-NewText (Join-Path $review 'checklist.md') $checklist
}

try {
    $SourcePath = Get-AbsolutePath $SourcePath
    $BackupRoot = Get-AbsolutePath $BackupRoot
    $WorkspaceRoot = Get-AbsolutePath $WorkspaceRoot
    foreach ($path in @($SourcePath, $BackupRoot, $WorkspaceRoot)) { Assert-NoLinks $path }
    foreach ($pair in @(@($SourcePath, $BackupRoot), @($SourcePath, $WorkspaceRoot), @($BackupRoot, $WorkspaceRoot))) {
        if ((Test-Contained $pair[0] $pair[1]) -or (Test-Contained $pair[1] $pair[0])) { throw 'Origem, backup e area de trabalho devem ser separados e nao sobrepostos.' }
    }
    if (-not (Test-Path -LiteralPath $SourcePath -PathType Container)) { throw 'Pasta de origem nao encontrada.' }
    if (Test-Path -LiteralPath (Join-Path $SourcePath '.git') -PathType Leaf) { throw 'Arquivo .git externo/worktree nao suportado; backup completo nao pode ser garantido.' }
    Assert-OutsideRepository $BackupRoot
    Assert-OutsideRepository $WorkspaceRoot
    if ($SyntheticTest) {
        $RepositoryUrl = Get-AbsolutePath $RepositoryUrl
        Assert-NoLinks $RepositoryUrl
        if (-not (Test-Path -LiteralPath $RepositoryUrl -PathType Container)) { throw 'Repositorio sintetico local nao encontrado.' }
        foreach ($root in @($SourcePath, $BackupRoot, $WorkspaceRoot)) {
            if ((Test-Contained $RepositoryUrl $root) -or (Test-Contained $root $RepositoryUrl)) { throw 'Repositorio sintetico deve ficar separado da origem e destinos.' }
        }
    }
    elseif ($RepositoryUrl -cne 'https://github.com/brunolsouzaminerva-lang/Jarvis.git') { throw 'Somente o repositorio GitHub Jarvis e permitido fora dos testes sinteticos.' }
    if ($DevelopmentRef -notmatch '^codex/[A-Za-z0-9._/-]+$') { throw 'Use uma branch codex/ de desenvolvimento, nunca main ou producao.' }
    $gitExecutable = (Get-Command git -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $hooksPath = Join-Path $WorkspaceRoot '.disabled-git-hooks'
    $neutralDirectory = [IO.Path]::GetTempPath()
    $null = Invoke-Git @('--version') -WorkingDirectory $neutralDirectory
    $null = Invoke-Git @('check-ref-format', '--branch', $DevelopmentRef) -WorkingDirectory $neutralDirectory
    $pythonFound = $false
    foreach ($name in @('python3', 'python', 'py')) {
        $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -eq $command) { continue }
        $arguments = if ($name -eq 'py') { @('-3', '-I', '-S', '--version') } else { @('-I', '-S', '--version') }
        $result = Invoke-Process $command.Source $arguments $neutralDirectory
        if ($result.ExitCode -eq 0 -and $result.Output -match '^Python 3\.') { $pythonFound = $true; break }
    }
    if (-not $pythonFound) { throw 'Python 3 funcional nao encontrado. Instale-o antes de preparar a integracao.' }
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    if ($AuthorizedRelativePaths.Count -eq 0) { throw 'Selecione ao menos um caminho relativo de codigo autorizado.' }
    $AuthorizedRelativePaths = @($AuthorizedRelativePaths | ForEach-Object {
        $relative = $_.Replace('\', '/')
        if ($relative -notmatch '^[^:]+\.py$' -or [IO.Path]::IsPathRooted($relative) -or @($relative.Split('/') | Where-Object { $_ -in @('', '.', '..', '.git') }).Count -gt 0 -or -not $seen.Add($relative)) { throw 'Caminhos autorizados devem ser arquivos .py relativos, unicos e sem traversal.' }
        $relative
    })
    $inventory = Get-Inventory $SourcePath
    $configuration = [ordered]@{ SourcePath = $SourcePath; BackupRoot = $BackupRoot; RepositoryUrl = $RepositoryUrl; DevelopmentRef = $DevelopmentRef; AuthorizedRelativePaths = $AuthorizedRelativePaths; SyntheticTest = [bool]$SyntheticTest }
    $configurationFingerprint = Get-Sha256Text ($configuration | ConvertTo-Json -Depth 10 -Compress)
    $statePath = Join-Path $WorkspaceRoot 'preparation-state.json'
    if (Test-Path -LiteralPath $WorkspaceRoot) {
        if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) { throw 'Area de trabalho preexistente sem estado reconhecido. Nada foi sobrescrito.' }
        $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        if ($state.Kind -ne $kind -or $state.Version -ne 1 -or $state.ConfigurationFingerprint -cne $configurationFingerprint) { throw 'Configuracao da area diverge. Preserve-a e escolha nova area de trabalho.' }
        if ($state.SourceFingerprint -cne $inventory.Fingerprint) { throw 'A origem mudou. Preserve a preparacao anterior e escolha nova area de trabalho.' }
        if ($state.Status -ne 'Ready') { throw 'Preparacao anterior incompleta. Preserve os artefatos e escolha nova area de trabalho.' }
        Assert-Backup $state $inventory.Fingerprint
        $null = Assert-Clone (Join-Path $WorkspaceRoot 'repository') $state.Commit
        Write-Host 'Preparacao existente verificada e reutilizada. Origem intacta; nenhum arquivo sobrescrito.'
        exit 0
    }
    $null = New-Item -ItemType Directory -Path $WorkspaceRoot
    $null = New-Item -ItemType Directory -Path $hooksPath
    if (-not (Test-Path -LiteralPath $BackupRoot)) { $null = New-Item -ItemType Directory -Path $BackupRoot }
    $backupPath = Join-Path $BackupRoot ((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
    $state = [ordered]@{ Kind = $kind; Version = 1; Status = 'Preparing'; ConfigurationFingerprint = $configurationFingerprint; SourcePath = $SourcePath; BackupRoot = $BackupRoot; RepositoryUrl = $RepositoryUrl; DevelopmentRef = $DevelopmentRef; AuthorizedRelativePaths = $AuthorizedRelativePaths; SourceFingerprint = $inventory.Fingerprint; BackupPath = $backupPath; Commit = $null }
    Save-State $state
    $copyRoot = Join-Path $backupPath 'source'
    $null = New-Item -ItemType Directory -Path $copyRoot
    foreach ($relative in $inventory.Directories) { $null = New-Item -ItemType Directory -Path (Join-Path $copyRoot $relative.Replace('/', [IO.Path]::DirectorySeparatorChar)) }
    foreach ($file in $inventory.Files) {
        $native = $file.Path.Replace('/', [IO.Path]::DirectorySeparatorChar)
        Copy-Item -LiteralPath (Join-Path $SourcePath $native) -Destination (Join-Path $copyRoot $native)
    }
    $after = Get-Inventory $SourcePath
    $copied = Get-Inventory $copyRoot
    if ($after.Fingerprint -cne $inventory.Fingerprint -or $copied.Fingerprint -cne $inventory.Fingerprint) { throw 'A origem mudou durante a copia ou o backup diverge. Backup nao marcado como completo.' }
    Write-NewJson (Join-Path $backupPath 'manifest.json') ([ordered]@{ Kind = $kind; Version = 1; SourcePath = $SourcePath; SourceFingerprint = $inventory.Fingerprint; Directories = $inventory.Directories; Files = $inventory.Files })
    Write-NewJson (Join-Path $backupPath 'completed.json') ([ordered]@{ Kind = $kind; Version = 1; SourceFingerprint = $inventory.Fingerprint; CompletedAtUtc = [DateTime]::UtcNow.ToString('O') })
    $clonePath = Join-Path $WorkspaceRoot 'repository'
    # No checkout until local/template/conditional filter names can be read
    # from the new clone. Only this newly created clone is populated here.
    $null = Invoke-Git @('clone', '--no-checkout', '--single-branch', '--no-tags', '--no-recurse-submodules', '--branch', $DevelopmentRef, '--', $RepositoryUrl, $clonePath)
    $null = Invoke-Git @('-C', $clonePath, 'checkout', '--no-recurse-submodules', 'HEAD', '--', '.')
    $state.Commit = Assert-Clone $clonePath
    New-Review $clonePath $state
    if ((Get-Inventory $SourcePath).Fingerprint -cne $inventory.Fingerprint) { throw 'A origem mudou durante a preparacao. Preserve os artefatos e use nova area.' }
    $state.Status = 'Ready'
    Save-State $state
    Write-Host 'Preparacao concluida: backup verificado, clone de desenvolvimento e revisao local criados.'
    Write-Host 'A origem nao foi alterada. Nenhum codigo corporativo foi executado, importado ou publicado.'
    Write-Host 'Relatorios e backup sao locais e confidenciais; nao os envie ao GitHub ou chat.'
    exit 0
}
catch {
    # Deliberately do not print native stdout/stderr or file contents.
    Write-Error ('Preparacao interrompida: ' + $_.Exception.Message) -ErrorAction Continue
    exit 1
}
