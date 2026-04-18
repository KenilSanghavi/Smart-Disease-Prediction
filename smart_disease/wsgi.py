import os

from django.core.wsgi import get_wsgi_application

# Only use pymysql locally
if not os.environ.get('DATABASE_URL'):
    try:
        import pymysql
        pymysql.install_as_MySQLdb()
    except ImportError:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_disease.settings')

application = get_wsgi_application()