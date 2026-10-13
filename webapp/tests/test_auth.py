"""
Kimlik doğrulama testleri: şifre hash'i, giriş/çıkış, oturum ve yetki
kontrolü, güvenli yönlendirme.
"""

import hashlib
import os
from urllib.parse import urlsplit

import pytest

import app as app_module
from conftest import ADMIN_SIFRE, giris, kullanici_ekle


def yer(response):
    """Yönlendirme hedefinin yolunu (query dahil) döndürür."""
    parts = urlsplit(response.headers["Location"])
    return parts.path + (f"?{parts.query}" if parts.query else "")


# ══════════════════════════════════════════
#  Şifre hash'i
# ══════════════════════════════════════════

class TestSifreHash:
    def test_yeni_hash_tuzlu_ve_dogrulaniyor(self):
        h1 = app_module.sifre_hashle("gizli")
        h2 = app_module.sifre_hashle("gizli")
        assert h1 != h2, "aynı şifre için tuz farklı olmalı"
        assert "$" in h1
        assert app_module.sifre_dogrula(h1, "gizli")
        assert not app_module.sifre_dogrula(h1, "yanlis")

    def test_eski_sha1_hash_destekleniyor(self):
        eski = hashlib.sha1(b"eski-sifre").hexdigest()
        assert app_module.sifre_dogrula(eski, "eski-sifre")
        assert not app_module.sifre_dogrula(eski, "baska")

    def test_seed_admin_sabit_sifre_kullanmiyor(self, db):
        admin = db.query_db("SELECT SifreHash FROM Kullanicilar WHERE KullaniciAdi='admin'", one=True)
        assert admin is not None
        assert "$" in admin["SifreHash"], "admin şifresi güvenli biçimde saklanmalı"
        assert not app_module.sifre_dogrula(admin["SifreHash"], "admin")
        assert app_module.sifre_dogrula(admin["SifreHash"], ADMIN_SIFRE)

    def test_ilk_giris_dosyasi_veritabaninin_yaninda(self):
        yol = os.path.join(os.path.dirname(os.environ["MUHASEBE_DB"]), "ILK_GIRIS.txt")
        assert os.path.exists(yol)
        with open(yol, encoding="utf-8") as f:
            assert ADMIN_SIFRE in f.read()


# ══════════════════════════════════════════
#  Giriş / çıkış ve oturum
# ══════════════════════════════════════════

class TestGiris:
    def test_dogru_sifre_ile_giris(self, client):
        r = giris(client, "admin", ADMIN_SIFRE)
        assert r.status_code == 302 and yer(r) == "/"
        with client.session_transaction() as s:
            assert s["kullanici_adi"] == "admin"
            assert s["rol"] == "Yonetici"

    @pytest.mark.parametrize("kullanici, sifre", [
        ("admin", "admin"),          # eski varsayılan şifre artık geçmez
        ("admin", "yanlis"),
        ("yok-boyle-biri", "x"),
        ("", ""),
    ])
    def test_hatali_giris_reddedilir(self, client, kullanici, sifre):
        r = giris(client, kullanici, sifre)
        assert r.status_code == 200
        assert "Hatalı kullanıcı adı veya şifre" in r.get_data(as_text=True)
        with client.session_transaction() as s:
            assert "kullanici_id" not in s

    def test_pasif_kullanici_giris_yapamaz(self, client):
        kullanici_ekle("pasif", app_module.sifre_hashle("sifre"), aktif=0)
        giris(client, "pasif", "sifre")
        with client.session_transaction() as s:
            assert "kullanici_id" not in s

    def test_eski_sha1_hash_giriste_yukseltilir(self, client, db):
        kullanici_ekle("eskici", hashlib.sha1(b"eski123").hexdigest())
        r = giris(client, "eskici", "eski123")
        assert r.status_code == 302
        h = db.query_db("SELECT SifreHash FROM Kullanicilar WHERE KullaniciAdi='eskici'", one=True)
        assert "$" in h["SifreHash"], "SHA1 hash ilk girişte güvenli biçime yükseltilmeli"
        assert app_module.sifre_dogrula(h["SifreHash"], "eski123")

    def test_giris_onceki_oturum_verisini_temizler(self, client):
        with client.session_transaction() as s:
            s["eski_anahtar"] = "kalmamali"
        giris(client, "admin", ADMIN_SIFRE)
        with client.session_transaction() as s:
            assert "eski_anahtar" not in s

    def test_cikis_oturumu_bitirir(self, client):
        giris(client, "admin", ADMIN_SIFRE)
        r = client.get("/logout")
        assert yer(r) == "/login"
        with client.session_transaction() as s:
            assert "kullanici_id" not in s
        assert yer(client.get("/")).startswith("/login")


# ══════════════════════════════════════════
#  Yetki kontrolü
# ══════════════════════════════════════════

KORUNAN_SAYFALAR = ["/", "/fisler", "/fis-ekle", "/fis/1",
                    "/api/hesaplar", "/api/cariler", "/api/kategoriler", "/api/dashboard"]


class TestYetki:
    @pytest.mark.parametrize("yol", KORUNAN_SAYFALAR)
    def test_girissiz_erisim_logine_yonlenir(self, client, yol):
        r = client.get(yol)
        assert r.status_code == 302
        assert yer(r).startswith("/login")

    def test_api_post_girissiz_reddedilir(self, client):
        assert yer(client.post("/api/fis-ekle", json={})).startswith("/login")
        assert yer(client.post("/api/fis-sil/1")).startswith("/login")

    def test_yonetici_sayfasi_muhasebeciye_kapali(self, client):
        kullanici_ekle("muh", app_module.sifre_hashle("muh-sifre"), rol="Muhasebeci")
        giris(client, "muh", "muh-sifre")
        assert yer(client.get("/kullanicilar")) == "/"
        r = client.post("/sifre-degistir", data={"kullanici_id": "1", "yeni_sifre": "ele-gecir"})
        assert yer(r) == "/"
        r = client.post("/api/fis-sil/1")
        assert yer(r) == "/"

    def test_muhasebeci_admin_sifresini_degistiremez(self, client, db):
        kullanici_ekle("muh2", app_module.sifre_hashle("muh-sifre"), rol="Muhasebeci")
        giris(client, "muh2", "muh-sifre")
        client.post("/sifre-degistir", data={"kullanici_id": "1", "yeni_sifre": "ele-gecir"})
        admin = db.query_db("SELECT SifreHash FROM Kullanicilar WHERE KullaniciAdi='admin'", one=True)
        assert not app_module.sifre_dogrula(admin["SifreHash"], "ele-gecir")

    def test_yonetici_kullanicilar_sayfasini_gorur(self, client):
        giris(client, "admin", ADMIN_SIFRE)
        r = client.get("/kullanicilar")
        assert r.status_code == 200

    def test_yonetici_sifre_degistirince_yeni_sifre_gecerli(self, client, db):
        kullanici_ekle("degisecek", app_module.sifre_hashle("eski"), rol="Muhasebeci")
        uid = db.query_db("SELECT KullaniciID FROM Kullanicilar WHERE KullaniciAdi='degisecek'", one=True)[0]
        giris(client, "admin", ADMIN_SIFRE)
        client.post("/sifre-degistir", data={"kullanici_id": str(uid), "yeni_sifre": "yeni-sifre"})
        client.get("/logout")
        giris(client, "degisecek", "eski")
        with client.session_transaction() as s:
            assert "kullanici_id" not in s
        giris(client, "degisecek", "yeni-sifre")
        with client.session_transaction() as s:
            assert s["kullanici_adi"] == "degisecek"


# ══════════════════════════════════════════
#  Yönlendirme
# ══════════════════════════════════════════

class TestYonlendirme:
    def test_login_required_goreli_next_verir(self, client):
        r = client.get("/fisler?tur=Gelir")
        assert yer(r).startswith("/login?next=")
        next_ = urlsplit(r.headers["Location"]).query.split("next=", 1)[1]
        assert not next_.startswith("http"), "next mutlak URL olmamalı (girişte reddedilir)"

    def test_giristen_sonra_istenen_sayfaya_donulur(self, client):
        # Regresyon: next mutlak URL olduğu için kullanıcı hep ana sayfaya düşüyordu
        r = client.get("/fisler")
        login_url = yer(r)
        r = client.post(login_url, data={"kullanici_adi": "admin", "sifre": ADMIN_SIFRE})
        assert yer(r) == "/fisler"

    @pytest.mark.parametrize("hedef", [
        "//kotu.example.com",
        "https://kotu.example.com/",
        "/\\kotu.example.com",
        "javascript:alert(1)",
        "kotu.example.com",
    ])
    def test_acik_yonlendirme_engellenir(self, client, hedef):
        r = giris(client, "admin", ADMIN_SIFRE, next_=hedef)
        assert yer(r) == "/"

    def test_site_ici_next_kabul_edilir(self, client):
        r = giris(client, "admin", ADMIN_SIFRE, next_="/fis-ekle")
        assert yer(r) == "/fis-ekle"

    def test_guvenli_yonlendirme_fonksiyonu(self, app):
        with app.test_request_context():
            assert app_module.guvenli_yonlendirme("/fisler") == "/fisler"
            assert app_module.guvenli_yonlendirme(None) == "/"
            assert app_module.guvenli_yonlendirme("//x.com") == "/"
            assert app_module.guvenli_yonlendirme("http://x.com") == "/"
