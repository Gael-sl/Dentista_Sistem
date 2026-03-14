from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Usuario(UserMixin, db.Model):
    """Modelo para el dentista/usuario del sistema"""
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Configuracion(db.Model):
    """Configuración general del consultorio (singleton)"""
    __tablename__ = 'configuracion'

    id = db.Column(db.Integer, primary_key=True)
    semana_inicio = db.Column(db.String(5), default='14:00')
    semana_fin = db.Column(db.String(5), default='18:00')
    fin_semana_inicio = db.Column(db.String(5), default='09:00')
    fin_semana_fin = db.Column(db.String(5), default='13:00')
    trabaja_sabado = db.Column(db.Boolean, default=True)
    trabaja_domingo = db.Column(db.Boolean, default=False)
    recovery_key_hash = db.Column(db.String(256), nullable=True)
    recovery_hint = db.Column(db.String(120), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TipoCita(db.Model):
    """Tipos de cita/consulta disponibles"""
    __tablename__ = 'tipos_cita'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)  # Limpieza, Extracción, Revisión, etc.
    duracion_minutos = db.Column(db.Integer, default=30)  # Duración estimada
    color = db.Column(db.String(7), default='#14b8a6')  # Color para mostrar en calendario
    activo = db.Column(db.Boolean, default=True)
    
    citas = db.relationship('Cita', backref='tipo_cita', lazy='dynamic')


class Paciente(db.Model):
    """Información del paciente"""
    __tablename__ = 'pacientes'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(15), nullable=False)
    email = db.Column(db.String(120))
    notas = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    citas = db.relationship('Cita', backref='paciente', lazy='dynamic')
    
    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellidos}"


class Cita(db.Model):
    """Citas agendadas"""
    __tablename__ = 'citas'
    
    id = db.Column(db.Integer, primary_key=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey('pacientes.id'), nullable=False)
    tipo_cita_id = db.Column(db.Integer, db.ForeignKey('tipos_cita.id'), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    
    # Estados: pendiente, confirmada, cancelada, completada, reagendada
    estado = db.Column(db.String(20), default='pendiente')
    confirmada_whatsapp = db.Column(db.Boolean, default=False)
    notas = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def fecha_hora_formateada(self):
        return f"{self.fecha.strftime('%d/%m/%Y')} {self.hora_inicio.strftime('%I:%M %p')}"
    
    @staticmethod
    def hay_conflicto(fecha, hora_inicio, hora_fin, excluir_id=None):
        """Verifica si hay conflicto de horario con otra cita"""
        query = Cita.query.filter(
            Cita.fecha == fecha,
            Cita.estado.notin_(['cancelada']),
            db.or_(
                db.and_(Cita.hora_inicio <= hora_inicio, Cita.hora_fin > hora_inicio),
                db.and_(Cita.hora_inicio < hora_fin, Cita.hora_fin >= hora_fin),
                db.and_(Cita.hora_inicio >= hora_inicio, Cita.hora_fin <= hora_fin)
            )
        )
        if excluir_id:
            query = query.filter(Cita.id != excluir_id)
        return query.first() is not None
