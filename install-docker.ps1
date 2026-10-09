param(
    [ValidateRange(0, 65535)]
    [int]$Port = 0,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

function Test-LocalPortAvailable {
    param([int]$CandidatePort)
    $listener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback,
        $CandidatePort
    )
    try {
        $listener.Start()
        return $true
    }
    catch [System.Net.Sockets.SocketException] {
        return $false
    }
    finally {
        $listener.Stop()
    }
}

function Get-DotEnvValue {
    param([string[]]$Lines, [string]$Name)
    foreach ($line in $Lines) {
        if ($line -match "^\s*$([regex]::Escape($Name))\s*=\s*(.*?)\s*$") {
            return $Matches[1].Trim('"', "'")
        }
    }
    return $null
}

function Set-DotEnvValue {
    param([string]$Path, [string[]]$Lines, [string]$Name, [string]$Value)
    $updated = [System.Collections.Generic.List[string]]::new()
    $found = $false
    foreach ($line in $Lines) {
        if (-not $found -and $line -match "^\s*$([regex]::Escape($Name))\s*=") {
            $updated.Add("$Name=$Value")
            $found = $true
        }
        else {
            $updated.Add($line)
        }
    }
    if (-not $found) {
        $updated.Add("$Name=$Value")
    }
    [System.IO.File]::WriteAllLines(
        $Path,
        $updated,
        [System.Text.UTF8Encoding]::new($false)
    )
}

Write-Host "AFAD Görev Takip - Windows Docker kurulumu" -ForegroundColor Cyan

$desktopExe = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
$userDesktopExe = Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\Docker Desktop.exe"
if (-not (Test-Path -LiteralPath $desktopExe) -and
    (Test-Path -LiteralPath $userDesktopExe)) {
    throw "Docker Desktop yalnızca mevcut Windows kullanıcısına kurulmuş. Makine-geneli kurulumdan önce Ayarlar > Uygulamalar bölümünden bu kurulumu kaldırın, ardından betiği yönetici olarak yeniden çalıştırın."
}

if (-not $SkipInstall -and -not (Test-Path -LiteralPath $desktopExe)) {
    if (-not (Test-Administrator)) {
        throw "Docker Desktop kurmak için PowerShell'i 'Yönetici olarak çalıştır' ile açıp betiği yeniden çalıştırın."
    }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget bulunamadı. Windows App Installer'ı kurup betiği yeniden çalıştırın."
    }

    Write-Host "Docker Desktop winget ile kuruluyor..." -ForegroundColor Yellow
    & winget install --id Docker.DockerDesktop --exact --scope machine --source winget `
        --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Desktop kurulumu başarısız oldu (winget çıkış kodu: $LASTEXITCODE)."
    }

    $desktopExe = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path -LiteralPath $desktopExe)) {
        Write-Host "Makine-geneli kurulum tamamlandı. Windows yeniden başlatma isterse yeniden başlatın; sonra betiği tekrar çalıştırın." -ForegroundColor Yellow
        return
    }
}

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw "WSL bulunamadı. Yönetici PowerShell'de 'wsl --install --no-distribution' komutunu çalıştırıp Windows'u yeniden başlatın."
}

& wsl.exe --status *> $null
if ($LASTEXITCODE -ne 0) {
    if (-not (Test-Administrator)) {
        throw "WSL2 kurulumu için yönetici PowerShell'i açın ve 'wsl --install --no-distribution' komutunu çalıştırın. Yeniden başlattıktan sonra bu betiği çalıştırın."
    }
    Write-Host "WSL2 kuruluyor. Bu işlem Windows'u yeniden başlatmayı gerektirebilir..." -ForegroundColor Yellow
    & wsl.exe --install --no-distribution
    if ($LASTEXITCODE -ne 0) {
        throw "WSL kurulumu başlatılamadı (çıkış kodu: $LASTEXITCODE). Windows'u güncelleyin ve WSL2'yi kurduktan sonra betiği tekrar çalıştırın."
    }
    Write-Host "WSL kurulumundan sonra Windows'u yeniden başlatıp bu betiği tekrar çalıştırın." -ForegroundColor Yellow
    return
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    $dockerCliDirectory = Join-Path $env:ProgramFiles "Docker\Docker\resources\bin"
    if (Test-Path -LiteralPath (Join-Path $dockerCliDirectory "docker.exe")) {
        $env:Path = "$dockerCliDirectory;$env:Path"
    }
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker CLI bulunamadı. Docker Desktop kurulumunu kontrol edip PowerShell'i yeniden açın."
    }
}

$dockerResourcesDirectory = Join-Path $env:ProgramFiles "Docker\Docker\resources\bin"
if (
    (Test-Path -LiteralPath (Join-Path $dockerResourcesDirectory "docker-credential-desktop.exe")) -and
    (($env:Path -split ";") -notcontains $dockerResourcesDirectory)
) {
    $env:Path = "$dockerResourcesDirectory;$env:Path"
}

$dockerInfo = & docker info --format '{{.OSType}}' 2>$null
if ($LASTEXITCODE -ne 0) {
    if (-not (Test-Path -LiteralPath $desktopExe)) {
        throw "Docker Desktop bulunamadı. Betiği yönetici PowerShell'de yeniden çalıştırın."
    }
    Write-Host "Docker Desktop başlatılıyor. İlk açılışta ekrandaki lisans/başlangıç adımlarını tamamlayın..." -ForegroundColor Yellow
    Start-Process -FilePath $desktopExe

    $deadline = (Get-Date).AddMinutes(5)
    do {
        Start-Sleep -Seconds 5
        $dockerInfo = & docker info --format '{{.OSType}}' 2>$null
        if ($LASTEXITCODE -eq 0) {
            break
        }
        Write-Host "Docker motoru başlatılıyor..."
    } while ((Get-Date) -lt $deadline)

    if ($LASTEXITCODE -ne 0) {
        throw "Docker motoru 5 dakika içinde hazır olmadı. Docker Desktop penceresindeki WSL2/sanallaştırma uyarılarını çözün, sonra bu betiği tekrar çalıştırın."
    }
}

if ($dockerInfo.Trim() -ne "linux") {
    throw "Docker Linux konteyner motorunda değil. Docker Desktop menüsünden 'Switch to Linux containers' seçeneğini kullanıp betiği tekrar çalıştırın."
}

& docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose eklentisi kullanılamıyor. Docker Desktop'ı güncelleyin/başlatın ve betiği tekrar çalıştırın."
}

$envFile = Join-Path $PSScriptRoot ".env"
$envExisted = Test-Path -LiteralPath $envFile
if (-not $envExisted) {
    $exampleFile = Join-Path $PSScriptRoot ".env.example"
    if (-not (Test-Path -LiteralPath $exampleFile)) {
        throw ".env.example bulunamadı."
    }
    Copy-Item -LiteralPath $exampleFile -Destination $envFile
}
$envLines = @(Get-Content -LiteralPath $envFile)
$configuredPort = Get-DotEnvValue -Lines $envLines -Name "APP_PORT"

if ($Port -gt 0) {
    $selectedPort = $Port
}
elseif ($envExisted -and $configuredPort -match "^\d+$") {
    $selectedPort = [int]$configuredPort
}
else {
    $selectedPort = 5000
    while ($selectedPort -lt 65535 -and -not (Test-LocalPortAvailable $selectedPort)) {
        $selectedPort++
    }
}

if ($selectedPort -lt 1 -or $selectedPort -gt 65535) {
    throw "Uygulama için kullanılabilir bir TCP portu bulunamadı."
}
$currentMapping = & docker compose port app 5000 2>$null
$mappedPort = $null
if ($LASTEXITCODE -eq 0 -and "$currentMapping" -match ":(\d+)\s*$") {
    $mappedPort = [int]$Matches[1]
}
if (-not (Test-LocalPortAvailable $selectedPort) -and $mappedPort -ne $selectedPort) {
    if ($Port -gt 0) {
        throw "Port $selectedPort kullanımda. Betiği başka boş bir portla çalıştırın."
    }
    $selectedPort++
    while ($selectedPort -lt 65535 -and
        -not (Test-LocalPortAvailable $selectedPort)) {
        $selectedPort++
    }
    if (-not (Test-LocalPortAvailable $selectedPort)) {
        throw "Uygulama için kullanılabilir bir TCP portu bulunamadı."
    }
    Write-Host "Seçilen port kullanımda; uygulama için $selectedPort kullanılacak." -ForegroundColor Yellow
}

Set-DotEnvValue -Path $envFile -Lines $envLines -Name "APP_PORT" -Value "$selectedPort"
$baseUrl = Get-DotEnvValue -Lines $envLines -Name "BASE_URL"
if (-not $baseUrl -or $baseUrl -eq "http://localhost:5000") {
    Set-DotEnvValue -Path $envFile -Lines @((Get-Content -LiteralPath $envFile)) `
        -Name "BASE_URL" -Value "http://localhost:$selectedPort"
}

Write-Host "Uygulama Docker ile başlatılıyor (http://localhost:$selectedPort)..." -ForegroundColor Cyan
& docker compose up -d --build
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose başlatılamadı. Hata ayrıntıları için 'docker compose logs app' komutunu çalıştırın."
}

$env:APP_PORT = "$selectedPort"
$uri = "http://localhost:$selectedPort"
$containerId = (& docker compose ps -q app | Select-Object -First 1).Trim()
$deadline = (Get-Date).AddMinutes(3)
$ready = $false
do {
    $health = ""
    if ($containerId) {
        $health = (& docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $containerId 2>$null).Trim()
    }
    if ($health -eq "healthy") {
        $ready = $true
    }
    elseif ($health -eq "unhealthy" -or $health -eq "exited") {
        break
    }
    else {
        Start-Sleep -Seconds 3
    }
} while (-not $ready -and (Get-Date) -lt $deadline)

if (-not $ready) {
    & docker compose logs --tail 80 app
    throw "Uygulama web isteğine yanıt vermedi. Docker loglarını kontrol edin."
}

try {
    $response = Invoke-WebRequest -Uri "$uri/login" -UseBasicParsing -TimeoutSec 10
    if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 500) {
        throw "Uygulama beklenmeyen HTTP durum kodu döndürdü: $($response.StatusCode)"
    }
}
catch {
    & docker compose logs --tail 80 app
    throw "Konteyner sağlıklı ancak Windows üzerinden $uri adresine erişilemiyor: $($_.Exception.Message)"
}

Write-Host "`nUygulama hazır: $uri" -ForegroundColor Green
$containerLogs = & docker compose logs --no-color --tail 100 app 2>&1
$tokenMatch = [regex]::Match(
    ($containerLogs -join "`n"),
    "Initial administrator setup token \(enter it at /setup\):\s*(\S+)"
)
if ($tokenMatch.Success) {
    Write-Host "İlk yönetici kurulum anahtarı: $($tokenMatch.Groups[1].Value)" -ForegroundColor Yellow
    Write-Host "Anahtarı saklayın; ilk yönetici hesabını oluşturduktan sonra geçersiz olur."
}
else {
    Write-Host "Kurulum zaten tamamlanmış olabilir. İlk kurulum gerekiyorsa 'docker compose logs app' ile anahtarı kontrol edin."
}
Write-Host "Durdurmak için: docker compose down"
Write-Host "Verileri silmeden durdurun; 'docker compose down -v' kalıcı veritabanı volume'unu siler." -ForegroundColor Yellow
