$output = "projeto_completo.txt"
$extensions = @("*.py", "*.html")
$excludeFolders = @("node_modules", ".git", "vendor", "dist", "build", ".next", "__pycache__", "env", "venv")

Write-Host "Iniciando processamento..."

$files = Get-ChildItem -Recurse -File | Where-Object {
    $file = $_
    $hasValidExtension = $extensions | Where-Object { $file.Name -like $_ }
    $inExcludedFolder = $excludeFolders | Where-Object { $file.FullName -like "*\$_\*" }
    return $hasValidExtension -and !$inExcludedFolder
}

Write-Host "Encontrados $($files.Count) arquivos para processar..."

"=== CONTEÚDO DOS ARQUIVOS ===" | Out-File $output

$contador = 0
foreach ($file in $files) {
    $contador++
    Write-Host "Processando arquivo $contador de $($files.Count): $($file.Name)"
    
    "`n" + "="*80 | Out-File $output -Append
    "ARQUIVO: $($file.FullName)" | Out-File $output -Append
    "="*80 | Out-File $output -Append
    
    try {
        $content = Get-Content $file.FullName -Raw -ErrorAction Stop
        if ($content) {
            $content | Out-File $output -Append
        }
    }
    catch {
        "ERRO: $($_.Exception.Message)" | Out-File $output -Append
    }
}

Write-Host "CoNCLuiDo! Arquivo salvo: $output"