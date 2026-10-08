param(
    [string]$InstallRoot = "$env:SystemDrive\inetpub\sites\AFADTakip",
    [string]$DataRoot = "$env:ProgramData\AFAD\Takip",
    [string]$SiteName = "AFAD-GorevTakip",
    [string]$AppPoolName = "AFADTakip",
    [ValidateRange(1024, 65535)]
    [int]$HttpPort = 8085,
    [string]$HostName = ""
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

$installFullPath = [System.IO.Path]::GetFullPath($InstallRoot).TrimEnd('\')
$installVolumeRoot = [System.IO.Path]::GetPathRoot($installFullPath).TrimEnd('\')
if ($installFullPath.Equals($installVolumeRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "InstallRoot cannot be a drive root."
}
$existingSite = Get-Website -Name $SiteName -ErrorAction SilentlyContinue
if ($existingSite -and
    [System.IO.Path]::GetFullPath($existingSite.PhysicalPath).TrimEnd('\') -ne $installFullPath) {
    throw "IIS'te '$SiteName' adlı başka bir site zaten var ve farklı dizini kullanıyor. -SiteName ile benzersiz bir ad seçin."
}
if ($existingSite -and $existingSite.ApplicationPool -ne $AppPoolName) {
    throw "IIS sitesi '$SiteName' zaten '$($existingSite.ApplicationPool)' havuzunu kullanıyor. Mevcut siteyi değiştirmemek için kurulumu durdurdum."
}
foreach ($site in (Get-Website | Where-Object { $_.Name -ne $SiteName })) {
    $siteRoot = [System.IO.Path]::GetFullPath($site.PhysicalPath).TrimEnd('\')
    if ($installFullPath.Equals($siteRoot, [StringComparison]::OrdinalIgnoreCase) -or
        $installFullPath.StartsWith("$siteRoot\", [StringComparison]::OrdinalIgnoreCase) -or
        $siteRoot.StartsWith("$installFullPath\", [StringComparison]::OrdinalIgnoreCase)) {
        throw "Kurulum dizini '$installFullPath', IIS sitesi '$($site.Name)' ile aynı veya iç içe. Mevcut sitelerden bağımsız bir InstallRoot seçin."
    }
}
if (-not $existingSite) {
    $portOwner = Get-Website | Where-Object {
        $_.Bindings.Collection | Where-Object {
            $parts = $_.bindingInformation -split ':', 3
            $parts.Count -eq 3 -and $parts[1] -eq "$HttpPort"
        }
    } | Select-Object -First 1
    if ($portOwner) {
        throw "HTTP portu $HttpPort, IIS sitesi '$($portOwner.Name)' tarafından kullanılıyor. Kullanılmayan farklı bir portla yeniden deneyin: .\install.ps1 -HttpPort 8095"
    }
} else {
    $expectedBinding = "*:${HttpPort}:$HostName"
    $hasExpectedBinding = $existingSite.Bindings.Collection |
        Where-Object { $_.bindingInformation -eq $expectedBinding }
    if (-not $hasExpectedBinding) {
        throw "IIS sitesi '$SiteName' var ancak beklenen binding '$expectedBinding' yok. Binding'leri otomatik değiştirmedim."
    }
}

$appPoolPath = "IIS:\AppPools\$AppPoolName"
if ((Test-Path -LiteralPath $appPoolPath) -and -not $existingSite) {
    throw "IIS'te '$AppPoolName' adlı uygulama havuzu zaten var. -AppPoolName ile benzersiz bir ad seçin."
}
if (Test-Path -LiteralPath $appPoolPath) {
    $sharedPoolSite = Get-Website | Where-Object {
        $_.Name -ne $SiteName -and $_.ApplicationPool -eq $AppPoolName
    } | Select-Object -First 1
    if ($sharedPoolSite) {
        throw "Uygulama havuzu '$AppPoolName', IIS sitesi '$($sharedPoolSite.Name)' tarafından kullanılıyor. -AppPoolName ile ayrı bir havuz adı seçin."
    }
}

$installationMarker = Join-Path $InstallRoot "AFADTakip.install-marker"
if (Test-Path -LiteralPath $InstallRoot -PathType Container) {
    $existingFiles = @(Get-ChildItem -LiteralPath $InstallRoot -Force)
    if ($existingFiles.Count -gt 0 -and -not (Test-Path -LiteralPath $installationMarker -PathType Leaf)) {
        throw "Kurulum dizini zaten dolu ve bu uygulama için işaretlenmemiş: $InstallRoot. Mevcut dosyalar korunacak; boş/ayrı bir dizin seçin."
    }
}

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

if (-not (Test-Path -LiteralPath $appPoolPath)) {
    New-WebAppPool -Name $AppPoolName | Out-Null
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

$appPoolIdentity = "IIS AppPool\$AppPoolName"
& icacls $InstallRoot /grant "${appPoolIdentity}:(OI)(CI)RX" /T | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Uygulama dosyası okuma izinleri ayarlanamadı." }
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
$variables = @($platform.environmentVariables.environmentVariable)
($variables | Where-Object { $_.name -eq "DATA_DIR" } |
    Select-Object -First 1).value = $dataPath
$config.Save($configPath)

$env:DATA_DIR = $dataPath
$prepareOutput = & $venvPython (Join-Path $InstallRoot "winserver_server.py") --prepare-only 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Uygulama veritabanı başlatılamadı: $($prepareOutput -join "`n")"
}

if (-not $existingSite) {
    $website = New-Website -Name $SiteName -PhysicalPath $InstallRoot `
        -ApplicationPool $AppPoolName -IPAddress "*" -Port $HttpPort `
        -HostHeader $HostName
    if (-not $website) {
        throw "Ayrı IIS sitesi '$SiteName' oluşturulamadı."
    }
}

Write-Host "`nUygulama dosyaları kuruldu: $InstallRoot" -ForegroundColor Green
Write-Host "Kalıcı veriler: $dataPath"
Write-Host "Ayrı IIS sitesi: $SiteName (uygulama havuzu: $AppPoolName)"
Write-Host "Web kökü: $InstallRoot"
if ($HostName) {
    $httpHost = $HostName
    Write-Host "IIS host adı: $HostName (DNS kaydının bu sunucuya yönlendiğini doğrulayın)"
} else {
    $httpHost = [System.Net.Dns]::GetHostName()
}
Write-Host "HTTP adresi: http://${httpHost}:$HttpPort"
Write-Host "HttpPlatformHandler, web.config içindeki Waitress sunucusunu yönetir."
Write-Host "Mevcut IIS sitelerinin binding'leri ve web kökleri değiştirilmedi."
Write-Host "HTTPS kullanacaksanız bu siteye ayrı HTTPS binding/sertifika ekleyin; sonra web.config içinde SESSION_COOKIE_SECURE=true ayarlayın."
Write-Host "İlk kurulum bilgisi:"
$prepareOutput | ForEach-Object { Write-Host $_ -ForegroundColor Yellow }
