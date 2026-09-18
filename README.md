# Accounting Database System

**English** | [Türkçe](README.tr.md)

A relational database project for managing accounting vouchers, income/expenses and
ledgers for small and medium-sized businesses. Alongside the SQL Server (T-SQL)
schema and queries, it includes a Flask web interface that uses the same model on
SQLite. Table, column and UI names are in Turkish.

## Highlights

- **Double-entry bookkeeping** — total debit = total credit on every voucher
- An 8-table schema normalized to 3NF; self-referencing chart-of-accounts hierarchy
- Period control (no entries into closed periods) and soft delete
- **Database objects:** `sp_FisEkle` (with transaction control), `fn_HesapBakiyesi`,
  `vw_GunlukGelirGiderOzeti`, and `trg_FisLog_*` triggers for the audit trail
- Role-based authorization and SQL injection protection through parameterized queries
- Test data with 6,000 vouchers

## Contents

```
sql/
  01_DDL_Create_Tables.sql       Tables and constraints
  02_DML_Insert_Data.sql         Sample data
  03_Temel_Sorgular.sql          Basic queries
  04_Ileri_Duzey_Sorgular.sql    JOINs, subqueries, analytical queries
  05_Veritabani_Objeleri.sql     Views, stored procedures, triggers, functions
  06_Toplu_Fis_Verisi_6000.sql   Bulk test data
docs/
  MuhasebeDB_Proje_Dokumani.md   Project report in Turkish (problem definition, ER, normalization, security)
  ER_Diyagrami.png
webapp/                          Flask web application (SQLite)
```

## SQL Server Setup

Run the scripts in the `sql/` folder in numerical order in SSMS or Azure Data Studio.

## Web Application

Includes a dashboard, voucher listing / creation / details, user management and
JSON API endpoints.

```bash
cd webapp
pip install -r requirements.txt
python app.py
```

The app opens at `http://127.0.0.1:5000`. The database is created with sample data
on first run. Default login: `admin` / `admin` — change it after the first login.

For more test data: `python generate_6000_fis.py`

![ER diagram](docs/ER_Diyagrami.png)
