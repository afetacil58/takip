param(
    [string]$InstallRoot = "$env:ProgramFiles\AFAD\Takip",
    [string]$DataRoot = "$env:ProgramData\AFAD\Takip"
)

$ErrorActionPreference = "Stop"
$packageRoot = $PSScriptRoot
$pythonVersion = "3.12.10"
$pythonInstaller = Join-Path $packageRoot "python-$pythonVersion-amd64.exe"
$applicationArchive = Join-Path $packageRoot "afad-gorev-takip-app.zip"
$wheelhouse = Join-Path $packageRoot "wheelhouse"
$checksumFile = Join-Path $packageRoot "SHA256SUMS.txt"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "PowerShell'i Yönetici olarak açıp bu betiği tekrar çalıştırın."
}

foreach ($requiredPath in @($pythonInstaller, $applicationArchive, $wheelhouse, $checksumFile)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Paket dosyası bulunamadı: $requiredPath"
    }
}

$checksumEntries = Get-Content -LiteralPath $checksumFile
if (-not $checksumEntries) {
    throw "SHA256SUMS.txt boş veya okunamıyor."
}
foreach ($entry in $checksumEntries) {
    if ($entry -notmatch '^([A-Fa-f0-9]{64})\s+\*(.+)$') {
        throw "SHA256SUMS.txt satırı geçersiz: $entry"
    }
    $expectedHash = $Matches[1].ToLowerInvariant()
    $relativePath = $Matches[2]
    $filePath = Join-Path $packageRoot $relativePath
    if (-not (Test-Path -LiteralPath $filePath -PathType Leaf)) {
        throw "Paket dosyası eksik: $relativePath"
    }
    $actualHash = (Get-FileHash -LiteralPath $filePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHash) {
        throw "Paket dosyası SHA-256 doğrulamasından geçmedi: $relativePath"
    }
}
Write-Host "Paket dosyalarının SHA-256 özetleri doğrulandı." -ForegroundColor Green

if (Test-Path -LiteralPath $InstallRoot) {
    throw "Kurulum klasörü zaten var: $InstallRoot. Mevcut verilerin üzerine yazmamak için kurulumu durdurdum."
}

$iisModule = Get-Module -ListAvailable -Name WebAdministration |
    Select-Object -First 1
if (-not $iisModule) {
    throw "IIS WebAdministration bulunamadı. Önce Windows Server'da IIS rolünü ve yönetim araçlarını kurun."
}
Import-Module WebAdministration
if (-not (Get-WebGlobalModule -Name httpPlatformHandler -ErrorAction SilentlyContinue)) {
    throw "IIS HttpPlatformHandler bulunamadı. https://www.iis.net/downloads/microsoft/httpplatformhandler adresinden x64 modülünü kurup betiği yeniden çalıştırın."
}

$pythonHome = Join-Path $env:ProgramFiles "Python312"
$python = Join-Path $pythonHome "python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "Python $pythonVersion x64 kuruluyor..." -ForegroundColor Cyan
    $process = Start-Process -FilePath $pythonInstaller `
        -ArgumentList @("/quiet", "InstallAllUsers=1", "TargetDir=`"$pythonHome`"", "Include_pip=1", "Include_launcher=0", "Include_test=0", "PrependPath=0") `
        -Wait -PassThru
    if ($process.ExitCode -notin @(0, 3010)) {
        throw "Python kurulumu başarısız oldu (kod $($process.ExitCode))."
    }
}

$appRoot = Join-Path $InstallRoot "app"
$venv = Join-Path $InstallRoot "venv"
$dataPath = Join-Path $DataRoot "data"
$logsPath = Join-Path $DataRoot "logs"
New-Item -ItemType Directory -Path $appRoot, $dataPath, $logsPath -Force | Out-Null
Expand-Archive -LiteralPath $applicationArchive -DestinationPath $appRoot

Write-Host "Python sanal ortamı ve çevrimdışı bağımlılıklar kuruluyor..." -ForegroundColor Cyan
& $python -m venv $venv
if ($LASTEXITCODE -ne 0) { throw "Python sanal ortamı oluşturulamadı." }
$venvPython = Join-Path $venv "Scripts\python.exe"
& $venvPython -m pip install --no-index --find-links $wheelhouse -r (Join-Path $packageRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Çevrimdışı Python bağımlılıkları kurulamadı." }

$appPoolIdentity = "IIS AppPool\AFADTakip"
& icacls $dataPath /grant "${appPoolIdentity}:(OI)(CI)M" /T | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Uygulama veri klasörü izinleri ayarlanamadı." }
& icacls $logsPath /grant "${appPoolIdentity}:(OI)(CI)M" /T | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Uygulama log klasörü izinleri ayarlanamadı." }

$configPath = Join-Path $appRoot "web.config"
Copy-Item -LiteralPath (Join-Path $packageRoot "web.config") -Destination $configPath
$config = [xml](Get-Content -LiteralPath $configPath -Raw)
$platform = $config.configuration.'system.webServer'.httpPlatform
$platform.processPath = $venvPython
$platform.arguments = '"' + (Join-Path $appRoot "winserver_server.py") + '"'
$platform.stdoutLogFile = Join-Path $logsPath "stdout"
$platform.environmentVariables.environmentVariable |
    Where-Object { $_.name -eq "DATA_DIR" } |
    ForEach-Object { $_.value = $dataPath }
$config.Save($configPath)

$env:DATA_DIR = $dataPath
$prepareOutput = & $venvPython (Join-Path $appRoot "winserver_server.py") --prepare-only 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Uygulama veritabanı başlatılamadı: $($prepareOutput -join "`n")"
}

Write-Host "`nUygulama dosyaları kuruldu: $appRoot" -ForegroundColor Green
Write-Host "Kalıcı veriler: $dataPath"
Write-Host "IIS uygulama havuzu adı: AFADTakip (kimlik: ApplicationPoolIdentity)"
Write-Host "IIS web sitesi kök klasörü olarak şu yolu kullanın: $appRoot"
Write-Host "IIS'te AFADTakip adlı uygulama havuzu oluşturup .NET CLR ayarını 'No Managed Code' yapın."
Write-Host "HttpPlatformHandler, web.config içindeki Waitress sunucusunu yönetir."
Write-Host "Önce HTTPS bağlamasını yapılandırın; dış erişimden önce web.config içinde SESSION_COOKIE_SECURE=true ekleyin."
Write-Host "İlk kurulum bilgisi:"
$prepareOutput | ForEach-Object { Write-Host $_ -ForegroundColor Yellow }
