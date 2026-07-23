-- ============================================================
--  ShantiVeer HMS — MySQL Database Setup Script
--  Run as MySQL root (or any user with CREATE privilege):
--      mysql -u root -p < mysql_schema.sql
-- ============================================================

-- 1. Create database
CREATE DATABASE IF NOT EXISTS shantiveer_hms
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- 2. Create dedicated user (change passwords if needed)
CREATE USER IF NOT EXISTS 'hms_user'@'localhost' IDENTIFIED BY 'HMS@Secure123';
CREATE USER IF NOT EXISTS 'hms_user'@'127.0.0.1' IDENTIFIED BY 'HMS@Secure123';

-- 3. Grant full access to the database
GRANT ALL PRIVILEGES ON shantiveer_hms.* TO 'hms_user'@'localhost';
GRANT ALL PRIVILEGES ON shantiveer_hms.* TO 'hms_user'@'127.0.0.1';
FLUSH PRIVILEGES;

-- 4. Verify
SELECT User, Host FROM mysql.user WHERE User = 'hms_user';
SHOW GRANTS FOR 'hms_user'@'localhost';

-- ============================================================
-- NOTE: Do NOT create the application tables here.
--       Django migrations handle all table creation.
--       After running this script, run:
--
--   export DJANGO_SETTINGS_MODULE=ShantiVeer_hms.settings_mysql
--   python manage.py migrate
--   python manage.py setup_roles
--   python manage.py seed_database      ← optional demo data
--   python manage.py runserver
-- ============================================================

-- 5. (Optional) Create a read-only reporting user
-- CREATE USER IF NOT EXISTS 'hms_readonly'@'localhost' IDENTIFIED BY 'ReadOnly@123';
-- GRANT SELECT ON shantiveer_hms.* TO 'hms_readonly'@'localhost';
-- FLUSH PRIVILEGES;
