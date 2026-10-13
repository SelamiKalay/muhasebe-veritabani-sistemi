"""
Muhasebe Fiş, Gelir-Gider ve Defter Sistemi — Flask Web Uygulaması
====================================================================
Ana uygulama dosyası. Tüm route'lar ve API endpoint'leri burada tanımlanır.
Tüm SQL sorguları parametrik (?) yer tutucular ile çalışır — SQL Injection koruması.
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from database import init_db, init_app, query_db, execute_db, get_db
from seed_data import seed
import json
import os
import hashlib
import hmac
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

# ── Flask Uygulaması ──
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or os.urandom(24)

# Veritabanı hook'larını kaydet
init_app(app)

# ── Şifre ve Yönlendirme Yardımcıları ──
def sifre_hashle(sifre):
    return generate_password_hash(sifre)

def sifre_dogrula(kayitli_hash, sifre):
    """Eski (tuzsuz SHA1) ve yeni (werkzeug) hash biçimlerini doğrular."""
    if '$' not in kayitli_hash:
        eski = hashlib.sha1(sifre.encode('utf-8')).hexdigest()
        return hmac.compare_digest(kayitli_hash, eski)
    return check_password_hash(kayitli_hash, sifre)

def guvenli_yonlendirme(hedef):
    """Açık yönlendirmeyi (open redirect) önlemek için yalnızca site içi yollara izin verir."""
    if hedef and hedef.startswith('/') and not hedef.startswith('//') and '\\' not in hedef:
        return hedef
    return url_for('index')

# ── Oturum Kontrol Decorator'ları ──
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'kullanici_id' not in session:
            flash('Lütfen giriş yapın.', 'warning')
            # Göreli yol: guvenli_yonlendirme mutlak URL'leri reddeder
            hedef = request.full_path if request.query_string else request.path
            return redirect(url_for('login', next=hedef))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'kullanici_id' not in session:
            flash('Lütfen giriş yapın.', 'warning')
            return redirect(url_for('login'))
        if session.get('rol') != 'Yonetici':
            flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


# ── Uygulama başlangıcında DB'yi hazırla ──
with app.app_context():
    init_db()
    # Seed data'yı Flask context dışında çalıştır (kendi bağlantısını kullanır)

# Seed data yükleme (standalone bağlantı kullanır)
seed()


# ══════════════════════════════════════════════
# SAYFA ROUTE'LARI (HTML döndüren)
# ══════════════════════════════════════════════

@app.route('/')
@login_required
def index():
    """
    Dashboard — Ana sayfa.
    Günlük gelir-gider özeti, genel istatistikler ve son fişler.
    """
    # Genel istatistikler
    stats = query_db("""
        SELECT
            (SELECT COUNT(*) FROM MuhasebeFisleri WHERE Durum = 'Aktif') as FisAdedi,
            COALESCE((
                SELECT SUM(ABS(fs2.AlacakTutari - fs2.BorcTutari) * fs2.KurDegeri)
                FROM MuhasebeFisleri f2
                JOIN FisSatirlari fs2 ON f2.FisID = fs2.FisID
                LEFT JOIN HesapPlani hp2 ON fs2.HesapID = hp2.HesapID
                WHERE f2.Durum = 'Aktif' AND (f2.FisTuru IN ('Tahsil','Acilis') OR hp2.HesapTuru = 'Gelir')
                AND NOT (f2.FisTuru IN ('Tahsil','Acilis') AND hp2.HesapAdi LIKE '%Kasa%')
            ), 0) as ToplamGelir,
            COALESCE((
                SELECT SUM(ABS(fs3.BorcTutari - fs3.AlacakTutari) * fs3.KurDegeri)
                FROM MuhasebeFisleri f3
                JOIN FisSatirlari fs3 ON f3.FisID = fs3.FisID
                LEFT JOIN HesapPlani hp3 ON fs3.HesapID = hp3.HesapID
                WHERE f3.Durum = 'Aktif' AND (f3.FisTuru = 'Tediye' OR hp3.HesapTuru = 'Gider')
                AND NOT (f3.FisTuru = 'Tediye' AND hp3.HesapAdi LIKE '%Kasa%')
            ), 0) as ToplamGider
        FROM MuhasebeFisleri f
        LEFT JOIN FisSatirlari fs ON f.FisID = fs.FisID
        LEFT JOIN HesapPlani hp ON fs.HesapID = hp.HesapID
        WHERE f.Durum = 'Aktif'
    """, one=True)

    # Günlük özet tablosu
    gunluk_ozet = query_db("""
        SELECT
            f.FisTarihi as Tarih,
            COALESCE(SUM(CASE WHEN f.FisTuru IN ('Tahsil','Acilis') OR hp.HesapTuru='Gelir' THEN ABS(fs.AlacakTutari - fs.BorcTutari) * fs.KurDegeri ELSE 0 END), 0) as ToplamGelir,
            COALESCE(SUM(CASE WHEN f.FisTuru = 'Tediye' OR hp.HesapTuru='Gider' THEN ABS(fs.BorcTutari - fs.AlacakTutari) * fs.KurDegeri ELSE 0 END), 0) as ToplamGider,
            COUNT(DISTINCT f.FisID) as FisAdedi
        FROM MuhasebeFisleri f
        LEFT JOIN FisSatirlari fs ON f.FisID = fs.FisID
        LEFT JOIN HesapPlani hp ON fs.HesapID = hp.HesapID
        WHERE f.Durum = 'Aktif' AND NOT ((f.FisTuru IN ('Tahsil','Acilis','Tediye')) AND hp.HesapAdi LIKE '%Kasa%')
        GROUP BY f.FisTarihi
        ORDER BY f.FisTarihi DESC
    """)

    # Son eklenen fişler
    son_fisler = query_db("""
        SELECT f.FisID, f.FisNo, f.FisTarihi, f.FisTuru, f.Aciklama, f.Durum,
               k.AdSoyad as Kullanici,
               COALESCE(SUM(fs.BorcTutari * fs.KurDegeri), 0) as ToplamTutar
        FROM MuhasebeFisleri f
        JOIN Kullanicilar k ON f.KullaniciID = k.KullaniciID
        LEFT JOIN FisSatirlari fs ON f.FisID = fs.FisID
        WHERE f.Durum = 'Aktif'
        GROUP BY f.FisID, f.FisNo, f.FisTarihi, f.FisTuru, f.Aciklama, f.Durum, k.AdSoyad
        ORDER BY f.OlusturmaTarihi DESC
        LIMIT 10
    """)

    toplam_gelir = stats['ToplamGelir'] if stats else 0
    toplam_gider = stats['ToplamGider'] if stats else 0
    net_kar = toplam_gelir - toplam_gider
    fis_adedi = stats['FisAdedi'] if stats else 0

    return render_template('index.html',
                           toplam_gelir=toplam_gelir,
                           toplam_gider=toplam_gider,
                           net_kar=net_kar,
                           fis_adedi=fis_adedi,
                           gunluk_ozet=gunluk_ozet,
                           son_fisler=son_fisler)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        kullanici_adi = request.form.get('kullanici_adi', '').strip()
        sifre = request.form.get('sifre', '').strip()
        user = query_db(
            "SELECT * FROM Kullanicilar WHERE KullaniciAdi = ? AND Aktif = 1",
            (kullanici_adi,),
            one=True
        )

        if user and sifre_dogrula(user['SifreHash'], sifre):
            # Eski SHA1 hash'i ilk başarılı girişte güvenli biçime yükselt
            if '$' not in user['SifreHash']:
                execute_db("UPDATE Kullanicilar SET SifreHash = ? WHERE KullaniciID = ?",
                           (sifre_hashle(sifre), user['KullaniciID']))
            session.clear()
            session['kullanici_id'] = user['KullaniciID']
            session['kullanici_adi'] = user['KullaniciAdi']
            session['ad_soyad'] = user['AdSoyad']
            session['rol'] = user['Rol']
            flash(f'Hoş geldiniz, {user["AdSoyad"]}!', 'success')
            return redirect(guvenli_yonlendirme(request.args.get('next')))
        else:
            flash('Hatalı kullanıcı adı veya şifre.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Başarıyla çıkış yaptınız.', 'info')
    return redirect(url_for('login'))

@app.route('/kullanicilar', methods=['GET', 'POST'])
@admin_required
def kullanicilar():
    if request.method == 'POST':
        k_adi = request.form.get('kullanici_adi', '').strip()
        sifre = request.form.get('sifre', '').strip()
        ad_soyad = request.form.get('ad_soyad', '').strip()
        rol = request.form.get('rol', 'Muhasebeci')
        
        if k_adi and sifre and ad_soyad:
            sifre_hash = sifre_hashle(sifre)
            try:
                execute_db(
                    "INSERT INTO Kullanicilar (KullaniciAdi, SifreHash, AdSoyad, Rol) VALUES (?, ?, ?, ?)",
                    (k_adi, sifre_hash, ad_soyad, rol)
                )
                flash('Kullanıcı başarıyla eklendi.', 'success')
            except Exception as e:
                flash(f'Hata: {str(e)}', 'danger')
        else:
            flash('Lütfen tüm alanları doldurun.', 'warning')
        return redirect(url_for('kullanicilar'))

    users = query_db("SELECT * FROM Kullanicilar WHERE Aktif = 1 ORDER BY KullaniciID DESC")
    return render_template('kullanici_yonetimi.html', users=users)

@app.route('/sifre-degistir', methods=['POST'])
@admin_required
def sifre_degistir():
    """Admin tarafından diğer profil şifresini/kendi şifresini değiştirme."""
    kullanici_id = request.form.get('kullanici_id')
    yeni_sifre = request.form.get('yeni_sifre', '').strip()
    
    if kullanici_id and yeni_sifre:
        sifre_hash = sifre_hashle(yeni_sifre)
        try:
            execute_db("UPDATE Kullanicilar SET SifreHash = ? WHERE KullaniciID = ?", (sifre_hash, kullanici_id))
            flash('Şifre başarıyla güncellendi.', 'success')
        except Exception as e:
            flash(f'Hata: {str(e)}', 'danger')
    else:
        flash('Lütfen yeni şifre girin.', 'warning')
        
    return redirect(url_for('kullanicilar'))


@app.route('/fisler')
@login_required
def fisler():
    """
    Fiş Listesi — Tüm fişleri filtreli listeleme.
    Query parametreleri: baslangic, bitis, tur
    """
    baslangic = request.args.get('baslangic', '')
    bitis = request.args.get('bitis', '')
    tur = request.args.get('tur', '')

    # Parametrik sorgu oluştur
    query = """
        SELECT f.FisID, f.FisNo, f.FisTarihi, f.FisTuru, f.Aciklama, f.Durum,
               k.AdSoyad as Kullanici, d.DonemAdi,
               COALESCE(SUM(fs.BorcTutari * fs.KurDegeri), 0) as ToplamBorc,
               COALESCE(SUM(fs.AlacakTutari * fs.KurDegeri), 0) as ToplamAlacak
        FROM MuhasebeFisleri f
        JOIN Kullanicilar k ON f.KullaniciID = k.KullaniciID
        JOIN MuhasebeDonemleri d ON f.DonemID = d.DonemID
        LEFT JOIN FisSatirlari fs ON f.FisID = fs.FisID
        WHERE f.Durum = 'Aktif'
    """
    params = []

    if baslangic:
        query += " AND f.FisTarihi >= ?"
        params.append(baslangic)
    if bitis:
        query += " AND f.FisTarihi <= ?"
        params.append(bitis)
    if tur:
        query += " AND f.FisTuru = ?"
        params.append(tur)

    query += """
        GROUP BY f.FisID, f.FisNo, f.FisTarihi, f.FisTuru, f.Aciklama, f.Durum, k.AdSoyad, d.DonemAdi
        ORDER BY f.FisTarihi DESC, f.FisNo DESC
    """

    fisler = query_db(query, tuple(params))

    return render_template('fisler.html',
                           fisler=fisler,
                           baslangic=baslangic,
                           bitis=bitis,
                           tur=tur)


@app.route('/fis-ekle')
@login_required
def fis_ekle_form():
    """Fiş ekleme formu (GET — sayfa gösterimi)."""
    # Dropdown verileri
    hesaplar = query_db("SELECT HesapID, HesapKodu, HesapAdi, HesapTuru FROM HesapPlani WHERE Aktif=1 ORDER BY HesapKodu")
    cariler = query_db("SELECT CariID, CariKodu, CariAdi FROM CariHesaplar WHERE Aktif=1 ORDER BY CariKodu")
    kategoriler = query_db("SELECT KategoriID, KategoriAdi, Tur FROM GelirGiderKategorileri ORDER BY Tur, KategoriAdi")
    donemler = query_db("SELECT DonemID, DonemAdi FROM MuhasebeDonemleri WHERE Durum='Acik' ORDER BY DonemAdi")

    return render_template('fis_ekle.html',
                           hesaplar=[dict(r) for r in hesaplar],
                           cariler=[dict(r) for r in cariler],
                           kategoriler=[dict(r) for r in kategoriler],
                           donemler=[dict(r) for r in donemler])


@app.route('/fis/<int:fis_id>')
@login_required
def fis_detay(fis_id):
    """Fiş detayı — belirli bir fişin başlık ve satırlarını gösterir."""
    fis = query_db("""
        SELECT f.*, k.AdSoyad as Kullanici, d.DonemAdi
        FROM MuhasebeFisleri f
        JOIN Kullanicilar k ON f.KullaniciID = k.KullaniciID
        JOIN MuhasebeDonemleri d ON f.DonemID = d.DonemID
        WHERE f.FisID = ?
    """, (fis_id,), one=True)

    if not fis:
        flash('Fiş bulunamadı.', 'danger')
        return redirect(url_for('fisler'))

    satirlar = query_db("""
        SELECT fs.*, hp.HesapKodu, hp.HesapAdi,
               c.CariKodu, c.CariAdi,
               kat.KategoriAdi, kat.Tur as KategoriTuru
        FROM FisSatirlari fs
        JOIN HesapPlani hp ON fs.HesapID = hp.HesapID
        LEFT JOIN CariHesaplar c ON fs.CariID = c.CariID
        LEFT JOIN GelirGiderKategorileri kat ON fs.KategoriID = kat.KategoriID
        WHERE fs.FisID = ?
        ORDER BY fs.SatirID
    """, (fis_id,))

    return render_template('fis_detay.html', fis=fis, satirlar=satirlar)


# ══════════════════════════════════════════════
# API ENDPOINT'LERİ (JSON döndüren)
# ══════════════════════════════════════════════

@app.route('/api/fis-ekle', methods=['POST'])
@login_required
def api_fis_ekle():
    """
    Yeni fiş + satırlarını ekleyen API endpoint'i.
    TRANSACTION ile atomik işlem — borç-alacak dengesi kontrol edilir.
    Tüm sorgularda parametrik (?) yer tutucular — SQL Injection koruması.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Geçersiz veri formatı.'}), 400

        fis_no = data.get('fisNo', '').strip()
        fis_tarihi = data.get('fisTarihi', '').strip()
        fis_turu = data.get('fisTuru', '').strip()
        aciklama = data.get('aciklama', '').strip()
        donem_id = data.get('donemId')
        kullanici_id = session.get('kullanici_id')
        satirlar = data.get('satirlar', [])

        # ── Validasyon ──
        if not all([fis_no, fis_tarihi, fis_turu, donem_id, kullanici_id]):
            return jsonify({'success': False, 'message': 'Zorunlu alanlar veya oturum bilgisi eksik.'}), 400

        if fis_turu not in ('Mahsup', 'Tahsil', 'Tediye', 'Acilis', 'Kapanis'):
            return jsonify({'success': False, 'message': 'Geçersiz fiş türü.'}), 400

        if not satirlar or len(satirlar) < 1:
            return jsonify({'success': False, 'message': 'En az bir fiş satırı gereklidir.'}), 400

        # ── Borç-Alacak dengesi kontrolü ──
        toplam_borc = sum(float(s.get('borcTutari', 0)) for s in satirlar)
        toplam_alacak = sum(float(s.get('alacakTutari', 0)) for s in satirlar)

        if abs(toplam_borc - toplam_alacak) > 0.01:
            return jsonify({
                'success': False,
                'message': f'Borç-alacak dengesi tutmuyor. Borç: {toplam_borc:,.2f}, Alacak: {toplam_alacak:,.2f}'
            }), 400

        if toplam_borc == 0:
            return jsonify({'success': False, 'message': 'En az bir borç veya alacak tutarı girilmelidir.'}), 400

        # ── Dönem kontrolü ──
        donem = query_db("SELECT Durum FROM MuhasebeDonemleri WHERE DonemID = ?", (donem_id,), one=True)
        if not donem:
            return jsonify({'success': False, 'message': 'Belirtilen dönem bulunamadı.'}), 400
        if donem['Durum'] == 'Kapali':
            return jsonify({'success': False, 'message': 'Kapatılmış döneme fiş eklenemez.'}), 400

        # ── TRANSACTION ile kayıt ──
        db = get_db()
        try:
            # Fiş başlığı ekle
            cur = db.execute("""
                INSERT INTO MuhasebeFisleri (FisNo, FisTarihi, FisTuru, Aciklama, DonemID, KullaniciID)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (fis_no, fis_tarihi, fis_turu, aciklama, donem_id, kullanici_id))
            fis_id = cur.lastrowid

            # Fiş satırlarını ekle
            for s in satirlar:
                hesap_id = s.get('hesapId')
                cari_id = s.get('cariId') or None
                kategori_id = s.get('kategoriId') or None
                borc = float(s.get('borcTutari', 0))
                alacak = float(s.get('alacakTutari', 0))
                satir_aciklama = s.get('aciklama', '')
                para_birimi = s.get('paraBirimi', 'TRY')
                kur = float(s.get('kurDegeri', 1.0))

                if not hesap_id:
                    raise ValueError('Her satırda hesap seçilmelidir.')

                db.execute("""
                    INSERT INTO FisSatirlari
                        (FisID, HesapID, CariID, KategoriID, BorcTutari, AlacakTutari, Aciklama, ParaBirimi, KurDegeri)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (fis_id, hesap_id, cari_id, kategori_id, borc, alacak, satir_aciklama, para_birimi, kur))

            # Log kaydı ekle
            db.execute("""
                INSERT INTO FisLog (FisID, Islem, YeniDegerler, KullaniciID)
                VALUES (?, 'INSERT', ?, ?)
            """, (fis_id, json.dumps({
                'FisNo': fis_no, 'FisTarihi': fis_tarihi, 'FisTuru': fis_turu,
                'ToplamTutar': toplam_borc, 'SatirSayisi': len(satirlar)
            }, ensure_ascii=False), kullanici_id))

            db.commit()

            return jsonify({
                'success': True,
                'message': f'Fiş başarıyla eklendi. (FisNo: {fis_no})',
                'fisId': fis_id
            }), 201

        except Exception as e:
            db.rollback()
            raise e

    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'Sunucu hatası: {str(e)}'}), 500


@app.route('/api/fis-sil/<int:fis_id>', methods=['POST'])
@admin_required
def api_fis_sil(fis_id):
    """
    Fiş ve ilgili satırlarını siler. (Sadece Yönetici)
    """
    db = get_db()
    try:
        # Fiş var mı kontrol et
        fis = query_db("SELECT * FROM MuhasebeFisleri WHERE FisID = ?", (fis_id,), one=True)
        if not fis:
            return jsonify({'success': False, 'message': 'Fiş bulunamadı.'}), 404

        # Satırları ve logları sil (veya Pasif yap)
        # Burada fiziksel silme yapıyoruz
        db.execute("DELETE FROM FisSatirlari WHERE FisID = ?", (fis_id,))
        db.execute("DELETE FROM MuhasebeFisleri WHERE FisID = ?", (fis_id,))
        
        # Log kaydı eklenebilir
        db.execute("""
            INSERT INTO FisLog (FisID, Islem, EskiDegerler, KullaniciID)
            VALUES (?, 'DELETE', ?, ?)
        """, (fis_id, json.dumps({'FisNo': fis['FisNo']}, ensure_ascii=False), session.get('kullanici_id')))

        db.commit()
        return jsonify({'success': True, 'message': 'Fiş başarıyla silindi.'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': f'Hata: {str(e)}'}), 500


@app.route('/api/hesaplar')
@login_required
def api_hesaplar():
    """Hesap planı listesi (JSON)."""
    rows = query_db("SELECT HesapID, HesapKodu, HesapAdi, HesapTuru FROM HesapPlani WHERE Aktif=1 ORDER BY HesapKodu")
    return jsonify([dict(r) for r in rows])


@app.route('/api/cariler')
@login_required
def api_cariler():
    """Cari hesap listesi (JSON)."""
    rows = query_db("SELECT CariID, CariKodu, CariAdi, CariTuru FROM CariHesaplar WHERE Aktif=1 ORDER BY CariKodu")
    return jsonify([dict(r) for r in rows])


@app.route('/api/kategoriler')
@login_required
def api_kategoriler():
    """Gelir-gider kategorileri listesi (JSON)."""
    rows = query_db("SELECT KategoriID, KategoriAdi, Tur FROM GelirGiderKategorileri ORDER BY Tur, KategoriAdi")
    return jsonify([dict(r) for r in rows])


@app.route('/api/dashboard')
@login_required
def api_dashboard():
    """Dashboard verileri (JSON) — aylık kâr/zarar grafiği için."""
    aylik = query_db("""
        SELECT
            substr(f.FisTarihi, 1, 7) as Ay,
            COALESCE(SUM(CASE WHEN f.FisTuru IN ('Tahsil','Acilis') OR hp.HesapTuru='Gelir' THEN ABS(fs.AlacakTutari - fs.BorcTutari)*fs.KurDegeri ELSE 0 END), 0) as Gelir,
            COALESCE(SUM(CASE WHEN f.FisTuru = 'Tediye' OR hp.HesapTuru='Gider' THEN ABS(fs.BorcTutari - fs.AlacakTutari)*fs.KurDegeri ELSE 0 END), 0) as Gider
        FROM FisSatirlari fs
        JOIN MuhasebeFisleri f ON fs.FisID = f.FisID
        JOIN HesapPlani hp ON fs.HesapID = hp.HesapID
        WHERE f.Durum = 'Aktif' AND NOT ((f.FisTuru IN ('Tahsil','Acilis','Tediye')) AND hp.HesapAdi LIKE '%Kasa%')
        GROUP BY substr(f.FisTarihi, 1, 7)
        ORDER BY Ay
    """)
    return jsonify([dict(r) for r in aylik])


# ── Çalıştırma ──
if __name__ == '__main__':
    print("=" * 50)
    print("  Muhasebe Web Uygulaması")
    print("  http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1', host='127.0.0.1', port=5000)
