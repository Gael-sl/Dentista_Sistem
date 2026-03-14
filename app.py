from flask import Flask, redirect, url_for
from sqlalchemy import text
from flask_login import LoginManager
from config import Config
from models import db, Usuario

login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    @app.route('/favicon.ico')
    def favicon():
        return redirect(url_for('static', filename='favicon.svg'))
    
    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))
    
    # Registrar blueprints
    from routes import main_bp
    app.register_blueprint(main_bp)
    
    from api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Crear tablas
    with app.app_context():
        db.create_all()
        ensure_runtime_schema()
        # Crear datos iniciales si no existen
        init_data()
    
    return app


def ensure_runtime_schema():
    """Pequeña migración runtime para columnas nuevas en SQLite sin perder datos."""
    inspector = db.inspect(db.engine)
    if 'configuracion' not in inspector.get_table_names():
        return

    columns = {col['name'] for col in inspector.get_columns('configuracion')}
    with db.engine.begin() as conn:
        if 'recovery_key_hash' not in columns:
            conn.execute(text('ALTER TABLE configuracion ADD COLUMN recovery_key_hash VARCHAR(256)'))
        if 'recovery_hint' not in columns:
            conn.execute(text('ALTER TABLE configuracion ADD COLUMN recovery_hint VARCHAR(120)'))


def init_data():
    """Crear datos iniciales"""
    from models import Usuario, TipoCita, Configuracion
    
    # Crear usuario inicial si no existe
    if not Usuario.query.filter_by(usuario='Dentista').first():
        admin = Usuario(nombre='Dentista', usuario='Dentista')
        admin.set_password('dentista1234')
        db.session.add(admin)
    
    # Crear tipos de cita si no existen
    tipos_default = [
        {'nombre': 'Revisión', 'duracion_minutos': 20, 'color': '#14b8a6'},
        {'nombre': 'Limpieza', 'duracion_minutos': 30, 'color': '#06b6d4'},
        {'nombre': 'Extracción', 'duracion_minutos': 45, 'color': '#f97316'},
        {'nombre': 'Endodoncia', 'duracion_minutos': 60, 'color': '#8b5cf6'},
        {'nombre': 'Ortodoncia', 'duracion_minutos': 30, 'color': '#ec4899'},
        {'nombre': 'Blanqueamiento', 'duracion_minutos': 45, 'color': '#eab308'},
    ]
    
    for tipo in tipos_default:
        if not TipoCita.query.filter_by(nombre=tipo['nombre']).first():
            db.session.add(TipoCita(**tipo))

    # Crear configuración por defecto (singleton)
    if not Configuracion.query.first():
        db.session.add(Configuracion())
    
    db.session.commit()


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
