import os

# Only use pymysql for local development
if not os.environ.get('DATABASE_URL'):
    import pymysql
    pymysql.install_as_MySQLdb()