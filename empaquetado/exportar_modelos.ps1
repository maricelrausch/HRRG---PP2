# Copia los modelos de Ollama de ESTA PC a salida\modelos_ollama,
# con la misma estructura que usa Ollama (manifests + blobs).
# Uso: powershell -ExecutionPolicy Bypass -File exportar_modelos.ps1
#      powershell -ExecutionPolicy Bypass -File exportar_modelos.ps1 -Modelos medgemma:4b,embeddinggemma
param(
    [string[]]$Modelos = @("medgemma:4b", "qwen2.5:0.5b", "embeddinggemma")
)
$ErrorActionPreference = "Stop"

if ($env:OLLAMA_MODELS) { $origen = $env:OLLAMA_MODELS }
else { $origen = Join-Path $env:USERPROFILE ".ollama\models" }
$destino = Join-Path $PSScriptRoot "salida\modelos_ollama"
$blobsDestino = Join-Path $destino "blobs"
New-Item -ItemType Directory -Force $blobsDestino | Out-Null

foreach ($modelo in $Modelos) {
    if ($modelo -notmatch ":") { $modelo = "${modelo}:latest" }
    $partes = $modelo.Split(":")
    $nombre = $partes[0]; $tag = $partes[1]

    if ($nombre -match "/") { $rel = "registry.ollama.ai\" + ($nombre -replace "/", "\") }
    else { $rel = "registry.ollama.ai\library\$nombre" }

    $manifiesto = Join-Path $origen "manifests\$rel\$tag"
    if (-not (Test-Path $manifiesto)) {
        throw "No se encuentra $modelo en $origen. Descargarlo antes con: ollama pull $modelo"
    }

    $carpetaManifiesto = Join-Path $destino "manifests\$rel"
    New-Item -ItemType Directory -Force $carpetaManifiesto | Out-Null
    Copy-Item $manifiesto (Join-Path $carpetaManifiesto $tag) -Force

    $json = Get-Content $manifiesto -Raw | ConvertFrom-Json
    $digests = @($json.config.digest) + @($json.layers | ForEach-Object { $_.digest })
    foreach ($d in $digests) {
        $archivo = $d -replace ":", "-"
        $dst = Join-Path $blobsDestino $archivo
        if (-not (Test-Path $dst)) { Copy-Item (Join-Path $origen "blobs\$archivo") $dst }
    }
    Write-Host "[OK] $modelo exportado"
}
