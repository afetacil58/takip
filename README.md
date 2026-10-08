# AFAD Görev Takip Sistemi

Şube müdürlerine atanan işlemleri tek merkezden izlemek için tasarlanmış bir web uygulaması.
Hiçbir internet bağlantısına ihtiyaç duymaz — kurum içi ağda veya tek bir bilgisayarda çalışır.

## Bugün hemen test etmek için (kendi bilgisayarında)

1. Python 3.9+ kurulu olmalı (çoğu Windows/Mac bilgisayarda zaten vardır, yoksa python.org'dan indirin).
2. Bu klasörü açın, terminal/CMD ile içine girin:
   ```
   pip install -r requirements.txt
   python app.py
   ```
3. Tarayıcıda **http://127.0.0.1:5000** adresini açın.
4. İlk açılışta **İlk Kurulum** sayfasından yönetici adını, kullanıcı adını, isteğe bağlı e-posta adresini ve güçlü bir şifreyi belirleyin. Uygulama artık varsayılan kullanıcı veya şifre oluşturmaz.

## Nasıl kullanılır

1. **"Şube Müdürleri"** sayfasından her şube müdürü için bir hesap açın (ad-soyad, şube adı, kullanıcı adı, geçici şifre).
2. Şube müdürlerine kendi kullanıcı adı/şifrelerini iletin — üretim kurulumunda kurum içi DNS adı ve HTTPS reverse proxy adresinden giriş yapıp kendilerine atanan işlemleri görüp güncelleyebilirler.
3. **"+ Yeni İşlem"** ile bir işlem oluşturup ilgili şube müdürüne atayın, öncelik ve termin tarihi verin.
4. Ana panelde:
   - Tüm şubelerin özet durumu (bekleyen/devam eden/tamamlanan) tek ekranda görünür.
   - Termini geçmiş işlemler kırmızı vurgulanır ve "gecikti" etiketiyle işaretlenir.
   - Şubeye, sorumluya veya duruma göre filtreleme yapılabilir.
5. Şube müdürü bir işleme girip durumunu güncellediğinde ve not eklediğinde, bu geçmiş işlem detayında saklanır — kim ne zaman ne yapmış görülebilir.

## Aylık faaliyet raporu modülü

Oturum açtıktan sonra **Aylık Faaliyet** menüsündeki **Kayıt Girişi** ve **Aylık Rapor** alt menülerinden modülü kullanabilirsiniz. Kayıt girişi faaliyetleri ekleme, düzenleme, silme ve eski verileri içe aktarma ekranıdır; aylık rapor ekranında dönem seçimi, rapor metinleri, logolar, yazdırma/PDF çıktısı ve onay/kilitleme bulunur. Faaliyetler SQLite veritabanında saklanır. Şube müdürleri yalnızca kendi şubelerinin kayıtlarını görüp yönetebilir; yöneticiler tüm şubeleri görüntüleyip belirli bir şube müdürü adına kayıt ekleyebilir ve raporu onaylayabilir.

Eski HTML prototipinde tarayıcıya kaydedilmiş kayıtları taşımak için prototip sayfasındaki **JSON yedeği indir** düğmesini kullanın. Uygulamadaki Aylık Faaliyet Raporu sayfasında bir şube müdürü seçip bu JSON dosyasını içe aktarın. Aynı yedek tekrar yüklense bile faaliyet kimliği veritabanında benzersiz tutulduğu için ikinci kopya oluşmaz. İçe aktarma eski tarayıcı verisini silmez; yedek dosyasını aktarım doğrulanana kadar saklayın. Prototip doğrudan `file://` ile açılmışsa web uygulaması tarayıcı güvenlik sınırı nedeniyle o sayfanın `localStorage` alanını okuyamaz; bu nedenle JSON aktarımını kullanın.

## Kurum sunucusuna kalıcı kurulum (herkesin erişebilmesi için)

Şu an `python app.py` ile çalıştırdığınızda uygulama **sadece geliştirme amaçlıdır** ve tek kullanıcı testi içindir.
Şube müdürlerinin kendi bilgisayarlarından erişebilmesi için:

1. Kurum içi bir Linux sunucuya (veya mevcut bir Windows sunucuya) bu klasörü kopyalayın.
2. Gerçek bir üretim sunucusu ile çalıştırın. Uygulama imzalama anahtarını kalıcı, gizli bir ortam değişkeni olarak tanımlayın; tüm worker'lar aynı değeri kullanmalıdır:
   ```
   export SECRET_KEY='<uzun-rastgele-ve-kalici-deger>'
   gunicorn --preload --workers 4 --bind 127.0.0.1:5000 wsgi:app
   ```
3. Gunicorn'u systemd gibi bir servis yöneticisiyle çalıştırın; SQLite veritabanı ve yükleme dizini servis kullanıcısına yazılabilir, yedeklenebilir kalıcı bir diskte olmalıdır.
4. Uygulamayı doğrudan internete açmayın. Nginx/Apache gibi bir reverse proxy üzerinden TLS/HTTPS sağlayın; güvenlik duvarında Gunicorn portunu dış erişime kapatıp yalnızca proxy'nin erişmesine izin verin.
5. Örnek Nginx reverse proxy yapılandırması:
   ```
   server {
       listen 443 ssl;
       server_name gorevtakip.example.org;
       ssl_certificate /etc/ssl/certs/gorevtakip.crt;
       ssl_certificate_key /etc/ssl/private/gorevtakip.key;
       client_max_body_size 15m;
       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```
   Uygulama `X-Forwarded-*` başlıklarını doğrudan güvenilir saymaz; TLS sonlandırmayı reverse proxy'de yapın ve Gunicorn portunu yalnızca yerel proxy'ye bağlayın.

### Docker ile kurulum (Linux veya Docker Desktop)

Docker Engine ve Docker Compose eklentisi kurulu olmalıdır. Özel kullanıcı bilgilerini kurulumdan önce dosyalara yazmanız gerekmez:

**Windows'ta Docker Desktop'ı makineye bir kez kurup uygulamayı başlatmak için** proje klasöründeki PowerShell'i yönetici olarak açın ve çalıştırın:
```
.\install-docker.ps1
```
Kuruluşunuz PowerShell yürütme ilkesini merkezi olarak yönetiyorsa `Set-ExecutionPolicy` komutunu çalıştırmayın; betiği doğrudan başlatın. İlke değişikliği gerekirse kurum BT yöneticinize danışın.
Betik Docker Desktop'ı `winget --scope machine` ile makine-geneli kurar (kurulum mevcut değilse), WSL2 ve Docker motorunun hazır olmasını bekler, uygulamayı başlatır ve tarayıcı adresiyle tek kullanımlık kurulum anahtarını gösterir. Docker Desktop motoru bilgisayardaki Copilot oturumları arasında paylaşılır; Docker Desktop'ı her oturum veya worktree için yeniden kurmanız gerekmez. Kurulumdan sonra başlayan oturumlar Docker CLI ve ortak motora erişebilir; kurulum sırasında açık olan Copilot/terminal oturumlarının ortam değişkenlerini yenilemek için bunları kapatıp yeniden açın. Docker Desktop'ın diğer Windows oturum açmalarında da hazır olmasını istiyorsanız Docker Desktop ayarlarından **Start Docker Desktop when you sign in** seçeneğini etkinleştirin. Windows yeniden başlatma isterse bilgisayarı yeniden başlatıp betiği tekrar çalıştırın. Kullanılan port `.env` içinde saklanır; böylece sonraki `docker compose` komutları aynı adreste çalışır. Docker Desktop kapalıysa daha sonra betiği yeniden çalıştırarak Docker motorunu açabilirsiniz. İsterseniz portu elle belirleyin: `.\install-docker.ps1 -Port 5001`.

Docker motoru oturumlar arasında ortaktır; her worktree'nin Compose projesi ve veritabanı volume'u ise varsayılan olarak ayrıdır. Docker Desktop, kurum/iş amaçlı kullanım için lisans koşullarına tabi olabilir; Docker'ın güncel lisansını ve bilgisayarınızda sanallaştırma/WSL2 gereksinimlerini kontrol edin.

İnternet erişimi olmayan, Docker Engine ve Compose zaten kurulu başka bir bilgisayara dağıtmak için `docker/` klasöründe uygulama imajı ve Python bağımlılıkları tek bir `.tar` dosyasında paketlenmiştir. Arşivi, `compose.yaml` dosyasını ve `install-offline.ps1` betiğini birlikte aktarın; çevrimdışı kurulum adımları `docker/README.md` içindedir. Docker Desktop/WSL kurulum programları bu pakete dahil değildir.

### Windows Server / IIS

Windows Server üzerinde IIS ile yayınlamak için `winserver/` klasöründeki paketi kullanın. Python 3.12, Windows bağımlılıkları ve HttpPlatformHandler kurucusu paket içindedir. Kurulum ayrı `C:\inetpub\sites\AFADTakip` dizini, `AFADTakip` uygulama havuzu ve 8085 portunda yeni `AFAD-GorevTakip` IIS sitesi oluşturur; mevcut sitenin `wwwroot` klasörüne ve binding'lerine dokunmaz. Ayrıntılı ve çakışmasız kurulum, HTTPS ve güvenlik duvarı adımları `winserver/README.md` dosyasındadır.

1. Proje klasöründe uygulamayı başlatın:
   ```
   docker compose up -d --build
   ```
   İlk kurulumda Docker veritabanı ve yükleme alanını kendi kalıcı `app_data` volume'unda oluşturur. Oturum imzalama anahtarı da volume içinde güvenli rastgele bir değerle otomatik üretilir.
2. İlk yönetici kurulum anahtarını alın:
   ```
   docker compose logs app
   ```
   Çıktıdaki **Initial administrator setup token** değerini saklayın ve `.env` içindeki `APP_PORT` değerine göre `http://localhost:<APP_PORT>` adresini açın (varsayılan `5000`). Kurulum ekranında anahtarla birlikte yönetici adını, kullanıcı adını, e-posta adresini (isteğe bağlı) ve güçlü şifreyi girin. Anahtar ilk yönetici oluşturulduktan sonra geçersiz olur. Docker varsayılan olarak sadece bu bilgisayardan erişime açıktır.
3. E-posta bildirimlerini yönetici hesabıyla **Ayarlar → Sistem Ayarları** sayfasından yapılandırın. SMTP sunucusu, port, bağlantı güvenliği, kullanıcı adı/parola, gönderen adı ve uygulama adresini kaydedip test e-postası gönderebilirsiniz. Yeni görev atandığında bildirim, ilgili şube müdürünün hesabındaki e-posta adresine gönderilir. Eski kurulumlardaki SMTP `.env` değerleri varsayılan olarak kullanılmaya devam eder; yönetim sayfasında kaydedilen ayarlar bunları geçersiz kılar.

Konteyner `python:3.12-alpine` imajında root olmayan kullanıcıyla ve Gunicorn üzerinden çalışır. Uygulama sağlık kontrolü içerir; konteyner içi HTTP portu `5000`, yerel makinedeki port `.env` içindeki `APP_PORT` değeridir (varsayılan `5000`). Veritabanı, yüklenen dosyalar ve oturum anahtarı `app_data` volume'unda konteyner yeniden oluşturulsa da korunur. `docker compose down` bu volume'u silmez; **`docker compose down -v` tüm uygulama verisini siler**. Düzenli yedek alın ve volume/yedek erişimini koruyun.
HTTPS'i reverse proxy'de sonlandırıyorsanız `.env` dosyasında `SESSION_COOKIE_SECURE=true` ayarlayın. HTTP üzerinden doğrudan kullanımda bu ayarı etkinleştirmeyin; tarayıcı güvenli oturum çerezlerini HTTP isteklerinde göndermez.

## Veri nerede saklanıyor?

Yerel çalıştırmada tüm veriler `gorev_takip.db` adlı SQLite dosyasında tutulur. Docker kurulumunda SQLite veritabanı, yüklenen dosyalar ve oturum anahtarı `app_data` adlı kalıcı volume'da saklanır.
Hiçbir veri dışarıya (internete) gönderilmez — e-posta bildirimleri hariç, onlar da yalnızca sizin belirlediğiniz
SMTP sunucusuna gider.

## E-posta bildirimleri

Sistem iki tür e-posta gönderebilir:

1. **Anlık bildirim** — bir şube müdürüne yeni işlem atandığında otomatik olarak gönderilir. Ekstra kurulum gerekmez,
   sadece e-posta ayarlarını yapmanız (aşağıya bakın) ve şube müdürünün profiline e-posta adresi eklemeniz yeterlidir.
2. **Günlük özet** — gecikmiş, termini yaklaşan ve uzun süredir güncellenmeyen işlemler için her şube müdürüne
   günde bir kez özet mail. Bu, `send_reminders.py` betiğinin düzenli çalıştırılmasını gerektirir (aşağıya bakın).

### 1. E-posta ayarlarını yapın

SMTP ayarları ortam değişkenlerinden okunur; parolayı `email_config.py` içine yazmayın. Docker Compose bunları proje kökündeki `.env` dosyasından alır. Gmail için normal hesap parolası yerine Google hesabında oluşturulan "uygulama şifresi" kullanılmalıdır. Yerel olarak `python app.py` çalıştırırken aynı değişkenleri uygulamayı başlatan terminalin ortamında tanımlayın. Ayarlar yoksa e-posta gönderilmeden sistem çalışmayı sürdürür.

### 2. Şube müdürlerine e-posta adresi ekleyin

"Şube Müdürleri" sayfasından her müdürün profiline (yeni eklerken veya "Düzenle" ile sonradan) e-posta adresini girin.
E-posta adresi olmayan müdürlere bildirim gönderilmez, sistemin geri kalanı etkilenmez.

### 3. Günlük özet için zamanlayıcı kurun

`send_reminders.py` betiği çalıştırıldığında o an gecikmiş/yaklaşan/durağan işlemleri kontrol edip mail atar,
ama kendiliğinden düzenli çalışmaz — bunu işletim sisteminizin zamanlayıcısına bağlamanız gerekir:

**Linux (cron):**
```
crontab -e
```
ve şu satırı ekleyin (klasör yolunu kendinize göre değiştirin):
```
0 8 * * * cd /tam/yol/gorev-takip && /usr/bin/python3 send_reminders.py >> hatirlatma.log 2>&1
```
Bu, her sabah 08:00'de betiği çalıştırır.

**Windows (Görev Zamanlayıcı):**
Görev Zamanlayıcı'yı açın → "Temel Görev Oluştur" → tetikleyici olarak "Her gün, 08:00" seçin → eylem olarak
"Bir program başlat"ı seçip program alanına `python.exe`, bağımsız değişkenler alanına `send_reminders.py`,
başlangıç dizini alanına da proje klasörünün tam yolunu yazın.

Elle test etmek isterseniz terminalden doğrudan `python send_reminders.py` çalıştırabilirsiniz.

`python test_email.py` yalnızca ayarların yüklenip yüklenmediğini gösterir; SMTP sunucusuna bağlanmaz, parolayı yazdırmaz ve e-posta göndermez. E-posta gönderme kodunun yerel, ağ bağlantısı kurmayan testlerini `python -m unittest discover -s tests` ile çalıştırabilirsiniz. Gerçek alıcıya teslimatı doğrulamak için önce SMTP ayarlarını kurumunuzun onayladığı yöntemle yapılandırıp kontrollü bir alıcı kullanın.

## Güvenlik ve işletim notları

- Yeni yönetici/şube müdürü hesaplarına geçici şifre verilir; ilk oturumda şifre değiştirilmeden uygulamanın diğer sayfaları açılamaz. Şifreler en az 4 karakter olmalıdır. Eski hesapların şifresi ve oturumları değişmeden kalır.
- Formlar ve JSON tabanlı aylık faaliyet istekleri CSRF koruması kullanır. Denetim kaydı yönetici menüsünde son 500 değişiklik ve oturum denemesini gösterir; parola ve istek gövdeleri kaydedilmez.
- Testler GitHub Actions'ta her pull request ve `main` dalına yapılan push için çalışır.
- Şifre sıfırlama e-postayla değil, sadece yönetici tarafından yapılabiliyor.
"# takip"
### 4. Git talimatları:
**Git Yükleme Talimatları:**
```
 git remote -v
 git remote set-url origin git@github.com:afetacil58/takip.git
 git fetch origin
 git checkout main
 git pull --rebase origin main
 git status
 git add .
 git commit -m "Initial setup"
 git push -u origin main
```
