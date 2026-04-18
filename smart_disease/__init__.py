import os

# Only use pymysql locally — not on Render
if not os.environ.get('DATABASE_URL'):
    try:
        import pymysql
        pymysql.install_as_MySQLdb()
    except ImportError:
        pass