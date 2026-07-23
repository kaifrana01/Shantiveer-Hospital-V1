

import pymysql

pymysql.install_as_MySQLdb()


import os

if os.environ.get('USE_MYSQL', '').lower() == 'true':
    try:
        import pymysql
        pymysql.install_as_MySQLdb()
    except ImportError:
        pass
