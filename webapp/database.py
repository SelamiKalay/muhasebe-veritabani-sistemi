"""
Muhasebe Veritabanı Bağlantı Modülü
====================================
SQLite bağlantısı, tablo oluşturma ve parametrik sorgu yardımcıları.
Tüm sorgular SQL Injection'a karşı parametrik (?) yer tutucularla çalışır.
"""

import sqlite3
import os
from flask import g

# Veritabanı dosyasının yolu: varsayılan webapp/muhasebe.db; MUHASEBE_DB ile
# değiştirilebilir (testler geçici bir veritabanı kullanır)
DATABASE_PATH = os.environ.get('MUHASEBE_DB') or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'muhasebe.db')


def get_db():
    """
    Flask request bağlamında SQLite bağlantısı döndürür.
    Her request için tek bir bağlantı kullanılır (g objesi ile).
    """
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.row_factory = sqlite3.Row          # Sütun adıyla erişim
        g.db.execute("PRAGMA journal_mode=WAL")  # Performans
        g.db.execute("PRAGMA foreign_keys=ON")   # FK kısıtlamalarını etkinleştir
    return g.db


def close_db(e=None):
    """Request sonunda bağlantıyı kapat."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_app(app):
    """Flask uygulamasına veritabanı hook'larını kaydet."""
    app.teardown_appcontext(close_db)


def query_db(query, args=(), one=False):
    """
    Parametrik SELECT sorgusu çalıştır.
    SQL Injection koruması: Tüm değerler '?' ile bağlanır.

    Parametreler:
        query (str): SQL sorgusu (ör: "SELECT * FROM X WHERE id = ?")
        args (tuple): Parametreler
        one (bool): True ise tek satır döner

    Dönüş:
        list[sqlite3.Row] veya sqlite3.Row veya None
    """
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    """
    Parametrik INSERT/UPDATE/DELETE sorgusu çalıştır ve commit et.
    SQL Injection koruması: Tüm değerler '?' ile bağlanır.

    Dönüş:
        lastrowid (int): Eklenen satırın ID'si
    """
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    return cur.lastrowid


def init_db():
    """
    Tüm tabloları oluşturur (yoksa). Mevcut DDL şemasının
    SQLite uyumlu halidir.
    """
    db = sqlite3.connect(DATABASE_PATH)
    db.execute("PRAGMA foreign_keys=ON")

    # ── Kullanicilar ──
    db.execute("""
        CREATE TABLE IF NOT EXISTS Kullanicilar (
            KullaniciID     INTEGER PRIMARY KEY AUTOINCREMENT,
            KullaniciAdi    TEXT    NOT NULL UNIQUE,
            SifreHash       TEXT    NOT NULL,
            AdSoyad         TEXT    NOT NULL,
            Rol             TEXT    NOT NULL CHECK (Rol IN ('Muhasebeci','Yonetici','SaltOkunur')),
            Aktif           INTEGER NOT NULL DEFAULT 1,
            KayitTarihi     TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)

    # ── MuhasebeDonemleri ──
    db.execute("""
        CREATE TABLE IF NOT EXISTS MuhasebeDonemleri (
            DonemID         INTEGER PRIMARY KEY AUTOINCREMENT,
            DonemAdi        TEXT    NOT NULL UNIQUE,
            BaslangicTarihi TEXT    NOT NULL,
            BitisTarihi     TEXT    NOT NULL,
            Durum           TEXT    NOT NULL DEFAULT 'Acik' CHECK (Durum IN ('Acik','Kapali')),
            CHECK (BitisTarihi > BaslangicTarihi)
        )
    """)

    # ── HesapPlani (self-referencing) ──
    db.execute("""
        CREATE TABLE IF NOT EXISTS HesapPlani (
            HesapID     INTEGER PRIMARY KEY AUTOINCREMENT,
            HesapKodu   TEXT    NOT NULL UNIQUE,
            HesapAdi    TEXT    NOT NULL,
            HesapTuru   TEXT    NOT NULL CHECK (HesapTuru IN ('Aktif','Pasif','Gelir','Gider','Ozkaynaklar')),
            UstHesapID  INTEGER NULL REFERENCES HesapPlani(HesapID),
            Aktif       INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ── CariHesaplar ──
    db.execute("""
        CREATE TABLE IF NOT EXISTS CariHesaplar (
            CariID   INTEGER PRIMARY KEY AUTOINCREMENT,
            CariKodu TEXT    NOT NULL UNIQUE,
            CariAdi  TEXT    NOT NULL,
            CariTuru TEXT    NOT NULL CHECK (CariTuru IN ('Musteri','Tedarikci','Personel','Diger')),
            VergiNo  TEXT    NULL,
            Telefon  TEXT    NULL,
            Adres    TEXT    NULL,
            Aktif    INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ── GelirGiderKategorileri ──
    db.execute("""
        CREATE TABLE IF NOT EXISTS GelirGiderKategorileri (
            KategoriID  INTEGER PRIMARY KEY AUTOINCREMENT,
            KategoriAdi TEXT    NOT NULL,
            Tur         TEXT    NOT NULL CHECK (Tur IN ('Gelir','Gider')),
            UNIQUE(KategoriAdi, Tur)
        )
    """)

    # ── MuhasebeFisleri ──
    db.execute("""
        CREATE TABLE IF NOT EXISTS MuhasebeFisleri (
            FisID            INTEGER PRIMARY KEY AUTOINCREMENT,
            FisNo            TEXT    NOT NULL UNIQUE,
            FisTarihi        TEXT    NOT NULL,
            FisTuru          TEXT    NOT NULL CHECK (FisTuru IN ('Mahsup','Tahsil','Tediye','Acilis','Kapanis')),
            Aciklama         TEXT    NULL,
            DonemID          INTEGER NOT NULL REFERENCES MuhasebeDonemleri(DonemID),
            KullaniciID      INTEGER NOT NULL REFERENCES Kullanicilar(KullaniciID),
            Durum            TEXT    NOT NULL DEFAULT 'Aktif' CHECK (Durum IN ('Aktif','Pasif','Iptal')),
            OlusturmaTarihi  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            GuncellemeTarihi TEXT    NULL
        )
    """)

    # ── FisSatirlari ──
    db.execute("""
        CREATE TABLE IF NOT EXISTS FisSatirlari (
            SatirID      INTEGER PRIMARY KEY AUTOINCREMENT,
            FisID        INTEGER NOT NULL REFERENCES MuhasebeFisleri(FisID),
            HesapID      INTEGER NOT NULL REFERENCES HesapPlani(HesapID),
            CariID       INTEGER NULL     REFERENCES CariHesaplar(CariID),
            KategoriID   INTEGER NULL     REFERENCES GelirGiderKategorileri(KategoriID),
            BorcTutari   REAL    NOT NULL DEFAULT 0.00 CHECK (BorcTutari >= 0),
            AlacakTutari REAL    NOT NULL DEFAULT 0.00 CHECK (AlacakTutari >= 0),
            Aciklama     TEXT    NULL,
            ParaBirimi   TEXT    NOT NULL DEFAULT 'TRY',
            KurDegeri    REAL    NOT NULL DEFAULT 1.0,
            CHECK (NOT (BorcTutari > 0 AND AlacakTutari > 0))
        )
    """)

    # ── FisLog (audit trail) ──
    db.execute("""
        CREATE TABLE IF NOT EXISTS FisLog (
            LogID        INTEGER PRIMARY KEY AUTOINCREMENT,
            FisID        INTEGER NOT NULL,
            Islem        TEXT    NOT NULL CHECK (Islem IN ('INSERT','UPDATE','DELETE')),
            EskiDegerler TEXT    NULL,
            YeniDegerler TEXT    NULL,
            IslemTarihi  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            KullaniciID  INTEGER NULL
        )
    """)

    # ── İndeksler ──
    db.execute("CREATE INDEX IF NOT EXISTS IX_Fis_Tarih    ON MuhasebeFisleri(FisTarihi)")
    db.execute("CREATE INDEX IF NOT EXISTS IX_Satir_Hesap  ON FisSatirlari(HesapID)")
    db.execute("CREATE INDEX IF NOT EXISTS IX_Satir_Cari   ON FisSatirlari(CariID)")
    db.execute("CREATE INDEX IF NOT EXISTS IX_Satir_Fis    ON FisSatirlari(FisID)")
    db.execute("CREATE INDEX IF NOT EXISTS IX_Log_Fis      ON FisLog(FisID)")

    db.commit()
    db.close()
    print("[OK] Veritabani tablolari olusturuldu:", DATABASE_PATH)


if __name__ == '__main__':
    init_db()
    print("[OK] Veritabani baslatma tamamlandi.")
