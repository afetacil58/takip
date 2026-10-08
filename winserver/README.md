# AFAD Görev Takip - Windows Server paketi

Bu paket uygulamayı Windows Server üzerinde IIS ve IIS **HttpPlatformHandler** arkasında, Waitress WSGI sunucusuyla çalıştırır. Docker, Gunicorn veya Linux gerekmez. Python ve uygulamanın Python bağımlılıkları paketle birlikte gelir; kurulum internet bağlantısı olmadan yapılabilir.

## Paket içeriği ve gereksinimler

- `python-3.12.10-amd64.exe`: x64 Python çalışma zamanı kurucusu.
- `httpPlatformHandler_amd64.msi`: Microsoft'un resmi IIS HttpPlatformHandler x64 kurucusu; betik eksikse sessiz kurar.
- `afad-gorev-takip-app.zip`: uygulamanın kaynak kodu, şablonları ve statik dosyaları.
- `wwwroot/`: uygulama dosyalarının IIS web köküne kopyalanmaya hazır dizin yapısı.
- `afad-gorev-takip-wwwroot.zip`: `wwwroot/` içeriğinin kök dizin yapısını koruyan kopyası; doğrudan web köküne açılabilir.
- `wheelhouse/`: Windows x64 / Python 3.12 için gereken Python paketleri.
- `install.ps1`: Python ortamı, uygulama dosyaları ve kalıcı veri klasörünü kurar.
- `requirements.txt`: kurulu Python paketlerinin sabit sürümleri.
- `SHA256SUMS.txt`: paket dosyalarının bütünlük kontrolü.

Hedef sunucu Windows Server x64 olmalı. **IIS Web Server** rolü ve yönetim araçları önceden kurulmalıdır. Python, HttpPlatformHandler ve uygulama bağımlılıkları pakette bulunduğundan kurulum çevrimdışı yapılabilir.

## Kurulum

1. `winserver` klasörünün tamamını sunucuya, örneğin `C:\AFAD-Setup` konumuna kopyalayın. Kurulum paketinin tamamını `wwwroot` içine kopyalamayın. Yalnızca hazır site dosyalarını elle yerleştirmek isterseniz `afad-gorev-takip-wwwroot.zip` arşivini `C:\inetpub\wwwroot` içine açabilirsiniz; yine de Python, HttpPlatformHandler, izinler ve IIS uygulama havuzu için sonraki kurulum adımlarını çalıştırın.
2. Yönetici PowerShell açın ve kurulum klasöründe betiği çalıştırın:

   ```powershell
   Set-Location C:\AFAD-Setup
   .\install.ps1
   ```

3. Betik HttpPlatformHandler yoksa paketteki MSI ile kurar, uygulama dosyalarını doğrudan `C:\inetpub\wwwroot` altına kopyalar, Python sanal ortamı ve bağımlılıkları kurup veritabanını hazırlar. İlk kurulum için çıktıda görünen tek kullanımlık yönetici kurulum anahtarını saklayın.
4. IIS Manager'da `AFADTakip` adında bir **Application Pool** oluşturun; **.NET CLR Version: No Managed Code** ve **Managed pipeline mode: Integrated** seçin. Kimlik **ApplicationPoolIdentity** olmalıdır. Mevcut **Default Web Site**'ı kullanabilir veya yeni site açabilirsiniz.
5. IIS sitesini şu web köküne yönlendirin:
   - Fiziksel yol: `C:\inetpub\wwwroot`
   - Application Pool: `AFADTakip`
   - Sunucu adı ve port: kurumunuzun IIS standardına göre belirleyin.
6. Siteye HTTPS binding ve geçerli TLS sertifikası ekleyin. Dış kullanıma açmadan önce `C:\inetpub\wwwroot\web.config` içindeki `<environmentVariables>` bölümüne aşağıdaki girdiyi ekleyin ve uygulama havuzunu geri dönüştürün:

   ```xml
   <environmentVariable name="SESSION_COOKIE_SECURE" value="true" />
   ```

7. HTTPS adresinde `/setup` sayfasını açıp kurulum anahtarıyla ilk yönetici hesabını oluşturun. SMTP, uygulama içindeki **Ayarlar → Sistem Ayarları** sayfasından yapılandırılır.

IIS HttpPlatformHandler, Waitress sürecini yönetir ve uygulamayı yalnızca `127.0.0.1` üzerinde dinletir; IIS gelen HTTP/HTTPS isteklerini uygulamaya aktarır. Uygulama kodu ve `web.config` doğrudan `C:\inetpub\wwwroot` altındadır. Python sanal ortamı `C:\inetpub\wwwroot\venv`; kalıcı veriler ve loglar `C:\ProgramData\AFAD\Takip` altındadır. Kurulum önceden var olan uygulama dosyalarının üzerine yazmadan önce bunları `%ProgramData%\AFAD\Takip\backup-*` altına yedekler.

## Yönetim ve yedekleme

- Uygulama stdout/stderr logları: `C:\ProgramData\AFAD\Takip\logs`
- Veritabanı: `C:\ProgramData\AFAD\Takip\data\gorev_takip.db`
- Yüklemeler: `C:\ProgramData\AFAD\Takip\data\uploads`
- Yedekleme öncesi IIS Manager'dan ilgili uygulama havuzunu durdurun; veritabanı ve `uploads` klasörünü birlikte yedekleyin. Yedekleri erişim kontrollü ve şifreli saklayın.
- Uygulamayı güncellerken önce veritabanı ve `uploads` yedeği alın. Yeni paketi kurmadan önce mevcut siteyi/application pool'u durdurun. Installer çakışan uygulama dosyalarını otomatik olarak yedekler; uygulama verilerini güncellemez veya silmez.
- SMTP parolası uygulama veritabanında saklanır. Veritabanı dosyası ve yedeklerine yalnızca IIS uygulama havuzu kimliği ve sunucu yöneticileri erişebilmelidir.

Varsayılan site 80/443 için bağlama veya TLS sertifikası otomatik oluşturmaz; bunlar kurumun DNS, güvenlik duvarı ve sertifika politikasına göre IIS Manager'da yapılmalıdır.
