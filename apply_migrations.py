import pymysql

conn = pymysql.connect(
    host='mysql-33f14155-hanzalas348-de44.a.aivencloud.com',
    port=16710,
    user='avnadmin',
    password='AVNS_uHkB-HrLcoESXJFa-zo',
    database='defaultdb',
    ssl={'ssl_disabled': False},
)
cur = conn.cursor()

# ── 1. masterdata_testinterpretation.test_name -> UNIQUE ─────────────────────
cur.execute("SHOW INDEX FROM masterdata_testinterpretation WHERE Key_name != 'PRIMARY'")
existing = [r[2] for r in cur.fetchall()]
if 'masterdata_testinterpretation_test_name' not in existing:
    try:
        cur.execute("ALTER TABLE masterdata_testinterpretation ADD UNIQUE KEY masterdata_testinterpretation_test_name (test_name(191))")
        conn.commit()
        print('Added UNIQUE index on masterdata_testinterpretation.test_name')
    except Exception as e:
        print(f'  Note: {e}')
        conn.rollback()
else:
    print('masterdata_testinterpretation.test_name already unique')

# Mark migration as applied
cur.execute("SELECT id FROM django_migrations WHERE app='masterdata' AND name='0008_testinterpretation_unique_test_name'")
if not cur.fetchone():
    cur.execute("INSERT INTO django_migrations (app, name, applied) VALUES ('masterdata', '0008_testinterpretation_unique_test_name', NOW())")
    conn.commit()
    print('Migration 0008 (masterdata) marked as applied')

# ── 2. pharmacy_pharmacyitem.name -> UNIQUE ───────────────────────────────────
cur.execute("SHOW INDEX FROM pharmacy_pharmacyitem WHERE Key_name != 'PRIMARY'")
existing = [r[2] for r in cur.fetchall()]
if 'pharmacy_pharmacyitem_name' not in existing:
    try:
        cur.execute("ALTER TABLE pharmacy_pharmacyitem ADD UNIQUE KEY pharmacy_pharmacyitem_name (name(191))")
        conn.commit()
        print('Added UNIQUE index on pharmacy_pharmacyitem.name')
    except Exception as e:
        print(f'  Note: {e}')
        conn.rollback()
else:
    print('pharmacy_pharmacyitem.name already unique')

# Mark migration as applied
cur.execute("SELECT id FROM django_migrations WHERE app='pharmacy' AND name='0004_pharmacyitem_unique_name'")
if not cur.fetchone():
    cur.execute("INSERT INTO django_migrations (app, name, applied) VALUES ('pharmacy', '0004_pharmacyitem_unique_name', NOW())")
    conn.commit()
    print('Migration 0004 (pharmacy) marked as applied')

conn.close()
print('Done.')
