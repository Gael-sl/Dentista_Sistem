import os
from dotenv import load_dotenv

load_dotenv()


def _normalize_database_url(url):
    # Fuerza un driver Python puro/binario compatible con Python moderno.
    if not url:
        return url

    if url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql+psycopg://', 1)

    if url.startswith('postgresql://') and '+psycopg' not in url and '+psycopg2' not in url and '+pg8000' not in url:
        return url.replace('postgresql://', 'postgresql+psycopg://', 1)

    return url

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-cambiar-en-produccion'
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(os.environ.get('DATABASE_URL')) or 'sqlite:///consultorio.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
