"""
AFAD Görev Takip Sistemi — Günlük Hatırlatma E-postası

Bu betik, her şube müdürü için:
  - Termini geçmiş (gecikmiş) işlemleri
  - Termine az kalmış (email_config.py'deki DAYS_AHEAD_WARNING gün içindeki) işlemleri
  - Uzun süredir güncellenmemiş (durağan) işlemleri
topluca kontrol eder ve raporlanacak en az bir işlem varsa özet bir e-posta gönderir.

Sistemin kendisi (app.py) yalnızca tarayıcıdan istek geldiğinde çalıştığı için,
bu günlük özeti göndermek için bu betiğin ayrıca ve düzenli olarak
(örn. her sabah 08:00'de) çalıştırılması gerekir.

------------------------------------------------------------------
LINUX (cron) ile otomatik çalıştırma:
    1. Terminalde:  crontab -e
    2. Şu satırı ekleyin (proje klasörünün tam yolunu yazın):
       0 8 * * * cd /tam/yol/gorev-takip && /usr/bin/python3 send_reminders.py >> hatirlatma.log 2>&1

WINDOWS (Görev Zamanlayıcı / Task Scheduler) ile otomatik çalıştırma:
    1. Görev Zamanlayıcı'yı açın -> "Temel Görev Oluştur"
    2. Tetikleyici: Her gün, saat 08:00
    3. Eylem: "Bir program başlat"
       Program/script:      python.exe (tam yolunu "where python" ile bulabilirsiniz)
       Bağımsız değişkenler: send_reminders.py
       Başlangıç dizini:     proje klasörünün tam yolu (gorev-takip klasörü)
------------------------------------------------------------------

Elle test etmek için doğrudan çalıştırabilirsiniz:
    python send_reminders.py
"""
import sqlite3
from datetime import date

import app as core

try:
    import email_config as mail_cfg
except ImportError:
    mail_cfg = None


def build_body(manager, overdue, upcoming, stale):
    lines = [f"Merhaba {manager['full_name']},", "", "Sistemdeki işlemlerinizle ilgili güncel durum özeti:", ""]

    if overdue:
        lines.append(f"GECİKMİŞ İŞLEMLER ({len(overdue)}):")
        for t in overdue:
            lines.append(f"  - {t['title']} (termin: {t['due_date']})")
        lines.append("")

    if upcoming:
        lines.append(f"TERMİNİ YAKLAŞAN İŞLEMLER ({len(upcoming)}):")
        for t in upcoming:
            lines.append(f"  - {t['title']} (termin: {t['due_date']})")
        lines.append("")

    if stale:
        lines.append(f"UZUN SÜREDİR GÜNCELLENMEYEN İŞLEMLER ({len(stale)}):")
        for t in stale:
            days = core.days_since_update(t)
            lines.append(f"  - {t['title']} ({days} gündür güncellenmedi)")
        lines.append("")

    base_url = mail_cfg.BASE_URL if mail_cfg else ""
    lines.append(f"Detaylar ve durum güncelleme için sisteme giriş yapın:\n{base_url}")
    lines.append("")
    lines.append("AFAD Görev Takip Sistemi")
    return "\n".join(lines)


def main():
    if not core.EMAIL_ENABLED:
        print("E-posta ayarları yapılmamış (email_config.py). Hiçbir mail gönderilmedi.")
        return

    core.init_db()  # veritabanı/şema kontrolü (ilk çalıştırmada da güvenli)

    days_ahead = getattr(mail_cfg, "DAYS_AHEAD_WARNING", 2)

    db = sqlite3.connect(core.DB_PATH)
    db.row_factory = sqlite3.Row

    managers = db.execute(
        "SELECT * FROM users WHERE role='manager' AND is_active=1 AND email IS NOT NULL AND email != ''"
    ).fetchall()

    sent = 0
    skipped_no_issue = 0

    for m in managers:
        tasks = db.execute("SELECT * FROM tasks WHERE assigned_to=?", (m["id"],)).fetchall()

        overdue = [t for t in tasks if core.is_overdue(t)]
        stale = [t for t in tasks if core.is_stale(t) and not core.is_overdue(t)]

        upcoming = []
        for t in tasks:
            if t["due_date"] and t["status"] not in ("Tamamlandı", "İptal"):
                try:
                    d = date.fromisoformat(t["due_date"])
                    delta = (d - date.today()).days
                    if 0 <= delta <= days_ahead:
                        upcoming.append(t)
                except ValueError:
                    pass

        if not (overdue or upcoming or stale):
            skipped_no_issue += 1
            continue

        subject = f"[Görev Takip] Günlük özet — {len(overdue) + len(upcoming) + len(stale)} işlem dikkat bekliyor"
        body = build_body(m, overdue, upcoming, stale)
        ok = core.send_email(m["email"], subject, body)
        if ok:
            sent += 1
            print(f"Gönderildi: {m['full_name']} <{m['email']}>")
        else:
            print(f"HATA: {m['full_name']} <{m['email']}> adresine gönderilemedi.")

    db.close()
    print(f"\nToplam {sent} özet e-postası gönderildi. {skipped_no_issue} şube müdürünün bildirilecek işi yoktu.")


if __name__ == "__main__":
    main()
