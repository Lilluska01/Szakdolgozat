import os
from pathlib import Path
class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent
    DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
    DB_PORT = int(os.getenv('DB_PORT', '3306'))
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_NAME = os.getenv('DB_NAME', 'university_system')
    DB_CHARSET = os.getenv('DB_CHARSET', 'utf8mb4')
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-this-development-secret')
    TOKEN_TTL_HOURS = int(os.getenv('TOKEN_TTL_HOURS', '8'))
    API_HOST = os.getenv('API_HOST', '127.0.0.1')
    API_PORT = int(os.getenv('API_PORT', '5000'))
    ACCESS_COOLDOWN_SECONDS = int(os.getenv('ACCESS_COOLDOWN_SECONDS', '5'))
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_DIR = BASE_DIR / 'logs'
    REPORT_DIR = BASE_DIR / 'reports'
    @classmethod
    def database_options(cls):
        return {'host': cls.DB_HOST, 'port': cls.DB_PORT, 'user': cls.DB_USER,
                'password': cls.DB_PASSWORD, 'database': cls.DB_NAME,
                'charset': cls.DB_CHARSET, 'autocommit': False,
                'connection_timeout': 10}
