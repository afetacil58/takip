# AFAD Görev Takip - Windows Server paketi

Bu paket uygulamayı Windows Server üzerinde IIS ve IIS **HttpPlatformHandler** arkasında, Waitress WSGI sunucusuyla çalıştırır. Docker, Gunicorn veya Linux gerekmez. Python ve uygulamanın Python bağımlılıkları paketle birlikte gelir; kurulum internet bağlantısı olmadan yapılabilir.

## Paket içeriği ve gereksinimler

- `python-3.12.10-amd64.exe`: x64 Python çalışma zamanı kurucusu.
- `afad-gorev-takip-app.zip`: uygulamanın kaynak kodu, şablonları ve statik dosyaları.
- `wheelhouse/`: Windows x64 / Python 3.12 için gereken Python paketleri.
- `install.ps1`: Python ortamı, uygulama dosyaları ve kalıcı veri klasörünü kurar.
- `requirements.txt`: kurulu Python paketlerinin sabit sürümleri.
- `web.config`: IIS HttpPlatformHandler yapılandırması.
- `SHA256SUMS.txt`: paket dosyalarının bütünlük kontrolü.

Hedef sunucu Windows Server x64 olmalı. **IIS Web Server** rolü ve yönetim araçları ile IIS'in **HttpPlatformHandler x64** modülü önceden kurulmalıdır. Handler kurulumu Microsoft'un [HttpPlatformHandler indirme sayfasından](https://www.iis.net/downloads/microsoft/httpplatformhandler) yapılabilir. Uygulama bağımlılıkları ve Python kurucusu bu pakette çevrimdışı olarak bulunur.

## Kurulum

1. `winserver` klasörünün tamamını sunucuya aktarın ve yönetici PowerShell açın.
2. Paket klasöründe çalıştırın:

   ```powershell
   .\install.ps1
   ```

3. Betik, Python 3.12'yi kurar, sanal ortamı ve wheelhouse bağımlılıklarını kurar, veritabanını başlatır ve IIS yapılandırmasını hazırlar. İlk kurulum için çıktıda görünen tek kullanımlık yönetici kurulum anahtarını saklayın.
4. IIS Manager'da `AFADTakip` adında bir **Application Pool** oluşturun; **.NET CLR Version: No Managed Code** ve **Managed pipeline mode: Integrated** seçin. Kimlik **ApplicationPoolIdentity** olmalıdır.
5. Yeni bir IIS web sitesi oluşturun:
   - Fiziksel yol: `C:\Program Files\AFAD\Takip\app`
   - Application Pool: `AFADTakip`
   - Sunucu adı ve port: kurumunuzun IIS standardına göre belirleyin.
6. Siteye HTTPS binding ve geçerli TLS sertifikası ekleyin. Dış kullanıma açmadan önce `app\web.config` içindeki `<environmentVariables>` bölümüne aşağıdaki girdiyi ekleyin ve uygulama havuzunu geri dönüştürün:

   ```xml
   <environmentVariable name="SESSION_COOKIE_SECURE" value="true" />
   ```

7. HTTPS adresinde `/setup` sayfasını açıp kurulum anahtarıyla ilk yönetici hesabını oluşturun. SMTP, uygulama içindeki **Ayarlar → Sistem Ayarları** sayfasından yapılandırılır.

IIS HttpPlatformHandler, Waitress sürecini yönetir ve uygulamayı yalnızca `127.0.0.1` üzerinde dinletir; IIS gelen HTTP/HTTPS isteklerini uygulamaya aktarır. Uygulama veritabanı ve yüklemeler `C:\ProgramData\AFAD\Takip\data` altında kalıcıdır. Kod dizini `Program Files` altında, veri ve log dizinleri ise ayrı konumdadır.

## Yönetim ve yedekleme

- Uygulama stdout/stderr logları: `C:\ProgramData\AFAD\Takip\logs`
- Veritabanı: `C:\ProgramData\AFAD\Takip\data\gorev_takip.db`
- Yüklemeler: `C:\ProgramData\AFAD\Takip\data\uploads`
- Yedekleme öncesi IIS Manager'dan ilgili uygulama havuzunu durdurun; veritabanı ve `uploads` klasörünü birlikte yedekleyin. Yedekleri erişim kontrollü ve şifreli saklayın.
- Uygulamayı güncellerken önce yedek alın. Yeni paketi kurmadan önce mevcut siteyi/application pool'u durdurun; mevcut kurulum klasörünün üzerine installer yazmaz. Var olan kurulumun güncellenmesi için kontrollü yedek/geri alma adımları gerekir.
- SMTP parolası uygulama veritabanında saklanır. Veritabanı dosyası ve yedeklerine yalnızca IIS uygulama havuzu kimliği ve sunucu yöneticileri erişebilmelidir.

Varsayılan site 80/443 için bağlama veya TLS sertifikası otomatik oluşturmaz; bunlar kurumun DNS, güvenlik duvarı ve sertifika politikasına göre IIS Manager'da yapılmalıdır.
