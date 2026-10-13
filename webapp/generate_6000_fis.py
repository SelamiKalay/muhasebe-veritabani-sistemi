"""
Muhasebe Veritabanı — 6000 Rastgele Fiş Verisi Üretme (SQLite)
================================================================
Bu script muhasebe.db SQLite dosyasına 6000 adet rastgele fiş ve
her fişe 2-6 satır ekler. Gelir/gider tutarları rastgele ve
gerçekçi (düz olmayan) değerlerdedir.
"""

import sqlite3
import random
from datetime import datetime, timedelta

from database import DATABASE_PATH  # MUHASEBE_DB ile değiştirilebilir


def generate():
    db = sqlite3.connect(DATABASE_PATH)
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    cur = db.cursor()

    # ── Mevcut referans verilerini çek ──
    def get_id(table, col_id, col_filter, value):
        row = cur.execute(f"SELECT {col_id} FROM {table} WHERE {col_filter}=?", (value,)).fetchone()
        return row[0] if row else None

    # Dönemler
    donem_2025 = get_id('MuhasebeDonemleri', 'DonemID', 'DonemAdi', '2025 Mali Yılı')
    donem_2026 = get_id('MuhasebeDonemleri', 'DonemID', 'DonemAdi', '2026 Mali Yılı')

    if not donem_2025 or not donem_2026:
        print("[HATA] Dönem verileri bulunamadı. Önce seed_data.py çalıştırın.")
        db.close()
        return

    # Kullanıcı ID'leri
    kullanici_ids = [row[0] for row in cur.execute("SELECT KullaniciID FROM Kullanicilar WHERE Aktif=1").fetchall()]
    if not kullanici_ids:
        print("[HATA] Aktif kullanıcı bulunamadı.")
        db.close()
        return

    # Hesap ID'leri
    hesap_ids = {}
    for row in cur.execute("SELECT HesapID, HesapKodu FROM HesapPlani").fetchall():
        hesap_ids[row[1]] = row[0]

    tum_hesap_idleri = list(hesap_ids.values())

    # Cari ID'leri
    cari_ids = [row[0] for row in cur.execute("SELECT CariID FROM CariHesaplar").fetchall()]

    # Kategori ID'leri
    gelir_kategori_ids = [row[0] for row in cur.execute(
        "SELECT KategoriID FROM GelirGiderKategorileri WHERE Tur='Gelir'"
    ).fetchall()]
    gider_kategori_ids = [row[0] for row in cur.execute(
        "SELECT KategoriID FROM GelirGiderKategorileri WHERE Tur='Gider'"
    ).fetchall()]

    # ── Sabitler ──
    fis_turleri = ['Mahsup', 'Tahsil', 'Tediye', 'Acilis', 'Kapanis']
    durumlar = ['Aktif'] * 8 + ['Pasif', 'Iptal']  # %80 Aktif, %10 Pasif, %10 İptal

    aciklamalar = [
        'Müşteri tahsilat - banka havalesi',
        'Tedarikçi ödeme - nakit',
        'Kira ödemesi',
        'Personel maaş ödemesi',
        'Ofis malzemesi alımı',
        'Ürün satış geliri',
        'Hizmet bedeli tahsilat',
        'Fatura ödemesi',
        'Kargo ve nakliye ücreti',
        'Bakım ve onarım gideri',
        'Reklam ve pazarlama harcaması',
        'Sigorta primi ödemesi',
        'Vergi ödemesi',
        'Elektrik faturası',
        'Su faturası',
        'Doğalgaz faturası',
        'İnternet ve telefon faturası',
        'Danışmanlık hizmeti',
        'Yazılım lisans ücreti',
        'Araç yakıt gideri',
        'Temizlik hizmeti',
        'Matbaa ve baskı gideri',
        'Eğitim ve seminer ücreti',
        'Depo kirası',
        'Hammadde alımı',
        'Stok devir işlemi',
        'Avans ödemesi',
        'Cari hesap mahsuplaşma',
        'Döviz alım işlemi',
        'Döviz satım işlemi',
    ]

    satir_aciklamalari = [
        'Banka hesabına giriş',
        'Kasadan çıkış',
        'Alıcılar hesabından düşüş',
        'Satıcılara ödeme kaydı',
        'Gelir kaydı',
        'Gider tahakkuku',
        'Havale ile ödeme',
        'Nakit tahsilat',
        'Çek ile tahsilat',
        'Senet ile ödeme',
        'Mahsup kaydı',
        'Devir bakiye kaydı',
        'KDV hesaplama',
        'Stopaj kesintisi',
        'Kur farkı kaydı',
        'Vade farkı kaydı',
        'Kasa sayım farkı',
        'Banka masrafı',
        'Kredi kartı tahsilat',
        'POS cihazı tahsilat',
    ]

    # ── Mevcut en yüksek fiş numarasının sıra değerini bul ──
    mevcut_max = cur.execute(
        "SELECT FisNo FROM MuhasebeFisleri ORDER BY FisID DESC LIMIT 1"
    ).fetchone()
    fis_sayaci = 5  # varsayılan
    if mevcut_max:
        try:
            son_no = mevcut_max[0]  # ör: FIS-2026-000004
            fis_sayaci = int(son_no.split('-')[-1]) + 1
        except:
            fis_sayaci = 5

    # ── Tarih aralığı: 2025-01-01 — 2026-03-24 (449 gün) ──
    baslangic = datetime(2025, 1, 1)
    toplam_gun = 449

    print(">> 6000 adet fiş oluşturma başlatılıyor...")
    print(f"   Veritabanı: {DATABASE_PATH}")

    toplam_fis = 6000
    fis_batch = []   # MuhasebeFisleri batch
    satir_batch = []  # FisSatirlari batch

    for i in range(toplam_fis):
        # ── Fiş başlık verileri ──
        fis_turu = random.choice(fis_turleri)

        # Rastgele tarih
        gun_farki = random.randint(0, toplam_gun - 1)
        fis_tarihi = baslangic + timedelta(days=gun_farki)
        fis_tarihi_str = fis_tarihi.strftime('%Y-%m-%d')

        # Dönem (tarihe göre)
        donem_id = donem_2025 if fis_tarihi.year == 2025 else donem_2026

        # Kullanıcı
        kullanici_id = random.choice(kullanici_ids)

        # Fiş numarası
        fis_no = f"FIS-{fis_tarihi.year}-{fis_sayaci:06d}"

        # Açıklama
        aciklama = random.choice(aciklamalar)

        # Durum
        durum = random.choice(durumlar)

        # Oluşturma tarihi (fiş tarihinden 0-3 gün, 0-23 saat, 0-59 dk sonra)
        olusturma_tarihi = fis_tarihi + timedelta(
            hours=random.randint(0, 72),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59)
        )
        olusturma_str = olusturma_tarihi.strftime('%Y-%m-%d %H:%M:%S')

        # Güncelleme tarihi (%30 ihtimalle)
        guncelleme_str = None
        if random.random() < 0.30:
            guncelleme = olusturma_tarihi + timedelta(days=random.randint(1, 15))
            guncelleme_str = guncelleme.strftime('%Y-%m-%d %H:%M:%S')

        fis_batch.append((
            fis_no, fis_tarihi_str, fis_turu, aciklama,
            donem_id, kullanici_id, durum, olusturma_str, guncelleme_str
        ))

        # ── Fiş satırları (2-6 satır, çiftler halinde borç=alacak) ──
        cift_sayisi = random.randint(1, 3)  # 1-3 çift = 2-6 satır

        for _ in range(cift_sayisi):
            # Rastgele tutar (düz sayı olmasın)
            tutar_tipi = random.random()
            if tutar_tipi < 0.15:
                # Küçük tutar: 73.50 - 999.99
                ana_tutar = round(random.uniform(73.50, 999.99), 2)
            elif tutar_tipi < 0.40:
                # Orta küçük: 1000 - 9999
                ana_tutar = round(random.uniform(1000.00, 9999.99), 2)
            elif tutar_tipi < 0.70:
                # Orta: 10000 - 49999
                ana_tutar = round(random.uniform(10000.00, 49999.99), 2)
            elif tutar_tipi < 0.90:
                # Büyük: 50000 - 149999
                ana_tutar = round(random.uniform(50000.00, 149999.99), 2)
            else:
                # Çok büyük: 150000 - 500000
                ana_tutar = round(random.uniform(150000.00, 500000.00), 2)

            # Kuruşlu tutar olsun (%80)
            if random.random() < 0.80:
                kurus = random.randint(1, 99) / 100.0
                ana_tutar = round(int(ana_tutar) + kurus, 2)

            # Hesap seçimi (borç ve alacak farklı)
            borc_hesap = random.choice(tum_hesap_idleri)
            alacak_hesap = random.choice(tum_hesap_idleri)
            while alacak_hesap == borc_hesap:
                alacak_hesap = random.choice(tum_hesap_idleri)

            # Cari (%70 bağlı, %30 NULL)
            cari_id = random.choice(cari_ids) if random.random() < 0.70 else None
            alacak_cari = cari_id
            if cari_id and random.random() < 0.30:
                alacak_cari = random.choice(cari_ids)

            # Kategori (fiş türüne göre)
            kategori_id = None
            if fis_turu in ('Tahsil', 'Acilis') and gelir_kategori_ids:
                kategori_id = random.choice(gelir_kategori_ids)
            elif fis_turu in ('Tediye', 'Kapanis') and gider_kategori_ids:
                kategori_id = random.choice(gider_kategori_ids)
            elif fis_turu == 'Mahsup':
                if random.random() < 0.5 and gelir_kategori_ids:
                    kategori_id = random.choice(gelir_kategori_ids)
                elif gider_kategori_ids:
                    kategori_id = random.choice(gider_kategori_ids)

            # Para birimi (%85 TRY, %10 USD, %5 EUR)
            para_birimi = 'TRY'
            kur_degeri = 1.0
            para_rand = random.random()
            if para_rand > 0.95:
                para_birimi = 'EUR'
                kur_degeri = round(random.uniform(38.20, 40.50), 4)
            elif para_rand > 0.85:
                para_birimi = 'USD'
                kur_degeri = round(random.uniform(35.50, 37.80), 4)

            # BORÇ satırı (placeholder FisID = i ile, sonra güncellenecek)
            satir_batch.append((
                i,  # geçici sıra (sonra FisID ile eşleştirilecek)
                borc_hesap, cari_id, kategori_id,
                ana_tutar, 0.00,
                random.choice(satir_aciklamalari),
                para_birimi, kur_degeri
            ))

            # ALACAK satırı
            satir_batch.append((
                i,  # geçici sıra
                alacak_hesap, alacak_cari, kategori_id,
                0.00, ana_tutar,
                random.choice(satir_aciklamalari),
                para_birimi, kur_degeri
            ))

        fis_sayaci += 1

        if (i + 1) % 1000 == 0:
            print(f"   {i + 1} fiş hazırlandı...")

    # ── Toplu ekleme ──
    print(">> Fişler veritabanına yazılıyor...")

    # 1) Fişleri ekle ve ID'lerini al
    fis_id_map = {}  # sıra -> gerçek FisID
    for idx, fis in enumerate(fis_batch):
        cur.execute("""
            INSERT INTO MuhasebeFisleri 
            (FisNo, FisTarihi, FisTuru, Aciklama, DonemID, KullaniciID, Durum, OlusturmaTarihi, GuncellemeTarihi)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, fis)
        fis_id_map[idx] = cur.lastrowid

        if (idx + 1) % 1000 == 0:
            print(f"   {idx + 1} fiş eklendi...")

    # 2) Satırları ekle (geçici sıra numarasını gerçek FisID ile değiştir)
    print(">> Fiş satırları ekleniyor...")
    satir_sayaci = 0
    for satir in satir_batch:
        gecici_idx, hesap_id, cari_id, kategori_id, borc, alacak, aciklama, para, kur = satir
        gercek_fis_id = fis_id_map[gecici_idx]

        cur.execute("""
            INSERT INTO FisSatirlari 
            (FisID, HesapID, CariID, KategoriID, BorcTutari, AlacakTutari, Aciklama, ParaBirimi, KurDegeri)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (gercek_fis_id, hesap_id, cari_id, kategori_id, borc, alacak, aciklama, para, kur))

        satir_sayaci += 1
        if satir_sayaci % 5000 == 0:
            print(f"   {satir_sayaci} satır eklendi...")

    db.commit()

    # ── Özet ──
    toplam_fis_db = cur.execute("SELECT COUNT(*) FROM MuhasebeFisleri").fetchone()[0]
    toplam_satir_db = cur.execute("SELECT COUNT(*) FROM FisSatirlari").fetchone()[0]
    toplam_borc = cur.execute("SELECT SUM(BorcTutari) FROM FisSatirlari").fetchone()[0]
    toplam_alacak = cur.execute("SELECT SUM(AlacakTutari) FROM FisSatirlari").fetchone()[0]

    print()
    print("=" * 60)
    print(">> İşlem tamamlandı!")
    print("=" * 60)
    print(f"   Toplam fiş sayısı    : {toplam_fis_db}")
    print(f"   Toplam satır sayısı  : {toplam_satir_db}")
    print(f"   Toplam borç tutarı   : {toplam_borc:,.2f} TL")
    print(f"   Toplam alacak tutarı : {toplam_alacak:,.2f} TL")

    # Fiş türlerine göre dağılım
    print("\n   Fiş Türlerine Göre Dağılım:")
    for row in cur.execute("SELECT FisTuru, COUNT(*) FROM MuhasebeFisleri GROUP BY FisTuru ORDER BY COUNT(*) DESC"):
        print(f"     {row[0]:10s} : {row[1]}")

    # Durum dağılımı
    print("\n   Durum Dağılımı:")
    for row in cur.execute("SELECT Durum, COUNT(*) FROM MuhasebeFisleri GROUP BY Durum ORDER BY COUNT(*) DESC"):
        print(f"     {row[0]:10s} : {row[1]}")

    db.close()
    print("\n>> Veritabanı kapatıldı. Uygulamayı yeniden başlatarak verileri görebilirsiniz.")


if __name__ == '__main__':
    generate()
