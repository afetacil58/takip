param(
    [string]$InstallRoot = "$env:SystemDrive\inetpub\wwwroot",
    [string]$DataRoot = "$env:ProgramData\AFAD\Takip"
)

$ErrorActionPreference = "Stop"
$packageRoot = $PSScriptRoot
$pythonVersion = "3.12.10"
$pythonInstaller = Join-Path $packageRoot "python-$pythonVersion-amd64.exe"
$httpPlatformInstaller = Join-Path $packageRoot "httpPlatformHandler_amd64.msi"
$siteSource = Join-Path $packageRoot "wwwroot"
$wheelhouse = Join-Path $packageRoot "wheelhouse"
$checksumFile = Join-Path $packageRoot "SHA256SUMS.txt"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "PowerShell'i Yönetici olarak açıp bu betiği tekrar çalıştırın."
}

foreach ($requiredPath in @($pythonInstaller, $httpPlatformInstaller, $siteSource, $wheelhouse, $checksumFile)) {
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

$iisModule = Get-Module -ListAvailable -Name WebAdministration |
    Select-Object -First 1
if (-not $iisModule) {
    throw "IIS WebAdministration bulunamadı. Önce Windows Server'da IIS rolünü ve yönetim araçlarını kurun."
}
Import-Module WebAdministration
if (-not (Get-WebGlobalModule -Name httpPlatformHandler -ErrorAction SilentlyContinue)) {
    Write-Host "IIS HttpPlatformHandler paketten kuruluyor..." -ForegroundColor Cyan
    $process = Start-Process -FilePath "$env:SystemRoot\System32\msiexec.exe" `
        -ArgumentList @("/i", "`"$httpPlatformInstaller`"", "/qn", "/norestart") `
        -Wait -PassThru
    if ($process.ExitCode -notin @(0, 3010)) {
        throw "HttpPlatformHandler kurulumu başarısız oldu (kod $($process.ExitCode))."
    }
    if ($process.ExitCode -eq 3010) {
        Write-Warning "HttpPlatformHandler kuruldu; değişikliklerin etkinleşmesi için sunucuyu yeniden başlatın."
    }
    Import-Module WebAdministration -Force
    if (-not (Get-WebGlobalModule -Name httpPlatformHandler -ErrorAction SilentlyContinue)) {
        throw "HttpPlatformHandler kuruldu ancak IIS modül kaydı görünmüyor. Sunucuyu yeniden başlatıp betiği tekrar çalıştırın."
    }
}

$appPoolPath = "IIS:\AppPools\AFADTakip"
if (-not (Test-Path -LiteralPath $appPoolPath)) {
    New-WebAppPool -Name "AFADTakip" | Out-Null
}
$appPool = Get-Item -LiteralPath $appPoolPath
$appPool.managedRuntimeVersion = ""
$appPool.processModel.identityType = 4
$appPool | Set-Item

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

$venv = Join-Path $InstallRoot "venv"
$dataPath = Join-Path $DataRoot "data"
$logsPath = Join-Path $DataRoot "logs"
New-Item -ItemType Directory -Path $InstallRoot, $dataPath, $logsPath -Force | Out-Null
$backupPath = Join-Path $DataRoot ("backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
$backedUpFiles = 0
Get-ChildItem -LiteralPath $siteSource -Recurse -File | ForEach-Object {
    $relativePath = $_.FullName.Substring($siteSource.Length).TrimStart('\')
    $targetPath = Join-Path $InstallRoot $relativePath
    if (Test-Path -LiteralPath $targetPath -PathType Leaf) {
        $backupFile = Join-Path $backupPath $relativePath
        New-Item -ItemType Directory -Path (Split-Path -Parent $backupFile) -Force | Out-Null
        Copy-Item -LiteralPath $targetPath -Destination $backupFile -Force
        $backedUpFiles++
    }
}
if ($backedUpFiles -gt 0) {
    Write-Host "Var olan $backedUpFiles dosyanın yedeği alındı: $backupPath" -ForegroundColor Yellow
}
Copy-Item -Path (Join-Path $siteSource "*") -Destination $InstallRoot -Recurse -Force

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

$configPath = Join-Path $InstallRoot "web.config"
$config = [xml](Get-Content -LiteralPath $configPath -Raw)
$platform = $config.configuration.'system.webServer'.httpPlatform
$platform.processPath = $venvPython
$platform.arguments = '"' + (Join-Path $InstallRoot "winserver_server.py") + '"'
$platform.stdoutLogFile = Join-Path $logsPath "stdout"
$platform.environmentVariables.environmentVariable |
    Where-Object { $_.name -eq "DATA_DIR" } |
    ForEach-Object { $_.value = $dataPath }
$config.Save($configPath)

$env:DATA_DIR = $dataPath
$prepareOutput = & $venvPython (Join-Path $InstallRoot "winserver_server.py") --prepare-only 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Uygulama veritabanı başlatılamadı: $($prepareOutput -join "`n")"
}

Write-Host "`nUygulama dosyaları kuruldu: $InstallRoot" -ForegroundColor Green
Write-Host "Kalıcı veriler: $dataPath"
Write-Host "IIS uygulama havuzu hazır: AFADTakip (No Managed Code, ApplicationPoolIdentity)"
Write-Host "IIS web sitesi kök klasörü olarak şu yolu kullanın: $InstallRoot"
Write-Host "IIS Manager'da sitenizin fiziksel yolunu $InstallRoot, uygulama havuzunu AFADTakip yapın."
Write-Host "HttpPlatformHandler, web.config içindeki Waitress sunucusunu yönetir."
Write-Host "Önce HTTPS bağlamasını yapılandırın; dış erişimden önce web.config içinde SESSION_COOKIE_SECURE=true ekleyin."
Write-Host "İlk kurulum bilgisi:"
$prepareOutput | ForEach-Object { Write-Host $_ -ForegroundColor Yellow }
