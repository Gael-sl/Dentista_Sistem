import os
from dotenv import load_dotenv

load_dotenv()


def _normalize_database_url(url):
    # Render y otros proveedores a veces entregan postgres://, SQLAlchemy requiere postgresql://
    if url and url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql://', 1)
    return url

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-cambiar-en-produccion'
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(os.environ.get('DATABASE_URL')) or 'sqlite:///consultorio.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
