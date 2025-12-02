from twilio.rest import Client # Importa la clase principal de Twilio para interactuar con la API
from datetime import datetime # Importa datetime para incluir la fecha actual en el mensaje SMS

# --- CREDENCIALES DE TWILIO ---
# Estas son las credenciales 
TWILIO_ACCOUNT_SID = "ACb8d867a9369f5736f68fc9b57cf2c9dd" 
TWILIO_AUTH_TOKEN = "3b490cf0daf20cb44611d251f12f14a8"           
TWILIO_PHONE_NUMBER = "+12137151738" # Número de teléfono de Twilio utilizado como remitente (de prueba)

# Inicializa el cliente de Twilio
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def send_alert_sms(recipient_phone, placa, tipo_alerta, comentario):
    """
    Función que envía un mensaje SMS de notificación al empleado sobre una alerta o sanción.
    
    :param recipient_phone: Número de teléfono del destinatario.
    :param placa: Placa del vehículo involucrado.
    :param tipo_alerta: Tipo de incidencia (ej. 'Sanción', 'Acceso Bloqueado').
    :param comentario: Detalles adicionales de la alerta.
    :return: (bool success, str message)
    """
    try:
        if not recipient_phone:
            # Si el número no está disponible en la base de datos
            return False, "Error: Número de teléfono del empleado no encontrado."
        
        # Validación para asegurar el formato internacional E.164 (+[código_país][número])
        if not recipient_phone.startswith('+'):
             # Se asume código de país +52 (México) si no se incluye un prefijo '+'
             recipient_phone = f"+52{recipient_phone}" 

        # Estructura del mensaje de alerta
        body_message = f"""
ALERTA ACCESO PLACA {placa}
Incidencia: {tipo_alerta}
Detalles: {comentario}
Fecha: {datetime.now().strftime('%Y-%m-%d')}
A LA TERCERA INFRACCION SE BLOQUEARA EL ACCESO

POR FAVOR NO RESPONDER A ESTE MENSAJE.

"""
        
        # Envía el mensaje usando el cliente de Twilio
        message = client.messages.create(
            to=recipient_phone, # Número del destinatario
            from_=TWILIO_PHONE_NUMBER, # Número remitente de Twilio
            body=body_message # Contenido del mensaje
        )
        
        # Si la llamada a la API tiene éxito, retorna True
        return True, "SMS enviado con éxito."
            
    except Exception as e:
        # Captura cualquier error durante el proceso de envío
        print(f"ERROR EN EL ENVÍO DE SMS a {recipient_phone}: {e}")
        return False, f"Error al enviar el SMS: {e}."