from contextlib import contextmanager
import mysql.connector
from mysql.connector import Error
from config.config import Config
class DatabaseError(RuntimeError):
    pass


class Database:
    def __init__(self, options=None):
        self.options = options or Config.database_options()

    def get_connection(self):
        try:
            return mysql.connector.connect(**self.options)
        except Error as exc:
            raise DatabaseError(f"MySQL kapcsolat sikertelen: {exc}") from exc

    @contextmanager
    def cursor(self, *, commit=False):
        connection = self.get_connection()
        cursor = connection.cursor(dictionary=True)
        try:
            yield cursor
            if commit:
                connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def get_cursor(self):
        connection = self.get_connection()
        return connection, connection.cursor(dictionary=True)
