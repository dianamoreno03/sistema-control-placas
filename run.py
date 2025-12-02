# run.py
from app import create_app
from app.db_manager import create_tables, seed_data

# 1. Ejecuta las funciones de DB_MANAGER para crear la BD y datos de prueba
create_tables()
seed_data()

# 2. Inicia la aplicación Flask
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0',port=5000)