# AFAD Görev Takip - çevrimdışı Docker paketi

Bu klasör uygulamayı, Python çalışma zamanını ve uygulamanın Python kütüphanelerini tek Docker imaj arşivinde taşır. Kurulum sırasında Docker Hub/PyPI erişimi veya kaynak kod deposu gerekmez.

## Paketin içeriği

- `afad-gorev-takip-image.tar`: uygulama imajı ve tüm Linux taban imaj katmanları; uygulama kaynak kodu ve imaj oluşturulurken kurulan Python bağımlılıkları dahildir.
- `SHA256SUMS.txt`: imaj arşivinin bütünlük doğrulama özeti.
- `compose.yaml`: imajı ağ erişimi olmadan çalıştırmak için Compose tanımı.
- `.env.example`: yerel port ve isteğe bağlı e-posta yapılandırma örneği.
- `install-offline.ps1`: arşivi doğrular, Docker'a yükler ve uygulamayı başlatır.
- `python-packages.txt`: imaj içindeki Python paketlerinin tam sürüm listesi.

## Kurulum

Hedef bilgisayarda Linux konteyner desteği olan Docker Engine/Docker Desktop ve Docker Compose eklentisi önceden kurulmuş ve çalışıyor olmalıdır. Bu paket Docker Desktop, WSL2 veya Windows bileşenlerini içermez. Windows'ta bu klasörü hedef bilgisayara kopyalayın, PowerShell'i klasör içinde açıp çalıştırın:

```powershell
.\install-offline.ps1
```

Varsayılan adres `http://localhost:5000`'dir. Port meşgulse başka port seçin:

```powershell
.\install-offline.ps1 -Port 5001
```

Betik arşivin SHA-256 değerini doğrular ve `docker load` ile yükler. İlk açılışta tek kullanımlık yönetici kurulum anahtarını gösterir. Tarayıcıda yerel uygulama adresini açıp yönetici hesabını oluşturun. Yönetici adı, kullanıcı adı, e-posta ve şifre bu paket içerisinde yer almaz; ilk kurulumda uygulamaya girilir.

SMTP bilgilerini kurulumdan sonra uygulamada yönetici hesabıyla **Ayarlar → Sistem Ayarları** sayfasına girin. Buradan e-posta bildirimlerini etkinleştirebilir, SMTP sunucu/port ve bağlantı türünü, kullanıcı adı/parolayı, gönderen adını ve e-postalardaki uygulama bağlantısını ayarlayabilir, ardından test e-postası gönderebilirsiniz. Yeni görev bildiriminin ulaşması için ilgili şube müdürünün kullanıcı hesabında e-posta adresi kayıtlı olmalıdır. SMTP parolası uygulama veritabanında saklanır; Docker volume ve yedeklerini yetkisiz erişime karşı koruyun.

SQLite veritabanı, yüklemeler ve oturum anahtarı `afad-gorev-takip_app_data` adlı kalıcı Docker volume'unda saklanır. Konteyneri durdurmak için:

```powershell
docker compose --project-name afad-gorev-takip -f compose.yaml down
```

`down -v` komutu veritabanını ve tüm uygulama kayıtlarını siler; kullanmayın. Uygulama HTTP portunu varsayılan olarak yalnızca yerel bilgisayara açar. Kurum ağına yayınlamadan önce HTTPS reverse proxy ve güvenlik duvarı kurulumunu yapın.

Paket hazırlanma anında `requirements.txt` içindeki sürüm aralıklarından çözümlenen bağımlılıkları içerir. Sonraki kaynak kod değişiklikleri bu arşive otomatik yansımaz; güncel paket için imajı yeniden oluşturup arşivi tekrar üretin.
