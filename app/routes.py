# app/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
import sqlite3
import os 
from .db_manager import (
    get_full_plate_info, 
    get_all_plates_association, 
    update_acceso_estado, 
    register_new_alert,
    register_employee_vehicle,
    get_all_alerts, 
    get_alerts_by_placa,
    count_alerts_for_association,
    get_employee_details_by_association 
) 
from .sms_service import send_alert_sms 
from .lpr_service import recognize_plate_from_image 

main = Blueprint('main', __name__)

# --- RUTAS DE NAVEGACIÓN ---

@main.route('/')
def index():
    return redirect(url_for('main.operador_consulta'))

# ----------------------------------------------------
#  MÓDULO DE OPERADOR (Consulta y Alerta)
# ----------------------------------------------------

@main.route('/operador', methods=['GET'])
def operador_consulta():
    return render_template('operador.html', data=None, error=None)

@main.route('/operador/buscar', methods=['POST'])
def operador_buscar():
    """Procesa la placa ingresada (texto) o subida (cámara LPR)."""
    placa = None
    
    # --- PROCESAR ENTRADA DE TEXTO (Manual) ---
    placa_manual = request.form.get('placa_input')
    if placa_manual:
        placa = placa_manual
    
    # --- PROCESAR SUBIDA DE ARCHIVO (LPR) ---
    elif 'placa_file' in request.files:
        uploaded_file = request.files['placa_file']
        
        if uploaded_file.filename != '':
            # Guardar el archivo temporalmente
            if not os.path.exists('static'):
                os.makedirs('static')
                
            file_path = os.path.join('static', uploaded_file.filename)
            uploaded_file.save(file_path)
            
            # 2 Llama al LPR
            placa_reconocida, status_msg = recognize_plate_from_image(file_path)
            
            #  Limpiar archivo temporal
            os.remove(file_path) 
            
            if placa_reconocida:
                placa = placa_reconocida
                flash(f"Placa reconocida como '{placa}'.")
            else:
                return render_template('operador.html', data=None, error=f" Error LPR/OCR: {status_msg}. Intente de nuevo.")

    #  --- REALIZAR BÚSQUEDA ---
    if not placa:
        return render_template('operador.html', data=None, error="Ingrese texto o suba una imagen válida.")

    info = get_full_plate_info(placa)
    
    if not info:
        return render_template('operador.html', data=None, error=f"Placa '{placa.upper()}' NO ENCONTRADA en el sistema.")
    
    return render_template('operador.html', data=info, error=None)


@main.route('/operador/alertar', methods=['POST'])
def operador_alertar():
    """Registra una nueva alerta/sanción, activa auto-bloqueo y envía SMS."""
    placa = request.form.get('placa_reg')
    asociacion_id = request.form.get('asociacion_id') 
    tipo_alerta = request.form.get('tipo_alerta')
    comentario = request.form.get('comentario')
    operador = "OPERADOR_DESCONOCIDO" 
    
    if not placa or not tipo_alerta or not asociacion_id:
        flash("Error: Faltan datos para registrar la alerta.")
        return redirect(url_for('main.operador_consulta'))

    success = register_new_alert(asociacion_id, placa, tipo_alerta, comentario, operador)
    
    auto_block_message = "" 
    
    if success:
        # 2. Lógica de Auto-Bloqueo (a partir de 3 alertas)
        alert_count = count_alerts_for_association(asociacion_id)
        
        if alert_count >= 3:
            update_acceso_estado(asociacion_id, 'BLOQUEADO')
            auto_block_message = f" ¡ACCESO BLOQUEADO AUTOMÁTICAMENTE! (Total: {alert_count} alertas)."

        # 3. Enviar SMS
        info = get_full_plate_info(placa) 
        if info and info['telefono']: 
            sms_success, sms_message = send_alert_sms(
                recipient_phone=info['telefono'], 
                placa=placa, 
                tipo_alerta=tipo_alerta, 
                comentario=comentario
            )
            flash_message = f"Alerta registrada. Notificación enviada: {sms_message} {auto_block_message}"
        else:
            flash_message = f"Alerta registrada. No se pudo enviar SMS. {auto_block_message}"
    else:
        flash_message = f" Error al intentar registrar la alerta para {placa.upper()}."

    flash(flash_message)
    return redirect(url_for('main.operador_consulta'))


# ----------------------------------------------------
# ADMINISTRADOR 
# ----------------------------------------------------

@main.route('/admin')
def admin_dashboard():
    return redirect(url_for('main.admin_buscar_placa')) 

@main.route('/admin/buscar', methods=['GET', 'POST'])
def admin_buscar_placa():
    if request.method == 'POST':
        placa = request.form.get('placa_input')
        info = get_full_plate_info(placa)
        alerts = None
        
        if info:
            alerts = get_alerts_by_placa(placa)
            
        return render_template('admin_consulta.html', info=info, alerts=alerts, error=None)
    
    else:
        all_plates = get_all_plates_association()
        return render_template('admin_dashboard_bloqueo.html', plates=all_plates) 

@main.route('/admin/toggle_access/<int:asociacion_id>', methods=['POST'])
def admin_toggle_access(asociacion_id):
    """Cambia el estado de acceso (Bloqueo/Activación) y envía SMS."""
    current_status = request.form.get('current_status')
    placa = request.form.get('placa_asociada')
    
    sms_notification_msg = "" 
    
    if current_status == 'ACTIVO':
        new_status = 'BLOQUEADO'
        message = f'Placa {placa} ha sido BLOQUEADA'
        alert_type_msg = "ACCESO BLOQUEADO"
        comment_msg = "Acceso bloqueado manualmente por un administrador."
    else:
        new_status = 'ACTIVO'
        message = f'Placa {placa} ha sido ACTIVADA'
        alert_type_msg = "ACCESO REACTIVADO"
        comment_msg = "Acceso reactivado manualmente por un administrador."

    update_acceso_estado(asociacion_id, new_status) 

    try:
        employee_info = get_employee_details_by_association(asociacion_id)
        if employee_info and employee_info['telefono']:
            sms_success, sms_message = send_alert_sms(
                recipient_phone=employee_info['telefono'],
                placa=placa,
                tipo_alerta=alert_type_msg,
                comentario=comment_msg
            )
            sms_notification_msg = f" Notificación SMS: {sms_message}"
        else:
            sms_notification_msg = " (No se pudo notificar por SMS: teléfono no encontrado.)"
    except Exception as e:
        print(f"Error al intentar enviar SMS de bloqueo: {e}")
        sms_notification_msg = " (Error al procesar envío de SMS.)"

    flash(message + sms_notification_msg)
    return redirect(url_for('main.admin_buscar_placa')) 

# --- RUTAS DE REGISTRO ---

@main.route('/admin/registro', methods=['GET'])
def admin_register():
    return render_template('admin_registro.html')

@main.route('/admin/registro', methods=['POST'])
def admin_register_submit():
    """Procesa el formulario y registra Empleado/Vehículo."""
    
    empleado_data = {
        'nombre': request.form.get('nombre'),
        'apellido': request.form.get('apellido'),
        'puesto': request.form.get('puesto'),
        'telefono': request.form.get('telefono')
    }
    vehiculo_data = {
        'placa': request.form.get('placa'),
        'marca': request.form.get('marca'),
        'modelo': request.form.get('modelo'),
        'color': request.form.get('color')
    }
    
    success, message = register_employee_vehicle(empleado_data, vehiculo_data)
    
    if success:
        flash(f"Registro exitoso {message}")
        return redirect(url_for('main.admin_buscar_placa'))
    else:
        flash(f" Error en el registro: {message}")
        return render_template('admin_registro.html') 

# --- RUTA DE HISTORIAL DE ALERTAS ---

@main.route('/admin/alertas', methods=['GET'])
def admin_alerts():
    """Muestra el listado completo de alertas (con filtro)."""
    
    search_query = request.args.get('q') 
    
    if search_query:
        all_alerts = get_all_alerts(search_query)
        message = f"Resultados para: '{search_query}'"
    else:
        all_alerts = get_all_alerts()
        message = "Historial Completo"
        
    return render_template('admin_alertas.html', alerts=all_alerts, search_query=search_query, message=message)