# AFAD Görev Takip - Windows Server paketi

Bu paket uygulamayı Windows Server üzerinde IIS ve IIS **HttpPlatformHandler** arkasında, Waitress WSGI sunucusuyla çalıştırır. Docker, Gunicorn veya Linux gerekmez. Python ve uygulamanın Python bağımlılıkları paketle birlikte gelir; kurulum internet bağlantısı olmadan yapılabilir.

## Paket içeriği ve gereksinimler

- `python-3.12.10-amd64.exe`: x64 Python çalışma zamanı kurucusu.
- `httpPlatformHandler_amd64.msi`: Microsoft'un resmi IIS HttpPlatformHandler x64 kurucusu; betik eksikse sessiz kurar.
- `afad-gorev-takip-app.zip`: uygulamanın kaynak kodu, şablonları ve statik dosyaları.
- `wwwroot/`: uygulama dosyalarının ayrı IIS web kökü için hazır dizin yapısı.
- `afad-gorev-takip-wwwroot.zip`: `wwwroot/` içeriğinin kök dizin yapısını koruyan kopyası; yalnızca uygulamaya ayrılmış boş bir fiziksel dizine açın, mevcut sitenin köküne açmayın.
- `wheelhouse/`: Windows x64 / Python 3.12 için gereken Python paketleri.
- `install.ps1`: Python ortamını ve uygulamayı kurar, ayrı IIS application pool/site oluşturur.
- `requirements.txt`: kurulu Python paketlerinin sabit sürümleri.
- `SHA256SUMS.txt`: paket dosyalarının bütünlük kontrolü.

Hedef sunucu Windows Server x64 olmalı. **IIS Web Server** rolü ve yönetim araçları önceden kurulmalıdır. Python, HttpPlatformHandler ve uygulama bağımlılıkları pakette bulunduğundan kurulum çevrimdışı yapılabilir.

## Mevcut IIS sitelerine dokunmadan kurulum

Kurulum varsayılan olarak **ayrı bir IIS sitesi**, ayrı uygulama havuzu ve ayrı fiziksel klasör kullanır:

- IIS site adı: `AFAD-GorevTakip`
- Uygulama havuzu: `AFADTakip`
- Uygulama dosyaları: `C:\inetpub\sites\AFADTakip`
- HTTP portu: `8085`
- Veritabanı/yüklemeler: `C:\ProgramData\AFAD\Takip\data`
- Loglar: `C:\ProgramData\AFAD\Takip\logs`

Var olan `Default Web Site`, sitelerin binding'leri, port 80/443 ve onların web kökleri değiştirilmez. Kurulum **`C:\inetpub\wwwroot` içine dosya kopyalamaz**. HttpPlatformHandler sunucu çapında IIS modülü olarak kurulur; diğer sitelerin ayarları değişmez. Kurulum sırasında başka bir IIS sitesi seçilen portu kullanıyorsa betik durur ve çakışmayan port seçmenizi ister.

### A. Sunucuda mevcut durumu kontrol edin

1. Paket klasörünün tamamını, örneğin `C:\AFAD-Setup` içine kopyalayın. `wwwroot` klasörü ve `afad-gorev-takip-wwwroot.zip` site dosyası örneğidir; bunları çalışan sitenin `C:\inetpub\wwwroot` dizinine açmayın.
2. Server Manager'da **Web Server (IIS)** rolünün kurulu olduğunu doğrulayın. Rol eksikse yönetici PowerShell'de `Install-WindowsFeature Web-Server, Web-Mgmt-Tools -IncludeManagementTools` çalıştırıp tamamlanmasını bekleyin.
3. Mevcut IIS sitelerini ve binding'lerini kaydedin:

   ```powershell
   Import-Module WebAdministration
   Get-Website | Select-Object Name, State, PhysicalPath,
     @{Name="Bindings";Expression={$_.Bindings.Collection.bindingInformation}}
   ```

   `8085` zaten kullanımda ise aşağıdaki kurulum komutunda boşta olan başka bir port verin. Mevcut sitenin web kökünü veya binding'lerini bu kurulum için düzenlemeyin.

### B. Paketi çalıştırın

1. Yönetici PowerShell açın:

   ```powershell
   Set-Location C:\AFAD-Setup
   .\install.ps1
   ```

2. Farklı bir site adı/port/host adı veya dizin gerekiyorsa:

   ```powershell
   .\install.ps1 `
     -SiteName "AFAD-GorevTakip" `
     -AppPoolName "AFADTakip" `
     -InstallRoot "C:\inetpub\sites\AFADTakip" `
     -DataRoot "C:\ProgramData\AFAD\Takip" `
     -HttpPort 8085 `
     -HostName "gorev.ornek.gov.tr"
   ```

   `-HostName` isteğe bağlıdır; DNS kaydı sunucunun IP adresine yönelmiş olmalı. Host adı verildiğinde siteye erişim o adla yapılır. Aynı portu paylaşan IIS sitelerinde çakışmamak için benzersiz host header kullanın; varsayılan host headersız kurulum ise 8085 portunu diğer IIS sitelerine ayırır. Alternatif port 1024–65535 aralığında ve sunucuda boş olmalıdır.

3. Betik imaj/paket özetlerini denetler, IIS HttpPlatformHandler x64'ü paketteki Microsoft imzalı MSI ile kurar (gerekirse), Python 3.12 ve bağımlılıkları hazırlar, site dosyalarını yalnızca `InstallRoot` altına yerleştirir, ayrı `AFADTakip` havuzunu ve `AFAD-GorevTakip` IIS sitesini oluşturur, sonra veritabanını başlatır. Seçilen site adı, uygulama havuzu veya port başka bir IIS kaydıyla çakışırsa mevcut yapılandırmaya dokunmadan hata verir.

   Güncellemede hedef klasörde çakışan uygulama dosyaları `%ProgramData%\AFAD\Takip\backup-*` altına kopyalanır. Betik uygulama veritabanını veya yüklemeleri silmez. İlk kurulumda yazdırılan tek kullanımlık yönetici kurulum anahtarını saklayın.

### C. Uygulamaya erişim ve HTTPS

1. Kurulum tamamlandığında `-HostName` vermediyseniz `http://SUNUCU-ADI:8085/setup` adresini açın; verdiyseniz `http://gorev.ornek.gov.tr:8085/setup` gibi DNS adını kullanın. Yerel testte host adı verilmemiş kurulum için `http://localhost:8085/setup` kullanılabilir.
2. Başka bilgisayarlardan erişilecekse Windows Defender Firewall'da yalnızca gerekli istemci ağından TCP `8085` için inbound kuralı açın. Kurum politikası gerektiriyorsa uygulamayı doğrudan HTTP ile yayınlamayın; öncelikle HTTPS yapılandırın.
3. Tercih edilen üretim yayını: IIS Manager'da **AFAD-GorevTakip** sitesine bu uygulama için DNS adına ait ayrı bir HTTPS binding (genellikle 443, SNI etkin ve ilgili sertifika seçili) ekleyin. Var olan sitenin binding veya sertifikasını silmeyin/değiştirmeyin; aynı IP/443 kullanılıyorsa ayrı host name ve SNI gerekir.
4. HTTPS çalıştığını doğruladıktan sonra `C:\inetpub\sites\AFADTakip\web.config` içindeki `<environmentVariables>` bölümüne şu satırı ekleyin ve yalnızca `AFADTakip` havuzunu recycle edin:

   ```xml
   <environmentVariable name="SESSION_COOKIE_SECURE" value="true" />
   ```

5. HTTPS adresinin `/setup` sayfasında kurulum anahtarıyla ilk yönetici hesabını oluşturun. SMTP, uygulamadaki **Ayarlar → Sistem Ayarları** sayfasından yapılandırılır.

IIS HttpPlatformHandler, Waitress sürecini yönetir ve uygulamayı yalnızca `127.0.0.1` üzerinde dinletir; IIS gelen istekleri yerel sürece aktarır. Python sanal ortamı `C:\inetpub\sites\AFADTakip\venv` altında bulunur. Var olan sitelerde değişiklik gerekmez.

## Yönetim ve yedekleme

- Uygulama stdout/stderr logları: `C:\ProgramData\AFAD\Takip\logs`
- Veritabanı: `C:\ProgramData\AFAD\Takip\data\gorev_takip.db`
- Yüklemeler: `C:\ProgramData\AFAD\Takip\data\uploads`
- Siteyi durdurma/başlatma: IIS Manager'da yalnızca `AFAD-GorevTakip` sitesini ve `AFADTakip` application pool'unu stop/start edin. Diğer sitelere dokunmayın.
- Yedekleme öncesi IIS Manager'dan ilgili uygulama havuzunu durdurun; veritabanı ve `uploads` klasörünü birlikte yedekleyin. Yedekleri erişim kontrollü ve şifreli saklayın.
- Uygulamayı güncellerken önce veritabanı ve `uploads` yedeği alın. Yeni paketi kurmadan önce mevcut siteyi/application pool'u durdurun. Installer çakışan uygulama dosyalarını otomatik olarak yedekler; uygulama verilerini güncellemez veya silmez.
- SMTP parolası uygulama veritabanında saklanır. Veritabanı dosyası ve yedeklerine yalnızca IIS uygulama havuzu kimliği ve sunucu yöneticileri erişebilmelidir.

## Geri alma

1. IIS Manager'da yalnızca `AFAD-GorevTakip` sitesini ve `AFADTakip` application pool'unu durdurup kaldırın. Diğer siteleri veya onların binding'lerini değiştirmeyin.
2. `C:\inetpub\sites\AFADTakip` uygulama klasörünü kaldırmadan önce uygulama dosyalarını ve gerekiyorsa logları yedekleyin. Veritabanı ve yüklemeler ayrı olan `C:\ProgramData\AFAD\Takip\data` dizinindedir; bu dizini silmek kullanıcı verisini kalıcı olarak siler.
3. `AFADTakip` havuzunu yalnızca artık başka hiçbir site kullanmıyorsa kaldırın. Python ve HttpPlatformHandler sunucu genelinde başka uygulamalarca kullanılabileceğinden bunları otomatik kaldırmayın.

Varsayılan kurulum 8085 HTTP kullanır; 80/443 binding'i veya TLS sertifikasını otomatik oluşturmaz. Var olan IIS sitesiyle ortak binding/sertifika üzerine yazılmaz.
