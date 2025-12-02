# app/__init__.py
from flask import Flask # Importa la clase principal Flask para crear la aplicación
import os # Importa el módulo 'os' para interactuar con el sistema operativo (rutas de archivos)

# Calcula la ruta absoluta al directorio 'templates'
# Esto asegura que Flask siempre encuentre las plantillas sin importar desde dónde se ejecute el script.
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))

def create_app():
    #Indica a Flask dónde buscar archivos estáticos, plantillas, etc.
    # template_folder: Especifica la ruta al directorio de plantillas 
    app = Flask(__name__, template_folder=template_dir)
    
    # Esta clave es  para la seguridad, ya que se usa para firmar cookies de sesión y proteger contra ataques 
    app.config['SECRET_KEY'] = 'una_clave_secreta_muy_larga_y_segura_para_flask' 

    # Importa el plano que contiene las rutas de tu aplicación.
    from .routes import main as main_blueprint
    
    # Esto hace que todas las rutas definidas sean accesibles en la aplicación.
    app.register_blueprint(main_blueprint)

    # Retorna el objeto de la aplicación Flask ya configurado
    return app