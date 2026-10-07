# AFAD Görev Takip Sistemi

Şube müdürlerine atanan işlemleri tek merkezden izlemek için basit, offline çalışan bir web uygulaması.
Hiçbir internet bağlantısına ihtiyaç duymaz — kurum içi ağda veya tek bir bilgisayarda çalışır.

## Bugün hemen test etmek için (kendi bilgisayarında)

1. Python 3.9+ kurulu olmalı (çoğu Windows/Mac bilgisayarda zaten vardır, yoksa python.org'dan indirin).
2. Bu klasörü açın, terminal/CMD ile içine girin:
   ```
   pip install -r requirements.txt
   python app.py
   ```
3. Tarayıcıda **http://127.0.0.1:5000** adresini açın.
4. Giriş yapın:
   - Kullanıcı adı: `admin`
   - Şifre: `degistir123`
   - **İlk girişten sonra parolayı mutlaka "Şifremi Değiştir" sayfasından değiştirin.**

## Nasıl kullanılır

1. **"Şube Müdürleri"** sayfasından her şube müdürü için bir hesap açın (ad-soyad, şube adı, kullanıcı adı, geçici şifre).
2. Şube müdürlerine kendi kullanıcı adı/şifrelerini iletin — aynı adresten (kurum ağındaysa `http://sunucu-ip:5000`) giriş yapıp kendilerine atanan işlemleri görüp güncelleyebilirler.
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
2. Gerçek bir üretim sunucusu ile çalıştırın (örnek — Linux, gunicorn ile):
   ```
   pip install flask gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```
3. Oturum imzalama anahtarını `SECRET_KEY` ortam değişkeniyle ayarlayın. Docker kurulumunda bu değer `.env` dosyasından okunur.
4. Sunucunun IP adresini şube müdürleriyle paylaşın: `http://<sunucu-ip>:5000`
5. (Önerilir) Kurumun IT/sistem odası ile görüşüp bu adresi kurum içi bir alan adına (örn. `gorevtakip.afad.local`) bağlatabilir ve HTTPS ekletebilirsiniz.

### Alpine Linux Docker ile kurulum

Sunucuda Docker Engine ve Docker Compose eklentisi kurulu olmalıdır. Proje klasöründe aşağıdaki adımları uygulayın:

1. Oturum anahtarı için `.env` dosyası oluşturun. Anahtarı terminalde üretin ve çıktıyı `.env` dosyasına `SECRET_KEY=` sonrasında yazın:
   ```
   openssl rand -hex 32
   ```
   Örnek `.env` biçimi (örnek değeri kullanmayın):
   ```
   SECRET_KEY=buraya_urettiginiz_uzun_rastgele_deger
   ```
2. E-posta bildirimleri kullanılacaksa `.env` dosyasına SMTP ayarlarını ekleyin. Parolayı kaynak koda veya `email_config.py` dosyasına yazmayın:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=465
   SMTP_USE_SSL=true
   SMTP_USER=kurum-hesabi@example.com
   SMTP_PASSWORD=posta-saglayicinizdan-alinan-uygulama-sifresi
   BASE_URL=http://sunucu-ip:5000
   ```
   `.env` dosyası Git tarafından yok sayılır; erişimini ve yedeklerini yine de koruyun.
3. Veritabanı ve yükleme klasörünün mevcut olduğundan emin olun. İlk kurulumda:
   ```
   touch gorev_takip.db
   mkdir -p uploads
   ```
   Konteyner root olmayan `10001` kullanıcısıyla çalışır; bu dosya ve klasörün yazılabilir olması gerekir. Linux sunucuda sahipliğini ayarlayın:
   ```
   sudo chown -R 10001:10001 gorev_takip.db uploads
   ```
4. Oturum anahtarı `.env` dosyasında tanımlıyken uygulamayı oluşturup başlatın:
   ```
   docker compose up -d --build
   ```
5. Tarayıcıdan **http://sunucu-ip:5000** adresini açın. İlk kurulumda giriş bilgileri `admin` / `degistir123` olur; ilk girişten sonra parolayı değiştirin.

Uygulama `python:3.12-alpine` imajında, root olmayan kullanıcıyla çalışır. Veritabanı (`gorev_takip.db`) ve yüklenen dosyalar (`uploads/`) proje klasöründe kalır; konteyner yeniden oluşturulduğunda silinmez. Yedekleme yaparken uygulamayı durdurup bu dosya ve klasörü kopyalayın. `.env` dosyasını ve yedekleri güvenli tutun. Durdurmak için `docker compose down` kullanın.

## Veri nerede saklanıyor?

Tüm veriler `gorev_takip.db` adlı tek bir dosyada (SQLite) tutulur — bu dosyayı düzenli olarak yedeklemeniz yeterlidir.
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

## Sınırlamalar / bir sonraki adımlar

- Şu an ilk admin şifresi kod içinde sabit (`degistir123`) — üretime almadan önce değiştirin.
- Şifre sıfırlama e-postayla değil, sadece admin üzerinden yapılabiliyor (mevcut haliyle basit tutuldu).
- İsterseniz eklenebilecekler: Excel'e dışa aktarma, dosya/ek yükleme (her ikisi de eklendi ✓).
  Bunları istediğinizde birlikte ekleyebiliriz.
"# takip" 
