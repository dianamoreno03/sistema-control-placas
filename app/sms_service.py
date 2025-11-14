# app/sms_service.py
from twilio.rest import Client
from datetime import datetime

# --- CREDENCIALES DE TWILIO ---

TWILIO_ACCOUNT_SID = "ACb8d867a9369f5736f68fc9b57cf2c9dd" 
TWILIO_AUTH_TOKEN = "3b490cf0daf20cb44611d251f12f14a8"           
TWILIO_PHONE_NUMBER = "+12137151738" # prueba

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def send_alert_sms(recipient_phone, placa, tipo_alerta, comentario):
    """
    mensaje SMS de notificación al empleado.
    """
    try:
        if not recipient_phone:
            #para que sea valido se tiene que validar en twilio 
            return False, "Error: Número de teléfono del empleado no encontrado."
        
        # esta validada con mexico 
        if not recipient_phone.startswith('+'):
             # se pone solo si no se incluye 
             recipient_phone = f"+52{recipient_phone}" 

        body_message = f"""
🚨 ALERTA ACCESO PLACA {placa}
Incidencia: {tipo_alerta}
Detalles: {comentario}
Fecha: {datetime.now().strftime('%Y-%m-%d')}
"""
        
        message = client.messages.create(
            to=recipient_phone,
            from_=TWILIO_PHONE_NUMBER,
            body=body_message
        )
        
        return True, "SMS enviado con éxito."
            
            #utilizar solo con los validados 
    except Exception as e:
        print(f"ERROR EN EL ENVÍO DE SMS a {recipient_phone}: {e}")
        return False, f"Error al enviar el SMS: {e}."