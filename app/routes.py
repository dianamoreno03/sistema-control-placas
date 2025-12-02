from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify # <-- jsonify para LPR
import sqlite3 
import os # Para manejo de archivos y rutas
import base64 # Para decodificar la imagen capturada por la cámara 
from datetime import datetime # Para generar marcas de tiempo para archivos temporales
from .db_manager import (
    get_full_plate_info, # Obtiene todos los detalles de una placa y su asociado
    get_all_plates_association, # Obtiene listado de todas las placas con info básica de asociación
    update_acceso_estado, # Cambia el estado de acceso (ACTIVO/BLOQUEADO)
    register_new_alert, # Registra una nueva alerta/sanción
    register_employee_vehicle, # Registra un nuevo empleado y vehículo asociado
    get_all_alerts, # Obtiene el historial de alertas
    get_alerts_by_placa, # Obtiene alertas específicas por placa
    count_alerts_for_association, # Cuenta las alertas para una asociación específica
    get_employee_details_by_association # Obtiene detalles del empleado por ID de asociación
) 
from .sms_service import send_alert_sms # Servicio para enviar notificaciones SMS
from .lpr_service import recognize_plate_from_image # Sistema Experto de Reconocimiento de Placas

# Crea un plano para organizar las rutas de la aplicación
main = Blueprint('main', __name__)

# --- RUTAS DE NAVEGACIÓN ---

@main.route('/')
def index():
    """Ruta de inicio. Redirige al módulo principal del operador."""
    return redirect(url_for('main.operador_consulta'))

# ----------------------------------------------------
#  MÓDULO DE OPERADOR (Consulta y Alerta)
# ----------------------------------------------------

@main.route('/operador', methods=['GET'])
def operador_consulta():
    """Página inicial del operador. Muestra el formulario de búsqueda y la interfaz de cámara/LPR."""
    # 'data=None' indica que la página se carga sin resultados de búsqueda iniciales.
    return render_template('operador.html', data=None, error=None)

@main.route('/operador/buscar', methods=['POST'])
def operador_buscar():
    """
    Procesa la placa ingresada manualmente por el operador.
    Busca la información en la DB y redirige a la página de resultados si tiene éxito.
    """
    placa = request.form.get('placa_input')
    
    if not placa:
        # Si no se ingresó placa, redirige a la consulta inicial
        return redirect(url_for('main.operador_consulta')) 

    # Consulta la DB para obtener toda la información de la placa
    info = get_full_plate_info(placa)
    
    if not info:
        # Si la placa no se encuentra, muestra un mensaje de error (flash)
        flash(f" Placa '{placa.upper()}' NO ENCONTRADA en el sistema.", 'error')
        return redirect(url_for('main.operador_consulta'))
    
    # Éxito: usa la ruta de resultados con los datos cargados
    return redirect(url_for('main.operador_with_data', placa=placa))

@main.route('/operador/alertar', methods=['POST'])
def operador_alertar():
    """
    Registra una nueva alerta/sanción en la DB, activa la lógica de auto-bloqueo 
    y envía una notificación SMS al asociado si es necesario.
    """
    placa = request.form.get('placa_reg')
    asociacion_id = request.form.get('asociacion_id') 
    tipo_alerta = request.form.get('tipo_alerta')
    comentario = request.form.get('comentario')
    operador = "OPERADOR" 
    
    if not placa or not tipo_alerta or not asociacion_id:
        flash("Error: Faltan datos clave para registrar la alerta.")
        return redirect(url_for('main.operador_consulta'))

    # 1. Registrar la alerta en la base de datos
    success = register_new_alert(asociacion_id, placa, tipo_alerta, comentario, operador)
    
    auto_block_message = "" 
    
    if success:
        # 2. Lógica de Auto-Bloqueo
        alert_count = count_alerts_for_association(asociacion_id)
        
        # Si el número de alertas alcanza o supera 3, bloquea el acceso
        if alert_count >= 3:
            update_acceso_estado(asociacion_id, 'BLOQUEADO')
            auto_block_message = f" ¡ACCESO BLOQUEADO AUTOMÁTICAMENTE! (Total: {alert_count} alertas)."

        # 3. Enviar SMS al asociado
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
            flash_message = f" Alerta registrada. No se pudo enviar SMS. {auto_block_message}"
    else:
        flash_message = f"Error al intentar registrar la alerta para {placa.upper()}."

    flash(flash_message)
    # Vuelve a la página de resultados para que el operador vea la placa y el nuevo estado.
    return redirect(url_for('main.operador_with_data', placa=placa))

# --- RUTA DE MANEJO DE IMAGEN  (LPR) ---

@main.route('/operador/capture_and_search', methods=['POST'])
def operador_capture_and_search():
    """
    Ruta  para el proceso de Reconocimiento de Placas 
    1. Recibe imagen  de la cámara.
    2. Guarda temporalmente el archivo.
    3. Llama al servicio LPR.
    4. Limpia el archivo temporal.
    5. Devuelve el resultado (redirección o error) en formato JSON.
    """
    try:
        # 1. Decodificar la imagen Base64
        data = request.get_json()
        # Obtiene la parte de datos puros (después de 'data:image/jpeg;base64,')
        image_data_base64 = data.get('image_data').split(',')[1]
        
        image_bytes = base64.b64decode(image_data_base64)
        
        # 2. Guardar archivo temporalmente
        temp_dir = 'static/temp'
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        file_name = f"placa_{timestamp}.jpg"
        file_path = os.path.join(temp_dir, file_name)
        
        with open(file_path, 'wb') as f:
            f.write(image_bytes)

        # 3. Llamar al Sistema Experto
        placa_reconocida, status_msg = recognize_plate_from_image(file_path)
        
        # 4. Limpiar archivo temporal
        os.remove(file_path) 

        # 5. Procesar resultado
        if placa_reconocida:
            # Éxito: devolver JSON con URL de redirección
            redirect_url = url_for('main.operador_with_data', placa=placa_reconocida)
            flash(f"📸 LPR Exitoso: Placa reconocida como '{placa_reconocida}'.", 'success')
            return jsonify({'success': True, 'redirect_url': redirect_url})
        else:
            # Fallo del LPR: devolver JSON con error
            flash(f"Error: {status_msg}", 'error')
            return jsonify({'success': False, 'message': status_msg})

    except Exception as e:
        flash(f"Error crítico en la captura: {e}", 'error')
        return jsonify({'success': False, 'message': f"Error interno del servidor: {e}"})

@main.route('/operador/with_data/<placa>')
def operador_with_data(placa):
    """
    Muestra el resultado después de una búsqueda exitosa (ya sea manual o por LPR).
    Esta ruta es la de "destino" tras un POST exitoso.
    """
    info = get_full_plate_info(placa)
    
    if not info:
        flash(f"Placa '{placa.upper()}' NO ENCONTRADA después de la búsqueda.")
        return redirect(url_for('main.operador_consulta'))

    # la plantilla del operador pero pasa la información de la placa
    return render_template('operador.html', data=info, error=None)


# ----------------------------------------------------
# MÓDULO DE ADMINISTRADOR
# ----------------------------------------------------

@main.route('/admin')
def admin_dashboard():
    """Ruta inicial del administrador. Redirige a la consulta/bloqueo."""
    return redirect(url_for('main.admin_buscar_placa')) 

@main.route('/admin/buscar', methods=['GET', 'POST'])
def admin_buscar_placa():
    """
    GET: Muestra la lista de todas las placas (para la gestión de bloqueo).
    POST: Procesa la búsqueda manual de una placa y muestra sus detalles y alertas.
    """
    if request.method == 'POST':
        placa = request.form.get('placa_input')
        info = get_full_plate_info(placa)
        alerts = None
        
        if info:
            # Si se encuentra la info, carga también el historial de alertas
            alerts = get_alerts_by_placa(placa)
            
        return render_template('admin_consulta.html', info=info, alerts=alerts, error=None)
    
    else:
        # Carga la lista completa de placas y sus estados
        all_plates = get_all_plates_association()
        return render_template('admin_dashboard_bloqueo.html', plates=all_plates) 

@main.route('/admin/toggle_access/<int:asociacion_id>', methods=['POST'])
def admin_toggle_access(asociacion_id):
    """
    Ruta para que el administrador cambie manualmente el estado de acceso (Bloqueo/Activación) 
    de una asociación y notifique por SMS.
    """
    current_status = request.form.get('current_status')
    placa = request.form.get('placa_asociada')
    
    sms_notification_msg = "" 
    
    # Determina el nuevo estado y los mensajes de alerta
    if current_status == 'ACTIVO':
        new_status = 'BLOQUEADO'
        message = f'Placa {placa} ha sido BLOQUEADA.'
        alert_type_msg = "ACCESO BLOQUEADO"
        comment_msg = "Acceso bloqueado manualmente por un administrador."
    else:
        new_status = 'ACTIVO'
        message = f'Placa {placa} ha sido ACTIVADA.'
        alert_type_msg = "ACCESO REACTIVADO"
        comment_msg = "Acceso reactivado manualmente por un administrador."

    # Actualiza el estado en la DB
    update_acceso_estado(asociacion_id, new_status) 

    # Intenta enviar notificación SMS
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
    """Muestra el formulario para registrar un nuevo Empleado/Vehículo."""
    return render_template('admin_registro.html')

@main.route('/admin/registro', methods=['POST'])
def admin_register_submit():
    """Procesa los datos del formulario de registro y llama al manager de DB."""
    
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
    
    # Intenta registrar
    success, message = register_employee_vehicle(empleado_data, vehiculo_data)
    
    if success:
        flash(f"Registro exitoso! {message}")
        # Redirige a la página de búsqueda/gestión tras el registro
        return redirect(url_for('main.admin_buscar_placa'))
    else:
        flash(f"Error en el registro: {message}")
        # Vuelve a renderizar el formulario si hay error
        return render_template('admin_registro.html') 

# --- RUTA DE HISTORIAL DE ALERTAS ---

@main.route('/admin/alertas', methods=['GET'])
def admin_alerts():
    """
    Muestra el listado completo de alertas, permitiendo la búsqueda por placa 
    u otros campos mediante el parámetro 'q'.
    """
    
    search_query = request.args.get('q') # Obtiene el parámetro de búsqueda
    
    if search_query:
        # Busca alertas que coincidan con el query
        all_alerts = get_all_alerts(search_query)
        message = f"Resultados para: '{search_query}'"
    else:
        # Obtiene todas las alertas
        all_alerts = get_all_alerts()
        message = "Historial Completo"
        
    return render_template('admin_alertas.html', alerts=all_alerts, search_query=search_query, message=message)