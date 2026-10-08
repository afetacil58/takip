param(
    [ValidateRange(1, 65535)]
    [int]$Port = 5000
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI bulunamadı. Çevrimdışı kurulacak bilgisayarda Docker Engine/Desktop önceden kurulu olmalıdır."
}

& docker info --format '{{.OSType}}' *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker motoru çalışmıyor. Docker Desktop/Engine'i başlatın ve betiği tekrar çalıştırın."
}
if ((& docker info --format '{{.OSType}}').Trim() -ne "linux") {
    throw "Bu uygulama Linux konteyner motoru gerektirir. Docker Desktop'ı Linux containers moduna alın."
}

& docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose eklentisi bulunamadı. Docker Desktop/Compose kurulmalıdır."
}

$imageArchive = Join-Path $PSScriptRoot "afad-gorev-takip-image.tar"
$checksumFile = Join-Path $PSScriptRoot "SHA256SUMS.txt"
if (-not (Test-Path -LiteralPath $imageArchive)) {
    throw "Uygulama imaj arşivi bulunamadı: $imageArchive"
}
if (-not (Test-Path -LiteralPath $checksumFile)) {
    throw "Arşiv doğrulama dosyası bulunamadı: $checksumFile"
}

$checksumLine = Get-Content -LiteralPath $checksumFile |
    Where-Object { $_ -match '\*?afad-gorev-takip-image\.tar$' } |
    Select-Object -First 1
if (-not $checksumLine -or $checksumLine -notmatch '^([A-Fa-f0-9]{64})\s+\*?afad-gorev-takip-image\.tar$') {
    throw "SHA256SUMS.txt biçimi geçersiz veya imaj arşivi listelenmemiş."
}
$expectedHash = $Matches[1].ToLowerInvariant()
$actualHash = (Get-FileHash -LiteralPath $imageArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $expectedHash) {
    throw "İmaj arşivi SHA-256 doğrulamasından geçmedi. Dosya kopyasını kontrol edin."
}
Write-Host "İmaj arşivi SHA-256 ile doğrulandı." -ForegroundColor Green

if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot ".env"))) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot ".env.example") `
        -Destination (Join-Path $PSScriptRoot ".env")
}
$envPath = Join-Path $PSScriptRoot ".env"
$envLines = @(Get-Content -LiteralPath $envPath)
$portLine = "APP_PORT=$Port"
$portSet = $false
$updatedLines = foreach ($line in $envLines) {
    if (-not $portSet -and $line -match '^\s*APP_PORT\s*=') {
        $portSet = $true
        $portLine
    }
    else {
        $line
    }
}
if (-not $portSet) {
    $updatedLines += $portLine
}
[System.IO.File]::WriteAllLines(
    $envPath,
    [string[]]$updatedLines,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host "Uygulama imajı yerel Docker motoruna yükleniyor..." -ForegroundColor Cyan
& docker load --input $imageArchive
if ($LASTEXITCODE -ne 0) {
    throw "Docker imaj arşivi yüklenemedi."
}

Write-Host "Uygulama başlatılıyor: http://localhost:$Port" -ForegroundColor Cyan
& docker compose --project-name afad-gorev-takip -f compose.yaml up -d
if ($LASTEXITCODE -ne 0) {
    throw "Uygulama başlatılamadı. docker compose --project-name afad-gorev-takip -f compose.yaml logs app komutunu çalıştırın."
}

$deadline = (Get-Date).AddMinutes(2)
$healthy = $false
do {
    $containerId = (& docker compose --project-name afad-gorev-takip `
        -f compose.yaml ps -q app | Select-Object -First 1).Trim()
    if ($containerId) {
        $health = (& docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $containerId 2>$null).Trim()
        if ($health -eq "healthy") {
            $healthy = $true
            break
        }
        if ($health -eq "unhealthy" -or $health -eq "exited") {
            break
        }
    }
    Start-Sleep -Seconds 3
} while ((Get-Date) -lt $deadline)

if (-not $healthy) {
    & docker compose --project-name afad-gorev-takip -f compose.yaml logs --tail 80 app
    throw "Uygulama sağlıklı duruma geçmedi. Yukarıdaki konteyner loglarını kontrol edin."
}

$response = Invoke-WebRequest -Uri "http://localhost:$Port/login" `
    -UseBasicParsing -TimeoutSec 10
if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 500) {
    throw "Uygulama HTTP $($response.StatusCode) yanıtı verdi."
}

Write-Host "`nUygulama hazır: http://localhost:$Port" -ForegroundColor Green
$logs = & docker compose --project-name afad-gorev-takip -f compose.yaml `
    logs --no-color --tail 100 app 2>&1
$tokenMatch = [regex]::Match(
    ($logs -join "`n"),
    "Initial administrator setup token \(enter it at /setup\):\s*(\S+)"
)
if ($tokenMatch.Success) {
    Write-Host "İlk yönetici kurulum anahtarı: $($tokenMatch.Groups[1].Value)" `
        -ForegroundColor Yellow
    Write-Host "Bu anahtarı saklayın; ilk yönetici hesabı oluşturulduktan sonra geçersiz olur."
}
else {
    Write-Host "İlk kurulum daha önce tamamlanmış olabilir. Gerekirse 'docker compose --project-name afad-gorev-takip -f compose.yaml logs app' komutunu çalıştırın."
}
Write-Host "Durdurmak için: docker compose --project-name afad-gorev-takip -f compose.yaml down"
Write-Host "Veri volume'unu silmek tüm kayıtları siler; 'down -v' kullanmayın."
