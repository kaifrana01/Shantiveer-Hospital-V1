import os

# Install pymysql as MySQLdb only when explicitly running with MySQL.
# On Vercel (PostgreSQL via DATABASE_URL), pymysql is not installed and not needed.
# On the VPS (MySQL/Aiven), set USE_MYSQL=true in the environment.
if os.environ.get('USE_MYSQL', '').lower() == 'true':
    try:
        import pymysql
        pymysql.install_as_MySQLdb()
    except ImportError:
        pass
