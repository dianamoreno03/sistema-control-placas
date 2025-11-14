# app/__init__.py
from flask import Flask
import os 

#la ruta templates (mis interfacws)
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))

def create_app():
    app = Flask(__name__, template_folder=template_dir)
    app.config['SECRET_KEY'] = 'una_clave_secreta_muy_larga_y_segura_para_flask' 

    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app