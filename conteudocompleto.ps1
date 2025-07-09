# Script para capturar códigos de arquivos importantes do projeto em um único TXT
# Salve como, por exemplo, 'Export-ProjectCode.ps1'

param(
    [string]$projectRoot = (Get-Location).Path, # Caminho padrão: diretório atual do script
    [string]$outputFile = "projeto_completo_filtrado.txt" # Nome do arquivo de saída
)

# Garante que o projectRoot seja um objeto Path para manipulações mais fáceis
$projectRootPath = Get-Item $projectRoot

# Extensões de arquivos de código e configuração relevantes
$extensions = @(
    ".py", ".html", ".css", ".js", ".json", # Código
    ".txt", ".md", ".toml", ".ini", ".yaml", ".yml", # Configurações e documentação
    ".conf", ".xml" # Outros tipos de configuração, se aplicável
)

# Nomes de pastas a serem excluídas, independentemente do nível hierárquico
$excludeFolderNames = @(
    "node_modules", ".git", "vendor", "dist", "build", ".next",
    "__pycache__", "env", "venv", # Ambientes e caches
    "db", # Se houver uma pasta chamada 'db'
    "static\plugins", "static\dist", # Pastas grandes de assets do AdminLTE/Bootstrap
    "media" # Se você tiver uma pasta de mídia com arquivos grandes
)

# Nomes de arquivos específicos a serem excluídos (independentemente da pasta)
$excludeFileNames = @(
    "db.sqlite3" # Exclui explicitamente o arquivo do banco de dados SQLite
)

# Extensões de arquivos que NUNCA devem ser incluídas (binários, logs, etc.)
$neverIncludeExtensions = @(
    ".sqlite3", ".bin", ".log", ".DS_Store", ".tmp", ".bak", ".exe", ".dll", ".so", ".pyc", ".map"
)

# Constrói a lista de caminhos absolutos para exclusão
$excludeAbsolutePaths = @()
foreach ($excludeName in $excludeFolderNames) {
    # Tenta obter o item para verificar se é uma pasta, e adiciona o caminho absoluto
    $excludedItem = Get-Item -Path (Join-Path $projectRoot $excludeName) -ErrorAction SilentlyContinue
    if ($excludedItem -and $excludedItem.PSIsContainer) { # Verifica se é uma pasta
        $excludeAbsolutePaths += $excludedItem.FullName.ToLower()
    }
}

Write-Host "Iniciando processamento a partir de: $projectRoot"
Write-Host "Arquivos serão salvos em: $outputFile"
Write-Host "Extensões a incluir: $($extensions -join ', ')"
Write-Host "Pastas a excluir (caminhos absolutos):"
$excludeAbsolutePaths | ForEach-Object { Write-Host "  - $_" }
Write-Host "Arquivos específicos a excluir: $($excludeFileNames -join ', ')"
Write-Host "Extensões a nunca incluir: $($neverIncludeExtensions -join ', ')"

# Get all files recursively and then filter them
$allProjectFiles = Get-ChildItem -Path $projectRoot -Recurse -File

$filteredFiles = $allProjectFiles | Where-Object {
    $file = $_
    $filePathLower = $file.FullName.ToLower() # Caminho do arquivo em minúsculas para comparação

    # 1. Filtrar por extensão válida
    $hasValidExtension = $extensions -contains $file.Extension.ToLower()
    if (-not $hasValidExtension) { return $false }

    # 2. Filtrar por extensões que NUNCA devem ser incluídas
    $isNeverIncludedExtension = $neverIncludeExtensions -contains $file.Extension.ToLower()
    if ($isNeverIncludedExtension) { return $false }

    # 3. Filtrar por pastas excluídas
    $isExcludedByFolder = $false
    foreach ($excludedPath in $excludeAbsolutePaths) {
        if ($filePathLower.StartsWith($excludedPath)) {
            $isExcludedByFolder = $true
            break
        }
    }
    if ($isExcludedByFolder) { return $false }

    # 4. Filtrar por nomes de arquivos específicos a serem excluídos
    $isExcludedByFileName = $excludeFileNames -contains $file.Name.ToLower()
    if ($isExcludedByFileName) { return $false }

    return $true # Se passou por todos os filtros, incluir
}

Write-Host "Encontrados $($filteredFiles.Count) arquivos para processar..."

"=== CONTEÚDO DOS ARQUIVOS ===" | Out-File $outputFile -Encoding UTF8

$contador = 0
foreach ($file in $filteredFiles) {
    $contador++
    # Obter o caminho relativo do arquivo em relação à raiz do projeto
    $relativePath = $file.FullName.Replace($projectRootPath.FullName + "\", "")
    Write-Host "Processando arquivo $contador de $($filteredFiles.Count): $relativePath"
    
    "`n" + "="*80 | Out-File $outputFile -Append -Encoding UTF8
    "ARQUIVO: $relativePath" | Out-File $outputFile -Append -Encoding UTF8
    "="*80 | Out-File $outputFile -Append -Encoding UTF8
    
    try {
        # Ler o conteúdo do arquivo com a codificação especificada
        $content = Get-Content $file.FullName -Raw -Encoding UTF8 -ErrorAction Stop
        if ($content) {
            $content | Out-File $outputFile -Append -Encoding UTF8
        } else {
            "(Arquivo vazio ou sem conteúdo visível)" | Out-File $outputFile -Append -Encoding UTF8
        }
    }
    catch {
        ("ERRO ao ler arquivo " + $relativePath + ": " + $_.Exception.Message) | Out-File $outputFile -Append -Encoding UTF8
    }
}

Write-Host "CoNCLUiDo! Arquivo salvo: $outputFile"