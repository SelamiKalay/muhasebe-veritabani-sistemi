"""
Muhasebe Veritabanı — Örnek Veri Yükleme Scripti
==================================================
02_DML_Insert_Data.sql dosyasının Python/SQLite karşılığıdır.
Parametrik sorgular (?) ile SQL Injection'a karşı güvenlidir.
"""

import os
import secrets
import sqlite3

from werkzeug.security import generate_password_hash

from database import DATABASE_PATH

# Konsolsuz başlatmada (baslat_sessiz.vbs) da bulunabilsin diye ilk şifre
# veritabanının yanına yazılır (varsayılan: webapp/ILK_GIRIS.txt)
ILK_GIRIS_DOSYASI = os.path.join(os.path.dirname(DATABASE_PATH), 'ILK_GIRIS.txt')


def ilk_admin_sifresi():
    """Ortam değişkeni verilmişse onu, yoksa rastgele bir şifre döndürür."""
    return os.environ.get('MUHASEBE_ADMIN_SIFRE') or secrets.token_urlsafe(9)


def seed():
    """Tüm örnek verileri veritabanına yükler."""
    db = sqlite3.connect(DATABASE_PATH)
    db.execute("PRAGMA foreign_keys=ON")
    cur = db.cursor()

    # Zaten veri var mı kontrol et
    count = cur.execute("SELECT COUNT(*) FROM Kullanicilar").fetchone()[0]
    if count > 0:
        print("[!] Veriler zaten mevcut, seed atlaniyor.")
        db.close()
        return

    # ── 1. Kullanicilar ──
    # Herkesçe bilinen sabit bir şifre (admin/admin) yerine ilk çalıştırmada
    # rastgele şifre üretilir; giriş yaptıktan sonra değiştirilmelidir.
    admin_sifre = ilk_admin_sifresi()
    cur.executemany("""
        INSERT INTO Kullanicilar (KullaniciAdi, SifreHash, AdSoyad, Rol) VALUES (?,?,?,?)
    """, [
        ('admin', generate_password_hash(admin_sifre), 'Sistem Yöneticisi', 'Yonetici'),
    ])

    # ── 2. MuhasebeDonemleri ──
    cur.executemany("""
        INSERT INTO MuhasebeDonemleri (DonemAdi, BaslangicTarihi, BitisTarihi, Durum) VALUES (?,?,?,?)
    """, [
        ('2025 Mali Yılı', '2025-01-01', '2025-12-31', 'Kapali'),
        ('2026 Mali Yılı', '2026-01-01', '2026-12-31', 'Acik'),
    ])

    # ── 3. HesapPlani — Ana hesaplar ──
    ana_hesaplar = [
        ('100',  'Kasa',                      'Aktif',  None),
        ('102',  'Bankalar',                  'Aktif',  None),
        ('120',  'Alıcılar',                  'Aktif',  None),
        ('320',  'Satıcılar',                 'Pasif',  None),
        ('600',  'Yurtiçi Satışlar',          'Gelir',  None),
        ('770',  'Genel Yönetim Giderleri',   'Gider',  None),
    ]
    cur.executemany("""
        INSERT INTO HesapPlani (HesapKodu, HesapAdi, HesapTuru, UstHesapID) VALUES (?,?,?,?)
    """, ana_hesaplar)

    # Alt hesaplar — önce ana hesap ID'lerini al
    def get_hesap_id(kod):
        return cur.execute("SELECT HesapID FROM HesapPlani WHERE HesapKodu=?", (kod,)).fetchone()[0]

    alt_hesaplar = [
        ('100.01', 'Merkez Kasa',        'Aktif',  get_hesap_id('100')),
        ('100.02', 'Döviz Kasası',       'Aktif',  get_hesap_id('100')),
        ('102.01', 'Ziraat Bankası',     'Aktif',  get_hesap_id('102')),
        ('102.02', 'İş Bankası',         'Aktif',  get_hesap_id('102')),
        ('600.01', 'Ürün Satışları',     'Gelir',  get_hesap_id('600')),
        ('770.01', 'Kira Giderleri',     'Gider',  get_hesap_id('770')),
    ]
    cur.executemany("""
        INSERT INTO HesapPlani (HesapKodu, HesapAdi, HesapTuru, UstHesapID) VALUES (?,?,?,?)
    """, alt_hesaplar)

    # ── 4. CariHesaplar ──
    cur.executemany("""
        INSERT INTO CariHesaplar (CariKodu, CariAdi, CariTuru, VergiNo, Telefon, Adres) VALUES (?,?,?,?,?,?)
    """, [
        ('C001', 'ABC Ticaret Ltd. Şti.',  'Musteri',    '1234567890', '0212-555-0001', 'İstanbul, Kadıköy'),
        ('C002', 'XYZ Bilişim A.Ş.',       'Musteri',    '9876543210', '0216-555-0002', 'İstanbul, Üsküdar'),
        ('C003', 'DEF Tedarik Ltd.',        'Tedarikci',  '1122334455', '0312-555-0003', 'Ankara, Çankaya'),
        ('C004', 'GHI Lojistik',           'Tedarikci',  '5566778899', '0232-555-0004', 'İzmir, Konak'),
        ('C005', 'Ali Veli',               'Personel',   None,          '0533-555-0005', 'İstanbul, Beşiktaş'),
    ])

    # ── 5. GelirGiderKategorileri ──
    cur.executemany("""
        INSERT INTO GelirGiderKategorileri (KategoriAdi, Tur) VALUES (?,?)
    """, [
        ('Ürün Satışı',     'Gelir'),
        ('Hizmet Geliri',   'Gelir'),
        ('Faiz Geliri',     'Gelir'),
        ('Kira Gideri',     'Gider'),
        ('Personel Gideri', 'Gider'),
        ('Ofis Malzemesi',  'Gider'),
    ])

    db.commit()
    db.close()
    print("[OK] Temel ayarlar ve Admin kullanıcısı başarıyla yüklendi.")

    with open(ILK_GIRIS_DOSYASI, 'w', encoding='utf-8') as f:
        f.write('Muhasebe Sistemi - ilk giris bilgileri\n'
                f'Kullanici adi: admin\nSifre: {admin_sifre}\n\n'
                'Giris yaptiktan sonra sifreyi degistirin ve bu dosyayi silin.\n')
    print(f"[i] Yönetici hesabı: admin / {admin_sifre}")
    print(f"    (Bu şifre {ILK_GIRIS_DOSYASI} dosyasına da yazıldı; "
          "giriş yaptıktan sonra şifreyi değiştirip dosyayı silin.)")


if __name__ == '__main__':
    seed()
