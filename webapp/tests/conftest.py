"""
Test ortamı: her test oturumu geçici bir SQLite veritabanı kullanır.

app.py içe aktarıldığında tabloları oluşturup örnek veriyi yüklediği için
MUHASEBE_DB ve MUHASEBE_ADMIN_SIFRE, app içe aktarılmadan ÖNCE ayarlanır.
"""

import os
import shutil
import sys
import tempfile

import pytest

WEBAPP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WEBAPP_DIR)

TMP_DIR = tempfile.mkdtemp(prefix="muhasebe-test-")
os.environ["MUHASEBE_DB"] = os.path.join(TMP_DIR, "test.db")
os.environ["MUHASEBE_ADMIN_SIFRE"] = "Test-Admin-Sifre-1"
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import app as app_module  # noqa: E402

ADMIN_SIFRE = os.environ["MUHASEBE_ADMIN_SIFRE"]


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(TMP_DIR, ignore_errors=True)


@pytest.fixture
def app():
    app_module.app.config.update(TESTING=True)
    return app_module.app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    """Uygulamanın veritabanı yardımcılarına app bağlamında erişim."""
    with app.app_context():
        yield app_module


def giris(client, kullanici_adi, sifre, next_=None):
    url = "/login" + (f"?next={next_}" if next_ is not None else "")
    return client.post(url, data={"kullanici_adi": kullanici_adi, "sifre": sifre})


def kullanici_ekle(kullanici_adi, sifre_hash, rol="Muhasebeci", aktif=1):
    """Testler için doğrudan veritabanına kullanıcı ekler (ya da günceller)."""
    with app_module.app.app_context():
        app_module.execute_db("DELETE FROM Kullanicilar WHERE KullaniciAdi = ?", (kullanici_adi,))
        app_module.execute_db(
            "INSERT INTO Kullanicilar (KullaniciAdi, SifreHash, AdSoyad, Rol, Aktif) "
            "VALUES (?, ?, ?, ?, ?)",
            (kullanici_adi, sifre_hash, kullanici_adi.title(), rol, aktif),
        )
