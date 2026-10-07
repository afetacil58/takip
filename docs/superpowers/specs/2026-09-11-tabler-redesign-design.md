# is_takip: Tabler ile Modernizasyon — Tasarım

**Tarih:** 2026-09-11
**Durum:** Onaylandı (kullanıcı onayı alındı, aynı konuşmada)
**Kaynak repo:** https://github.com/tabler/tabler.git (yerel klon: `C:\AP\tabler`)

## Amaç

AFAD Görev Takip Sistemi'nin (`C:\AP\is_takip`) mevcut, tamamen özel CSS ile
yazılmış arayüzünü Tabler admin dashboard bileşen kütüphanesi kullanarak
daha modern ve görsel olarak tutarlı bir hale getirmek. Backend (Flask
route'ları, veritabanı şeması, iş mantığı) değişmez; kapsam sadece şablonlar
ve statik varlıklardır.

## Kapsam

Tam yeniden tasarım: aşağıdaki 13 şablonun tamamı Tabler bileşenleriyle
yeniden kurulur.

```
templates/
  base.html          (navbar iskeleti)
  login.html
  dashboard.html
  task_form.html
  task_detail.html
  reports.html
  statistics.html
  users.html
  admins.html
  personnel.html
  edit_user.html
  edit_admin.html
  change_password.html
```

## Kapsam dışı

- Flask route/view mantığı, yetkilendirme kuralları, veritabanı şeması
- Dosya ekleri, e-posta hatırlatma sistemi (`send_reminders.py`, `email_config.py`)
- Yeni özellik eklenmesi (sadece görsel/UX modernizasyonu)

## Mevcut durum (referans)

- Şablonlama: Flask/Jinja2, `base.html` üzerinden `{% block content %}`
- Stil: tek elle yazılmış `static/style.css` (framework yok), CSS custom
  property'leri (`--navy`, `--accent`, vb.) ile basit bir marka teması
- Navigasyon: üstte yatay `topbar`, rol bazlı linkler (admin vs şube müdürü)
- Grafikler: `statistics.html` ve `dashboard.html` içinde div tabanlı elle
  yazılmış "stacked bar" / "haftalık çubuk" görselleri, kütüphane yok
- Marka: AFAD logosu (`static/img/afad-logo.png`), turuncu-kırmızı vurgu
  rengi (`--accent: #c8102e`), lacivert (`--navy: #1c3a5e`) birincil renk

## Mimari kararlar

### 1. Build & asset stratejisi

Tabler monorepo'sunun tamamı (docs/preview Astro siteleri, playwright
testleri vb.) projeye dahil edilmez — sadece `@tabler/core` paketi bir
kerelik derlenir:

```
cd C:\AP\tabler
pnpm --filter @tabler/core build
```

Bu, `core/dist/{css,js,img}` altında üretim için hazır, minify edilmiş
dosyalar üretir. Bunlardan ihtiyaç duyulanlar (`tabler.min.css`,
`tabler.min.js`, Tabler Icons font/CSS, ApexCharts JS) elle
`is_takip/static/vendor/tabler/` altına kopyalanır:

```
static/vendor/tabler/
  css/tabler.min.css
  js/tabler.min.js
  js/apexcharts.min.js   (varsa core/dist içinde, yoksa ayrıca vendor edilir)
  icons/                 (Tabler Icons webfont/CSS)
```

Flask çalışma zamanında hiçbir Node/pnpm build adımı çalıştırmaz — bu tamamen
statik, bir defalık bir "vendor" kopyalama işlemidir. Tabler ileride
güncellenmek istenirse aynı adımlar tekrarlanır. İnternet erişimi olmadan
(intranet/kurumsal ortam) çalışabilmesi için CDN kullanılmaz.

### 2. Tema / renk

`<html>` etiketine Tabler'ın hazır `data-bs-theme-primary="orange"`
özniteliği eklenir (Tabler'ın önceden tanımlı turuncu paleti). Ardından
`static/style.css` içinde kalacak küçük bir override bloğu ile
`--tblr-primary` ve ilgili CSS değişkenleri, AFAD'ın mevcut kurumsal
turuncu-kırmızı tonuna (`#c8102e` civarı) sabitlenir. AFAD logosu
(`afad-logo.png`) navbar'da aynı şekilde kullanılmaya devam eder.

### 3. Navigasyon

`base.html`, Tabler'ın yatay (horizontal) navbar düzenine geçirilir:

- Sol: logo rozeti + "Görev Takip Sistemi" başlığı
- Sağ: rol bazlı linkler
  - Admin: Panel, Şube Müdürleri, Yöneticiler, Raporlar, İstatistikler
  - Şube müdürü: Panel, Personelim
- "+ Yeni İşlem" birincil buton (Tabler `btn btn-primary`)
- Kullanıcı adı + dropdown menü: Şifremi Değiştir, Yardım (PDF), Çıkış
- Flash mesajları → Tabler `alert alert-{success|danger|warning}` bileşeni

### 4. Sayfa bazlı dönüşüm eşlemesi

| Mevcut öğe | Tabler karşılığı |
|---|---|
| `.summary-card`, `.overview-chart`, `.report-card` | `card`, `card-body` |
| `.badge`, `.chip`, `.status` | `badge`, `badge-{color}` |
| `.progress-bar` / `.progress-fill` | `progress`, `progress-bar` |
| `.task-table`, `.report-table` | `table table-vcenter card-table` |
| `.filter-bar` (input/select) | `form-control`, `form-select`, `input-group` |
| `form label/input/select/textarea` | `form-label`, `form-control`, `form-select` |
| `.login-box` | Tabler "auth kartı" (`card` + ortalanmış layout) |
| `.checkbox-list` (çoklu sorumlu personel seçimi) | Tabler çoklu seçim / checkbox listesi bileşeni |

### 5. Grafikler (ApexCharts)

`dashboard.html` ve `statistics.html` içindeki div-tabanlı elle çizilmiş
grafikler **ApexCharts** ile değiştirilir:

- Genel/şube durum dağılımı → donut veya yatay stacked bar chart
- Şube karşılaştırma (toplam/tamamlanan/geciken) → gruplu yatay bar chart
- Haftalık eğilim (oluşturulan/tamamlanan) → line veya bar chart

Backend hesaplama mantığı (route'larda zaten hazırlanan sayım/agregasyon
verisi) **değişmez** — Jinja şablonunda bu veriler `tojson` filtresiyle
JSON'a çevrilip sayfa altında küçük bir `<script>` bloğunda ApexCharts'a
verilir. Yeni bir backend endpoint'i veya API gerekmez.

### 6. `style.css`'in geleceği

Dosya tamamen silinmez; AFAD'a özgü olup Tabler'da karşılığı olmayan
küçük özelleştirmeler (tema rengi override'ı, logo rozeti boyutu, print
stilleri `@media print`) için daraltılmış halde tutulur. Tabler'ın
karşıladığı tüm genel bileşen stilleri (`.task-table`, `.badge`, `.chip`,
`.progress-bar`, form stilleri vb.) kaldırılır.

## Uygulama sırası

Riski azaltmak için aşağıdaki sıra izlenir; her adımdan sonra `flask run`
ile tarayıcıda manuel görsel kontrol yapılır:

1. Vendor asset kurulumu (`static/vendor/tabler/...`) + `base.html` iskeleti
   (navbar, tema, flash mesajları)
2. `login.html` (izole, düşük riskli, hızlı doğrulama)
3. `dashboard.html` (en çok kullanılan sayfa; ApexCharts entegrasyonunun ilk
   denemesi)
4. `task_detail.html`, `task_form.html` (çoklu sorumlu personel seçimi dahil)
5. `reports.html`, `statistics.html` (kalan grafikler)
6. `users.html`, `admins.html`, `personnel.html`, `edit_user.html`,
   `edit_admin.html`, `change_password.html`

## Test / doğrulama

Projede otomatik test altyapısı yok; doğrulama tarayıcıda manuel gezinme ile
yapılır:

- Masaüstü ve mobil genişlik (responsive navbar davranışı)
- Rol bazlı navigasyon görünürlüğü (admin vs şube müdürü)
- `reports.html` print görünümü (`@media print` — mevcut "yazdır" akışı
  bozulmamalı)
- Form gönderimleri (yeni işlem, kullanıcı düzenleme, şifre değiştirme,
  dosya ekleme) uçtan uca çalışmalı — sadece stil değişti, davranış aynı
  kalmalı

## Riskler / açık noktalar

- **ApexCharts dosya boyutu**: `core/dist` içinde ayrı paketlenmemişse
  ayrıca vendor edilmesi gerekebilir; uygulama sırasında adım 1'de
  netleştirilecek.
- **Tabler Icons**: font/CSS dosyalarının lisans/boyut açısından uygun
  alt kümesi (yalnızca kullanılan ikonlar) seçilebilir, gerekirse tüm
  ikon seti dahil edilir.
- **Proje git deposu değil**: `C:\AP\is_takip` şu an bir git deposu değil,
  bu yüzden bu spec dosyası commit'lenemedi. İstenirse ayrı bir adımda git
  başlatılabilir.
