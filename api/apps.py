from django.apps import AppConfig
from django.db.backends.signals import connection_created


def configure_sqlite_connection(sender, connection, **kwargs):
    """
    Configure production-grade SQLite pragmas on every connection:
    - WAL mode: allows concurrent readers while writing
    - synchronous=NORMAL: optimal balance between ACID safety and speed
    - busy_timeout=10000: wait up to 10 seconds for locks before busy error
    """
    if connection.vendor == 'sqlite':
        cursor = connection.cursor()
        cursor.execute('PRAGMA journal_mode = WAL;')
        cursor.execute('PRAGMA synchronous = NORMAL;')
        cursor.execute('PRAGMA busy_timeout = 10000;')
        cursor.execute('PRAGMA wal_autocheckpoint = 1000;')
        cursor.execute('PRAGMA foreign_keys = ON;')


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        connection_created.connect(configure_sqlite_connection)
