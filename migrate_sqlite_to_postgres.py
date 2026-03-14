import os
import sqlite3
from datetime import datetime

from app import create_app
from models import db, Usuario, TipoCita, Paciente, Cita, Configuracion


def parse_dt(value):
    if value in (None, ""):
        return None
    # Guarda compatibilidad con formatos comunes de SQLite
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def parse_date(value):
    if value in (None, ""):
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_time(value):
    if value in (None, ""):
        return None
    for fmt in ("%H:%M:%S.%f", "%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Formato de hora no soportado: {value}")


def sqlite_columns(conn, table_name):
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {r[1] for r in rows}


def row_to_dict(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def main():
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("Define DATABASE_URL apuntando a Postgres antes de ejecutar la migracion")
    if "sqlite" in database_url.lower():
        raise RuntimeError("DATABASE_URL no debe apuntar a SQLite para esta migracion")

    sqlite_path = os.environ.get("SQLITE_PATH", os.path.join("instance", "consultorio.db"))
    if not os.path.exists(sqlite_path):
        raise FileNotFoundError(f"No existe la base SQLite origen: {sqlite_path}")

    app = create_app()

    with app.app_context():
        db.create_all()

        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row

        try:
            # usuarios
            cur = conn.execute("SELECT * FROM usuarios")
            for row in cur.fetchall():
                r = row_to_dict(cur, row)
                obj = Usuario(
                    id=r.get("id"),
                    nombre=r.get("nombre"),
                    usuario=r.get("usuario"),
                    password_hash=r.get("password_hash"),
                    created_at=parse_dt(r.get("created_at")) or datetime.utcnow(),
                )
                db.session.merge(obj)

            # configuracion (si existe)
            if "configuracion" in {t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}:
                cfg_cols = sqlite_columns(conn, "configuracion")
                cur = conn.execute("SELECT * FROM configuracion LIMIT 1")
                row = cur.fetchone()
                if row:
                    r = row_to_dict(cur, row)
                    obj = Configuracion(
                        id=r.get("id") or 1,
                        semana_inicio=r.get("semana_inicio", "14:00"),
                        semana_fin=r.get("semana_fin", "18:00"),
                        fin_semana_inicio=r.get("fin_semana_inicio", "09:00"),
                        fin_semana_fin=r.get("fin_semana_fin", "13:00"),
                        trabaja_sabado=bool(r.get("trabaja_sabado", 1)),
                        trabaja_domingo=bool(r.get("trabaja_domingo", 0)),
                        recovery_key_hash=r.get("recovery_key_hash") if "recovery_key_hash" in cfg_cols else None,
                        recovery_hint=r.get("recovery_hint") if "recovery_hint" in cfg_cols else None,
                        updated_at=parse_dt(r.get("updated_at")) or datetime.utcnow(),
                    )
                    db.session.merge(obj)

            # tipos_cita
            cur = conn.execute("SELECT * FROM tipos_cita")
            for row in cur.fetchall():
                r = row_to_dict(cur, row)
                obj = TipoCita(
                    id=r.get("id"),
                    nombre=r.get("nombre"),
                    duracion_minutos=r.get("duracion_minutos") or 30,
                    color=r.get("color") or "#14b8a6",
                    activo=bool(r.get("activo", 1)),
                )
                db.session.merge(obj)

            # pacientes
            cur = conn.execute("SELECT * FROM pacientes")
            for row in cur.fetchall():
                r = row_to_dict(cur, row)
                obj = Paciente(
                    id=r.get("id"),
                    nombre=r.get("nombre"),
                    apellidos=r.get("apellidos"),
                    telefono=r.get("telefono"),
                    email=r.get("email"),
                    notas=r.get("notas"),
                    created_at=parse_dt(r.get("created_at")) or datetime.utcnow(),
                )
                db.session.merge(obj)

            # citas
            cur = conn.execute("SELECT * FROM citas")
            for row in cur.fetchall():
                r = row_to_dict(cur, row)
                obj = Cita(
                    id=r.get("id"),
                    paciente_id=r.get("paciente_id"),
                    tipo_cita_id=r.get("tipo_cita_id"),
                    fecha=parse_date(r.get("fecha")),
                    hora_inicio=parse_time(r.get("hora_inicio")),
                    hora_fin=parse_time(r.get("hora_fin")),
                    estado=r.get("estado") or "pendiente",
                    confirmada_whatsapp=bool(r.get("confirmada_whatsapp", 0)),
                    notas=r.get("notas"),
                    created_at=parse_dt(r.get("created_at")) or datetime.utcnow(),
                    updated_at=parse_dt(r.get("updated_at")) or datetime.utcnow(),
                )
                db.session.merge(obj)

            db.session.commit()
            print("Migracion completada: SQLite -> Postgres")
        finally:
            conn.close()


if __name__ == "__main__":
    main()
