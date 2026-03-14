from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from models import db, Paciente, Cita, TipoCita, Configuracion, Usuario
from datetime import datetime, timedelta
from urllib.parse import quote
import calendar
from werkzeug.security import generate_password_hash, check_password_hash

api_bp = Blueprint('api', __name__)

def _parse_hhmm(value):
    return datetime.strptime(value, '%H:%M').time()


def get_or_create_config():
    config = Configuracion.query.first()
    if not config:
        config = Configuracion()
        db.session.add(config)
        db.session.commit()
    return config


def validar_horario_laboral(fecha, hora_inicio, hora_fin):
    """Devuelve mensaje de error si está fuera del horario laboral, o None si es válido."""
    config = get_or_create_config()
    dow = fecha.weekday()  # 0=Lun … 5=Sáb, 6=Dom

    if dow == 5 and not config.trabaja_sabado:
        return 'El consultorio no trabaja los sábados'
    if dow == 6 and not config.trabaja_domingo:
        return 'El consultorio no trabaja los domingos'

    if dow in (5, 6):
        inicio_lab = _parse_hhmm(config.fin_semana_inicio)
        fin_lab = _parse_hhmm(config.fin_semana_fin)
    else:
        inicio_lab = _parse_hhmm(config.semana_inicio)
        fin_lab = _parse_hhmm(config.semana_fin)

    if hora_inicio < inicio_lab or hora_fin > fin_lab or hora_inicio >= hora_fin:
        if dow in (5, 6):
            return f'Fin de semana: horario permitido {config.fin_semana_inicio} a {config.fin_semana_fin}'
        return f'Entre semana: horario permitido {config.semana_inicio} a {config.semana_fin}'
    return None


@api_bp.route('/tipos-cita')
@login_required
def get_tipos_cita():
    """Obtener todos los tipos de cita activos"""
    tipos = TipoCita.query.filter_by(activo=True).all()
    return jsonify([{
        'id': t.id,
        'nombre': t.nombre,
        'duracion_minutos': t.duracion_minutos,
        'color': t.color
    } for t in tipos])


@api_bp.route('/configuracion/horario', methods=['GET'])
@login_required
def get_configuracion_horario():
    """Obtener horario laboral configurable"""
    config = get_or_create_config()
    return jsonify({
        'semana_inicio': config.semana_inicio,
        'semana_fin': config.semana_fin,
        'fin_semana_inicio': config.fin_semana_inicio,
        'fin_semana_fin': config.fin_semana_fin,
        'trabaja_sabado': config.trabaja_sabado,
        'trabaja_domingo': config.trabaja_domingo,
    })


@api_bp.route('/configuracion/horario', methods=['PUT'])
@login_required
def update_configuracion_horario():
    """Actualizar horario laboral"""
    data = request.get_json() or {}
    config = get_or_create_config()

    semana_inicio = data.get('semana_inicio', config.semana_inicio)
    semana_fin = data.get('semana_fin', config.semana_fin)
    fin_semana_inicio = data.get('fin_semana_inicio', config.fin_semana_inicio)
    fin_semana_fin = data.get('fin_semana_fin', config.fin_semana_fin)

    try:
        if _parse_hhmm(semana_inicio) >= _parse_hhmm(semana_fin):
            return jsonify({'error': 'Entre semana, la hora inicio debe ser menor que la hora fin'}), 400
        if _parse_hhmm(fin_semana_inicio) >= _parse_hhmm(fin_semana_fin):
            return jsonify({'error': 'Fin de semana, la hora inicio debe ser menor que la hora fin'}), 400
    except ValueError:
        return jsonify({'error': 'Formato de hora inválido. Usa HH:MM'}), 400

    config.semana_inicio = semana_inicio
    config.semana_fin = semana_fin
    config.fin_semana_inicio = fin_semana_inicio
    config.fin_semana_fin = fin_semana_fin
    config.trabaja_sabado = bool(data.get('trabaja_sabado', config.trabaja_sabado))
    config.trabaja_domingo = bool(data.get('trabaja_domingo', config.trabaja_domingo))

    db.session.commit()
    return jsonify({'message': 'Horario actualizado correctamente'})


@api_bp.route('/usuario/cambiar-password', methods=['POST'])
@login_required
def cambiar_password():
    """Cambiar contraseña del usuario autenticado"""
    data = request.get_json() or {}
    actual = (data.get('actual_password') or '').strip()
    nueva = (data.get('nueva_password') or '').strip()

    if not actual or not nueva:
        return jsonify({'error': 'Contraseña actual y nueva son requeridas'}), 400
    if len(nueva) < 6:
        return jsonify({'error': 'La nueva contraseña debe tener al menos 6 caracteres'}), 400
    if not current_user.check_password(actual):
        return jsonify({'error': 'La contraseña actual es incorrecta'}), 400

    user = Usuario.query.get(current_user.id)
    user.set_password(nueva)
    db.session.commit()
    return jsonify({'message': 'Contraseña actualizada correctamente'})


@api_bp.route('/usuario/recovery-key', methods=['POST'])
@login_required
def configurar_recovery_key():
    """Guardar o actualizar clave de recuperación para reset desde login"""
    data = request.get_json() or {}
    recovery_key = (data.get('recovery_key') or '').strip()
    recovery_hint = (data.get('recovery_hint') or '').strip()

    if len(recovery_key) < 4:
        return jsonify({'error': 'La clave de recuperación debe tener al menos 4 caracteres'}), 400

    config = get_or_create_config()
    config.recovery_key_hash = generate_password_hash(recovery_key)
    config.recovery_hint = recovery_hint or None
    db.session.commit()
    return jsonify({'message': 'Clave de recuperación actualizada'})


@api_bp.route('/usuario/recovery-key', methods=['GET'])
@login_required
def obtener_recovery_key_info():
    """Saber si existe clave de recuperación configurada"""
    config = get_or_create_config()
    return jsonify({
        'configured': bool(config.recovery_key_hash),
        'hint': config.recovery_hint or ''
    })


@api_bp.route('/usuario/reset-password', methods=['POST'])
def reset_password_with_recovery_key():
    """Resetear contraseña desde login usando clave de recuperación"""
    data = request.get_json() or {}
    usuario = (data.get('usuario') or '').strip()
    recovery_key = (data.get('recovery_key') or '').strip()
    nueva_password = (data.get('nueva_password') or '').strip()

    if not usuario or not recovery_key or not nueva_password:
        return jsonify({'error': 'Usuario, clave de recuperación y nueva contraseña son requeridos'}), 400
    if len(nueva_password) < 6:
        return jsonify({'error': 'La nueva contraseña debe tener al menos 6 caracteres'}), 400

    user = Usuario.query.filter_by(usuario=usuario).first()
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    config = get_or_create_config()
    if not config.recovery_key_hash:
        return jsonify({'error': 'No hay clave de recuperación configurada. Configúrala dentro de la app.'}), 400
    if not check_password_hash(config.recovery_key_hash, recovery_key):
        return jsonify({'error': 'La clave de recuperación es incorrecta'}), 400

    user.set_password(nueva_password)
    db.session.commit()
    return jsonify({'message': 'Contraseña restablecida correctamente. Ya puedes iniciar sesión.'})


@api_bp.route('/citas/mes/<int:year>/<int:month>')
@login_required
def get_citas_mes(year, month):
    """Obtener citas de un mes específico"""
    # Primer y último día del mes
    primer_dia = datetime(year, month, 1).date()
    ultimo_dia = datetime(year, month, calendar.monthrange(year, month)[1]).date()
    
    citas = Cita.query.filter(
        Cita.fecha >= primer_dia,
        Cita.fecha <= ultimo_dia,
        Cita.estado != 'cancelada'
    ).all()
    
    # Agrupar citas por día
    citas_por_dia = {}
    for cita in citas:
        dia = cita.fecha.day
        if dia not in citas_por_dia:
            citas_por_dia[dia] = []
        citas_por_dia[dia].append({
            'id': cita.id,
            'paciente': cita.paciente.nombre_completo,
            'tipo': cita.tipo_cita.nombre,
            'hora': cita.hora_inicio.strftime('%I:%M %p'),
            'estado': cita.estado,
            'color': cita.tipo_cita.color
        })
    
    return jsonify(citas_por_dia)


@api_bp.route('/citas/dia/<fecha>')
@login_required
def get_citas_dia(fecha):
    """Obtener citas de un día específico"""
    try:
        fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Formato de fecha inválido'}), 400
    
    citas = Cita.query.filter(
        Cita.fecha == fecha_obj,
        Cita.estado != 'cancelada'
    ).order_by(Cita.hora_inicio).all()
    
    return jsonify([{
        'id': cita.id,
        'paciente_id': cita.paciente_id,
        'paciente_nombre': cita.paciente.nombre,
        'paciente_apellidos': cita.paciente.apellidos,
        'paciente_completo': cita.paciente.nombre_completo,
        'telefono': cita.paciente.telefono,
        'tipo_id': cita.tipo_cita_id,
        'tipo': cita.tipo_cita.nombre,
        'fecha': cita.fecha.strftime('%Y-%m-%d'),
        'hora_inicio': cita.hora_inicio.strftime('%H:%M'),
        'hora_fin': cita.hora_fin.strftime('%H:%M'),
        'hora_formateada': cita.hora_inicio.strftime('%I:%M %p'),
        'estado': cita.estado,
        'confirmada': cita.confirmada_whatsapp,
        'color': cita.tipo_cita.color,
        'notas': cita.notas
    } for cita in citas])


@api_bp.route('/citas/todas')
@login_required
def get_todas_citas():
    """Obtener todas las citas con filtros opcionales"""
    # Parámetros de filtro
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    estado = request.args.get('estado')
    
    query = Cita.query.filter(Cita.estado != 'cancelada')
    
    if fecha_inicio:
        query = query.filter(Cita.fecha >= datetime.strptime(fecha_inicio, '%Y-%m-%d').date())
    if fecha_fin:
        query = query.filter(Cita.fecha <= datetime.strptime(fecha_fin, '%Y-%m-%d').date())
    if estado:
        query = query.filter(Cita.estado == estado)
    
    citas = query.order_by(Cita.fecha.desc(), Cita.hora_inicio).all()
    
    return jsonify([{
        'id': cita.id,
        'paciente_id': cita.paciente_id,
        'paciente_nombre': cita.paciente.nombre_completo,
        'telefono': cita.paciente.telefono,
        'tipo': cita.tipo_cita.nombre,
        'fecha': cita.fecha.strftime('%Y-%m-%d'),
        'fecha_formateada': cita.fecha.strftime('%d/%m/%Y'),
        'hora_inicio': cita.hora_inicio.strftime('%H:%M'),
        'hora_formateada': cita.hora_inicio.strftime('%I:%M %p'),
        'estado': cita.estado,
        'confirmada': cita.confirmada_whatsapp,
        'color': cita.tipo_cita.color
    } for cita in citas])


@api_bp.route('/citas', methods=['POST'])
@login_required
def crear_cita():
    """Crear una nueva cita"""
    data = request.get_json()
    
    # Validar datos requeridos
    required = ['nombre', 'apellidos', 'telefono', 'tipo_cita_id', 'fecha', 'hora', 'hora_fin']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'El campo {field} es requerido'}), 400
    
    try:
        fecha = datetime.strptime(data['fecha'], '%Y-%m-%d').date()
        hora_inicio = datetime.strptime(data['hora'], '%H:%M').time()
        hora_fin = datetime.strptime(data['hora_fin'], '%H:%M').time()
        
        tipo_cita = TipoCita.query.get(data['tipo_cita_id'])
        if not tipo_cita:
            return jsonify({'error': 'Tipo de cita no válido'}), 400
        
        # Validar horario laboral
        error_horario = validar_horario_laboral(fecha, hora_inicio, hora_fin)
        if error_horario:
            return jsonify({'error': error_horario}), 400
        
        # Verificar conflictos de horario
        if Cita.hay_conflicto(fecha, hora_inicio, hora_fin):
            return jsonify({'error': 'Ya existe una cita en ese horario'}), 409
        
        # Buscar o crear paciente
        paciente = Paciente.query.filter_by(telefono=data['telefono']).first()
        if not paciente:
            paciente = Paciente(
                nombre=data['nombre'],
                apellidos=data['apellidos'],
                telefono=data['telefono']
            )
            db.session.add(paciente)
            db.session.flush()
        else:
            # Actualizar datos del paciente si es necesario
            paciente.nombre = data['nombre']
            paciente.apellidos = data['apellidos']
        
        # Crear cita
        cita = Cita(
            paciente_id=paciente.id,
            tipo_cita_id=data['tipo_cita_id'],
            fecha=fecha,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            notas=data.get('notas', '')
        )
        db.session.add(cita)
        db.session.commit()
        
        fecha_fmt = cita.fecha.strftime('%d/%m/%Y')
        hora_fmt = cita.hora_inicio.strftime('%I:%M %p')
        msg_wa = (f"Estimado/a {paciente.nombre_completo}, le confirmamos su cita en el "
                  f"Consultorio Dental Castillo el {fecha_fmt} a las {hora_fmt} "
                  f"({tipo_cita.nombre}). \u00a1Le esperamos! \U0001f9b7")
        wa_link = f"https://wa.me/52{paciente.telefono}?text={quote(msg_wa)}"
        return jsonify({
            'message': 'Cita creada exitosamente',
            'id': cita.id,
            'whatsapp_link': wa_link
        }), 201
        
    except ValueError as e:
        return jsonify({'error': f'Error en formato de datos: {str(e)}'}), 400


@api_bp.route('/citas/<int:cita_id>', methods=['GET'])
@login_required
def get_cita(cita_id):
    """Obtener una cita específica"""
    cita = Cita.query.get_or_404(cita_id)
    return jsonify({
        'id': cita.id,
        'paciente_id': cita.paciente_id,
        'nombre': cita.paciente.nombre,
        'apellidos': cita.paciente.apellidos,
        'telefono': cita.paciente.telefono,
        'tipo_cita_id': cita.tipo_cita_id,
        'tipo': cita.tipo_cita.nombre,
        'fecha': cita.fecha.strftime('%Y-%m-%d'),
        'hora_inicio': cita.hora_inicio.strftime('%H:%M'),
        'hora_fin': cita.hora_fin.strftime('%H:%M'),
        'estado': cita.estado,
        'confirmada': cita.confirmada_whatsapp,
        'notas': cita.notas
    })


@api_bp.route('/citas/<int:cita_id>', methods=['PUT'])
@login_required
def editar_cita(cita_id):
    """Editar una cita existente"""
    cita = Cita.query.get_or_404(cita_id)
    data = request.get_json()
    
    try:
        # Si se cambia fecha u hora, verificar conflictos
        if 'fecha' in data or 'hora' in data or 'hora_fin' in data:
            fecha = datetime.strptime(data.get('fecha', cita.fecha.strftime('%Y-%m-%d')), '%Y-%m-%d').date()
            hora_inicio = datetime.strptime(data.get('hora', cita.hora_inicio.strftime('%H:%M')), '%H:%M').time()
            hora_fin = datetime.strptime(data.get('hora_fin', cita.hora_fin.strftime('%H:%M')), '%H:%M').time()
            
            error_horario = validar_horario_laboral(fecha, hora_inicio, hora_fin)
            if error_horario:
                return jsonify({'error': error_horario}), 400
            
            if Cita.hay_conflicto(fecha, hora_inicio, hora_fin, excluir_id=cita.id):
                return jsonify({'error': 'Ya existe una cita en ese horario'}), 409
            
            cita.fecha = fecha
            cita.hora_inicio = hora_inicio
            cita.hora_fin = hora_fin
        
        # Actualizar otros campos
        if 'tipo_cita_id' in data:
            cita.tipo_cita_id = data['tipo_cita_id']
        if 'estado' in data:
            cita.estado = data['estado']
        if 'notas' in data:
            cita.notas = data['notas']
        
        # Actualizar datos del paciente si se proporcionan
        if any(k in data for k in ['nombre', 'apellidos', 'telefono']):
            if 'nombre' in data:
                cita.paciente.nombre = data['nombre']
            if 'apellidos' in data:
                cita.paciente.apellidos = data['apellidos']
            if 'telefono' in data:
                cita.paciente.telefono = data['telefono']
        
        db.session.commit()
        
        return jsonify({'message': 'Cita actualizada exitosamente'})
        
    except ValueError as e:
        return jsonify({'error': f'Error en formato de datos: {str(e)}'}), 400


@api_bp.route('/citas/<int:cita_id>/confirmar', methods=['POST'])
@login_required
def confirmar_cita(cita_id):
    """Marcar cita como confirmada vía WhatsApp"""
    cita = Cita.query.get_or_404(cita_id)
    cita.confirmada_whatsapp = True
    cita.estado = 'confirmada'
    db.session.commit()
    return jsonify({'message': 'Cita confirmada'})


@api_bp.route('/citas/<int:cita_id>/cancelar', methods=['POST'])
@login_required
def cancelar_cita(cita_id):
    """Cancelar una cita"""
    cita = Cita.query.get_or_404(cita_id)
    cita.estado = 'cancelada'
    db.session.commit()
    return jsonify({'message': 'Cita cancelada'})


@api_bp.route('/citas/<int:cita_id>/reagendar', methods=['POST'])
@login_required
def reagendar_cita(cita_id):
    """Reagendar una cita (solo cambia fecha y hora)"""
    cita = Cita.query.get_or_404(cita_id)
    data = request.get_json()
    
    if not data.get('fecha') or not data.get('hora'):
        return jsonify({'error': 'Fecha y hora son requeridos'}), 400
    
    try:
        fecha = datetime.strptime(data['fecha'], '%Y-%m-%d').date()
        hora_inicio = datetime.strptime(data['hora'], '%H:%M').time()
        
        hora_inicio_dt = datetime.combine(fecha, hora_inicio)
        hora_fin_dt = hora_inicio_dt + timedelta(minutes=cita.tipo_cita.duracion_minutos)
        hora_fin = hora_fin_dt.time()

        error_horario = validar_horario_laboral(fecha, hora_inicio, hora_fin)
        if error_horario:
            return jsonify({'error': error_horario}), 400
        
        if Cita.hay_conflicto(fecha, hora_inicio, hora_fin, excluir_id=cita.id):
            return jsonify({'error': 'Ya existe una cita en ese horario'}), 409
        
        cita.fecha = fecha
        cita.hora_inicio = hora_inicio
        cita.hora_fin = hora_fin
        cita.estado = 'reagendada'
        cita.confirmada_whatsapp = False
        
        db.session.commit()
        
        # Generar link de WhatsApp con la nueva fecha
        mensaje = f"Hola {cita.paciente.nombre}, su cita ha sido reagendada para el {cita.fecha.strftime('%d/%m/%Y')} a las {cita.hora_inicio.strftime('%I:%M %p')}. Consultorio Dental Castillo."
        whatsapp_link = f"https://wa.me/52{cita.paciente.telefono}?text={mensaje.replace(' ', '%20')}"
        
        return jsonify({
            'message': 'Cita reagendada exitosamente',
            'whatsapp_link': whatsapp_link
        })
        
    except ValueError as e:
        return jsonify({'error': f'Error en formato de datos: {str(e)}'}), 400


@api_bp.route('/citas/<int:cita_id>/whatsapp')
@login_required
def get_whatsapp_link(cita_id):
    """Generar link de WhatsApp para confirmar cita"""
    cita = Cita.query.get_or_404(cita_id)
    
    mensaje = f"Hola {cita.paciente.nombre}, le recordamos su cita el {cita.fecha.strftime('%d/%m/%Y')} a las {cita.hora_inicio.strftime('%I:%M %p')}. ¿Confirma su asistencia? Consultorio Dental Castillo."
    whatsapp_link = f"https://wa.me/52{cita.paciente.telefono}?text={mensaje.replace(' ', '%20')}"
    
    return jsonify({'whatsapp_link': whatsapp_link})


@api_bp.route('/tipos-cita/<int:tipo_id>', methods=['PUT'])
@login_required
def update_tipo_cita(tipo_id):
    """Actualizar duración o nombre de un tipo de cita"""
    tipo = TipoCita.query.get_or_404(tipo_id)
    data = request.get_json()
    if 'duracion_minutos' in data:
        dur = int(data['duracion_minutos'])
        if dur < 5 or dur > 300:
            return jsonify({'error': 'La duración debe estar entre 5 y 300 minutos'}), 400
        tipo.duracion_minutos = dur
    if 'nombre' in data and data['nombre'].strip():
        tipo.nombre = data['nombre'].strip()
    db.session.commit()
    return jsonify({'message': 'Actualizado', 'id': tipo.id, 'duracion_minutos': tipo.duracion_minutos})


@api_bp.route('/tipos-cita', methods=['POST'])
@login_required
def crear_tipo_cita():
    """Crear un nuevo tipo de cita personalizado"""
    data = request.get_json()
    nombre = (data.get('nombre') or '').strip()
    if not nombre:
        return jsonify({'error': 'El nombre es requerido'}), 400
    duracion = int(data.get('duracion_minutos', 30))
    activo = bool(data.get('activo', True))
    existente = TipoCita.query.filter_by(nombre=nombre).first()
    if existente:
        existente.duracion_minutos = max(5, min(300, duracion))
        existente.activo = activo if data.get('activo') is not None else existente.activo
        db.session.commit()
        return jsonify({'id': existente.id, 'nombre': existente.nombre, 'duracion_minutos': existente.duracion_minutos}), 200

    tipo = TipoCita(
        nombre=nombre,
        duracion_minutos=max(5, min(300, duracion)),
        activo=activo
    )
    db.session.add(tipo)
    db.session.commit()
    return jsonify({'id': tipo.id, 'nombre': tipo.nombre, 'duracion_minutos': tipo.duracion_minutos}), 201
