-- ============================================================
-- Muhasebe Fiş, Gelir-Gider ve Defter Sistemi
-- DML Script — Örnek Veri Ekleme
-- RDBMS: SQL Server (T-SQL)
-- ============================================================

USE MuhasebeDB;
GO

-- ============================================================
-- 1. Kullanicilar — 3 farklı rolde kullanıcı
--    NOT: Hash değerleri yalnızca örnek veridir (tuzsuz SHA1/MD5, zayıf şifreler).
--    Gerçek kullanımda tuzlu ve yavaş bir algoritma (bcrypt/scrypt/PBKDF2) kullanın;
--    web uygulaması (webapp/) bu nedenle werkzeug scrypt hash'i kullanır.
-- ============================================================
INSERT INTO Kullanicilar (KullaniciAdi, SifreHash, AdSoyad, Rol) VALUES
('admin',       'a94a8fe5ccb19ba61c4c0873d391e987982fbbd3',  N'Ahmet Yılmaz',      'Yonetici'),
('muhasebeci1', 'e10adc3949ba59abbe56e057f20f883e',          N'Fatma Kaya',         'Muhasebeci'),
('okuyucu1',    'd8578edf8458ce06fbc5bb76a58c5ca4',          N'Mehmet Demir',       'SaltOkunur');
GO

-- ============================================================
-- 2. MuhasebeDonemleri — 2025 ve 2026 dönemleri
-- ============================================================
INSERT INTO MuhasebeDonemleri (DonemAdi, BaslangicTarihi, BitisTarihi, Durum) VALUES
(N'2025 Mali Yılı',    '2025-01-01', '2025-12-31', 'Kapali'),
(N'2026 Mali Yılı',    '2026-01-01', '2026-12-31', 'Acik');
GO

-- ============================================================
-- 3. HesapPlani — Ana hesaplar ve alt hesaplar
-- ============================================================

-- Ana hesaplar (UstHesapID = NULL)
INSERT INTO HesapPlani (HesapKodu, HesapAdi, HesapTuru, UstHesapID) VALUES
('100',  N'Kasa',                    'Aktif',    NULL),
('102',  N'Bankalar',                'Aktif',    NULL),
('120',  N'Alıcılar',               'Aktif',    NULL),
('320',  N'Satıcılar',              'Pasif',    NULL),
('600',  N'Yurtiçi Satışlar',       'Gelir',    NULL),
('770',  N'Genel Yönetim Giderleri','Gider',    NULL);
GO

-- Alt hesaplar (UstHesapID ile bağlı)
INSERT INTO HesapPlani (HesapKodu, HesapAdi, HesapTuru, UstHesapID) VALUES
('100.01', N'Merkez Kasa',               'Aktif',  (SELECT HesapID FROM HesapPlani WHERE HesapKodu = '100')),
('100.02', N'Döviz Kasası',              'Aktif',  (SELECT HesapID FROM HesapPlani WHERE HesapKodu = '100')),
('102.01', N'Ziraat Bankası',            'Aktif',  (SELECT HesapID FROM HesapPlani WHERE HesapKodu = '102')),
('102.02', N'İş Bankası',               'Aktif',  (SELECT HesapID FROM HesapPlani WHERE HesapKodu = '102')),
('600.01', N'Ürün Satışları',            'Gelir',  (SELECT HesapID FROM HesapPlani WHERE HesapKodu = '600')),
('770.01', N'Kira Giderleri',            'Gider',  (SELECT HesapID FROM HesapPlani WHERE HesapKodu = '770'));
GO

-- ============================================================
-- 4. CariHesaplar — 5 farklı cari
-- ============================================================
INSERT INTO CariHesaplar (CariKodu, CariAdi, CariTuru, VergiNo, Telefon, Adres) VALUES
('C001', N'ABC Ticaret Ltd. Şti.',   'Musteri',    '1234567890', '0212-555-0001', N'İstanbul, Kadıköy'),
('C002', N'XYZ Bilişim A.Ş.',        'Musteri',    '9876543210', '0216-555-0002', N'İstanbul, Üsküdar'),
('C003', N'DEF Tedarik Ltd.',         'Tedarikci',  '1122334455', '0312-555-0003', N'Ankara, Çankaya'),
('C004', N'GHI Lojistik',            'Tedarikci',  '5566778899', '0232-555-0004', N'İzmir, Konak'),
('C005', N'Ali Veli',                'Personel',   NULL,          '0533-555-0005', N'İstanbul, Beşiktaş');
GO

-- ============================================================
-- 5. GelirGiderKategorileri — 6 kategori
-- ============================================================
INSERT INTO GelirGiderKategorileri (KategoriAdi, Tur) VALUES
(N'Ürün Satışı',         'Gelir'),
(N'Hizmet Geliri',       'Gelir'),
(N'Faiz Geliri',         'Gelir'),
(N'Kira Gideri',         'Gider'),
(N'Personel Gideri',     'Gider'),
(N'Ofis Malzemesi',      'Gider');
GO

-- ============================================================
-- 6. MuhasebeFisleri ve FisSatirlari — 4 fiş ve satırlar
-- ============================================================

-- ---- FİŞ 1: Tahsilat Fişi ----
-- ABC Ticaret'ten 50.000 TL tahsilat (banka havalesi)
INSERT INTO MuhasebeFisleri (FisNo, FisTarihi, FisTuru, Aciklama, DonemID, KullaniciID)
VALUES ('FIS-2026-0001', '2026-01-15', 'Tahsil', N'ABC Ticaret tahsilat - banka havalesi',
        (SELECT DonemID FROM MuhasebeDonemleri WHERE DonemAdi = N'2026 Mali Yılı'),
        (SELECT KullaniciID FROM Kullanicilar WHERE KullaniciAdi = 'muhasebeci1'));
GO

-- Fiş 1 Satırları: Borç = Alacak = 50.000
INSERT INTO FisSatirlari (FisID, HesapID, CariID, KategoriID, BorcTutari, AlacakTutari, Aciklama) VALUES
(
    (SELECT FisID FROM MuhasebeFisleri WHERE FisNo = 'FIS-2026-0001'),
    (SELECT HesapID FROM HesapPlani WHERE HesapKodu = '102.01'),    -- Ziraat Bankası BORÇ
    (SELECT CariID FROM CariHesaplar WHERE CariKodu = 'C001'),       -- ABC Ticaret
    NULL,
    50000.00, 0.00, N'Banka hesabına giriş'
),
(
    (SELECT FisID FROM MuhasebeFisleri WHERE FisNo = 'FIS-2026-0001'),
    (SELECT HesapID FROM HesapPlani WHERE HesapKodu = '120'),       -- Alıcılar ALACAK
    (SELECT CariID FROM CariHesaplar WHERE CariKodu = 'C001'),       -- ABC Ticaret
    (SELECT KategoriID FROM GelirGiderKategorileri WHERE KategoriAdi = N'Ürün Satışı'),
    0.00, 50000.00, N'Alıcılar hesabından düşüş'
);
GO

-- ---- FİŞ 2: Tediye (Ödeme) Fişi ----
-- DEF Tedarik'e 30.000 TL ödeme (kasadan)
INSERT INTO MuhasebeFisleri (FisNo, FisTarihi, FisTuru, Aciklama, DonemID, KullaniciID)
VALUES ('FIS-2026-0002', '2026-01-20', 'Tediye', N'DEF Tedarik ödeme - nakit',
        (SELECT DonemID FROM MuhasebeDonemleri WHERE DonemAdi = N'2026 Mali Yılı'),
        (SELECT KullaniciID FROM Kullanicilar WHERE KullaniciAdi = 'muhasebeci1'));
GO

INSERT INTO FisSatirlari (FisID, HesapID, CariID, KategoriID, BorcTutari, AlacakTutari, Aciklama) VALUES
(
    (SELECT FisID FROM MuhasebeFisleri WHERE FisNo = 'FIS-2026-0002'),
    (SELECT HesapID FROM HesapPlani WHERE HesapKodu = '320'),       -- Satıcılar BORÇ
    (SELECT CariID FROM CariHesaplar WHERE CariKodu = 'C003'),       -- DEF Tedarik
    NULL,
    30000.00, 0.00, N'Satıcılara ödeme'
),
(
    (SELECT FisID FROM MuhasebeFisleri WHERE FisNo = 'FIS-2026-0002'),
    (SELECT HesapID FROM HesapPlani WHERE HesapKodu = '100.01'),    -- Merkez Kasa ALACAK
    (SELECT CariID FROM CariHesaplar WHERE CariKodu = 'C003'),       -- DEF Tedarik
    (SELECT KategoriID FROM GelirGiderKategorileri WHERE KategoriAdi = N'Ofis Malzemesi'),
    0.00, 30000.00, N'Kasadan çıkış'
);
GO

-- ---- FİŞ 3: Mahsup Fişi ----
-- Kira gideri kaydı: 8.500 TL
INSERT INTO MuhasebeFisleri (FisNo, FisTarihi, FisTuru, Aciklama, DonemID, KullaniciID)
VALUES ('FIS-2026-0003', '2026-02-01', 'Mahsup', N'Şubat ayı kira gideri',
        (SELECT DonemID FROM MuhasebeDonemleri WHERE DonemAdi = N'2026 Mali Yılı'),
        (SELECT KullaniciID FROM Kullanicilar WHERE KullaniciAdi = 'muhasebeci1'));
GO

INSERT INTO FisSatirlari (FisID, HesapID, CariID, KategoriID, BorcTutari, AlacakTutari, Aciklama) VALUES
(
    (SELECT FisID FROM MuhasebeFisleri WHERE FisNo = 'FIS-2026-0003'),
    (SELECT HesapID FROM HesapPlani WHERE HesapKodu = '770.01'),    -- Kira Giderleri BORÇ
    NULL,
    (SELECT KategoriID FROM GelirGiderKategorileri WHERE KategoriAdi = N'Kira Gideri'),
    8500.00, 0.00, N'Kira gideri tahakkuku'
),
(
    (SELECT FisID FROM MuhasebeFisleri WHERE FisNo = 'FIS-2026-0003'),
    (SELECT HesapID FROM HesapPlani WHERE HesapKodu = '102.02'),    -- İş Bankası ALACAK
    NULL,
    NULL,
    0.00, 8500.00, N'Banka hesabından ödeme'
);
GO

-- ---- FİŞ 4: Tahsilat Fişi (Farklı Para Birimi) ----
-- XYZ Bilişim'den 5.000 USD tahsilat (kur: 36.50)
INSERT INTO MuhasebeFisleri (FisNo, FisTarihi, FisTuru, Aciklama, DonemID, KullaniciID)
VALUES ('FIS-2026-0004', '2026-02-15', 'Tahsil', N'XYZ Bilişim USD tahsilat',
        (SELECT DonemID FROM MuhasebeDonemleri WHERE DonemAdi = N'2026 Mali Yılı'),
        (SELECT KullaniciID FROM Kullanicilar WHERE KullaniciAdi = 'admin'));
GO

INSERT INTO FisSatirlari (FisID, HesapID, CariID, KategoriID, BorcTutari, AlacakTutari, Aciklama, ParaBirimi, KurDegeri) VALUES
(
    (SELECT FisID FROM MuhasebeFisleri WHERE FisNo = 'FIS-2026-0004'),
    (SELECT HesapID FROM HesapPlani WHERE HesapKodu = '100.02'),    -- Döviz Kasası BORÇ
    (SELECT CariID FROM CariHesaplar WHERE CariKodu = 'C002'),       -- XYZ Bilişim
    (SELECT KategoriID FROM GelirGiderKategorileri WHERE KategoriAdi = N'Hizmet Geliri'),
    5000.00, 0.00, N'Döviz kasasına giriş',
    'USD', 36.5000
),
(
    (SELECT FisID FROM MuhasebeFisleri WHERE FisNo = 'FIS-2026-0004'),
    (SELECT HesapID FROM HesapPlani WHERE HesapKodu = '120'),       -- Alıcılar ALACAK
    (SELECT CariID FROM CariHesaplar WHERE CariKodu = 'C002'),       -- XYZ Bilişim
    NULL,
    0.00, 5000.00, N'Alıcılar hesabından düşüş',
    'USD', 36.5000
);
GO

PRINT '>> Tüm örnek veriler başarıyla eklendi.';
GO
