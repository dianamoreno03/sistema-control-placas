# app/db_manager.py
import sqlite3

DB_NAME = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.execute('PRAGMA foreign_keys = ON') 
    conn.row_factory = sqlite3.Row
    return conn

# ----------------------------------------------------------------------
# FUNCIONES DE CREACIÓN DE BASE DE DATOS 
# ----------------------------------------------------------------------

def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Tabla EMPLEADOS (CON TELEFONO)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS EMPLEADOS (
            id_empleado INTEGER PRIMARY KEY AUTOINCREMENT, 
            nombre TEXT NOT NULL,
            apellido TEXT NOT NULL,
            puesto TEXT,
            sexo TEXT,
            foto_url TEXT,
            telefono TEXT UNIQUE,
            activo BOOLEAN DEFAULT 1 
        )
    """)
    
    # 2. Tabla VEHICULOS 
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS VEHICULOS (
            id_vehiculo INTEGER PRIMARY KEY AUTOINCREMENT,
            placa TEXT UNIQUE NOT NULL,
            marca TEXT,
            modelo TEXT,
            anio INTEGER,
            color TEXT,
            puertas INTEGER
        )
    """)
    
    # 3. Tabla EMPLEADO_VEHICULO_ASOCIACION
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS EMPLEADO_VEHICULO_ASOCIACION (
            id_asociacion INTEGER PRIMARY KEY AUTOINCREMENT,
            fk_empleado INTEGER NOT NULL,
            fk_vehiculo INTEGER NOT NULL,
            estado_acceso TEXT NOT NULL, 
            fecha_registro TEXT,
            FOREIGN KEY (fk_empleado) REFERENCES EMPLEADOS(id_empleado),
            FOREIGN KEY (fk_vehiculo) REFERENCES VEHICULOS(id_vehiculo),
            UNIQUE (fk_empleado, fk_vehiculo) 
        )
    """)

    # 4. Tabla para registrar intentos de acceso (LOGS del Sistema Experto)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS intentos_acceso (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            placa TEXT NOT NULL,
            exitoso BOOLEAN NOT NULL,
            alerta TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 5. Tabla para historial de accesos exitosos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accesos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            placa TEXT NOT NULL,
            empleado_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (empleado_id) REFERENCES EMPLEADOS(id_empleado)
        )
    """)
    
    # 6. Tabla ALERTAS_SANCIONES 
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ALERTAS_SANCIONES (
            id_alerta INTEGER PRIMARY KEY AUTOINCREMENT,
            fk_asociacion INTEGER NOT NULL, 
            placa_asociada TEXT NOT NULL, 
            fecha_hora_alerta TEXT,
            tipo_alerta TEXT,
            comentario_operador TEXT,
            operador_registra TEXT,
            FOREIGN KEY (fk_asociacion) REFERENCES EMPLEADO_VEHICULO_ASOCIACION(id_asociacion)
        )
    """)
    
    conn.commit()
    conn.close()

def seed_data():
    """Inserta datos iniciales de prueba (CON TELÉFONO DE PRUEBA)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM EMPLEADOS")
    if cursor.fetchone()[0] == 0:
        
        cursor.execute("INSERT INTO EMPLEADOS (nombre, apellido, puesto, telefono, activo) VALUES (?, ?, ?, ?, 1)", ('Juan', 'Pérez', 'Gerente', '+525512345678')) 
        cursor.execute("INSERT INTO EMPLEADOS (nombre, apellido, puesto, telefono, activo) VALUES (?, ?, ?, ?, 1)", ('María', 'López', 'Operador', '+525587654321')) 

        cursor.execute("INSERT INTO VEHICULOS (placa, marca, modelo, anio, color) VALUES (?, ?, ?, ?, ?)", ('ABC1234', 'Nissan', 'Versa', 2020, 'Gris'))
        cursor.execute("INSERT INTO VEHICULOS (placa, marca, modelo, anio, color) VALUES (?, ?, ?, ?, ?)", ('XYZ5678', 'Honda', 'CRV', 2018, 'Rojo'))
        cursor.execute("INSERT INTO VEHICULOS (placa, marca, modelo, anio, color) VALUES (?, ?, ?, ?, ?)", ('QWE9012', 'Mazda', '3', 2023, 'Negro')) 
        
        conn.execute("INSERT INTO EMPLEADO_VEHICULO_ASOCIACION (fk_empleado, fk_vehiculo, estado_acceso, fecha_registro) VALUES (?, ?, ?, DATETIME('now'))", (1, 1, 'ACTIVO')) 
        conn.execute("INSERT INTO EMPLEADO_VEHICULO_ASOCIACION (fk_empleado, fk_vehiculo, estado_acceso, fecha_registro) VALUES (?, ?, ?, DATETIME('now'))", (2, 2, 'ACTIVO')) 
        conn.execute("INSERT INTO EMPLEADO_VEHICULO_ASOCIACION (fk_empleado, fk_vehiculo, estado_acceso, fecha_registro) VALUES (?, ?, ?, DATETIME('now'))", (1, 3, 'ACTIVO')) 

        conn.commit()
    conn.close()

# --- FUNCIONES CRUD ---

def get_all_plates_association():
    conn = get_db_connection()
    plates = conn.execute("""
        SELECT 
            T1.id_asociacion, T3.placa, T1.estado_acceso, T2.nombre, T2.apellido
        FROM EMPLEADO_VEHICULO_ASOCIACION AS T1
        JOIN EMPLEADOS AS T2 ON T1.fk_empleado = T2.id_empleado
        JOIN VEHICULOS AS T3 ON T1.fk_vehiculo = T3.id_vehiculo
    """).fetchall()
    conn.close()
    return [dict(row) for row in plates]

def update_acceso_estado(asociacion_id, nuevo_estado):
    conn = get_db_connection()
    try:
        conn.execute("""
            UPDATE EMPLEADO_VEHICULO_ASOCIACION
            SET estado_acceso = ?
            WHERE id_asociacion = ?
        """, (nuevo_estado.upper(), asociacion_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error al actualizar estado: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_full_plate_info(placa):
    conn = get_db_connection()
    cursor = conn.execute("""
        SELECT 
            T1.id_asociacion, T1.estado_acceso,
            T2.nombre, T2.apellido, T2.puesto, T2.telefono, T2.foto_url,
            T3.placa, T3.marca, T3.modelo, T3.anio, T3.color
        FROM EMPLEADO_VEHICULO_ASOCIACION AS T1
        JOIN EMPLEADOS AS T2 ON T1.fk_empleado = T2.id_empleado
        JOIN VEHICULOS AS T3 ON T1.fk_vehiculo = T3.id_vehiculo
        WHERE T3.placa = ?
    """, (placa.upper(),)).fetchone()
    conn.close()
    return dict(cursor) if cursor else None 

def register_new_alert(asociacion_id, placa, tipo, comentario, operador):
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO ALERTAS_SANCIONES 
            (fk_asociacion, placa_asociada, fecha_hora_alerta, tipo_alerta, comentario_operador, operador_registra)
            VALUES (?, ?, DATETIME('now'), ?, ?, ?)
        """, (asociacion_id, placa.upper(), tipo, comentario, operador))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error al registrar alerta para {placa}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_alerts_by_placa(placa):
    conn = get_db_connection()
    alerts = conn.execute("""
        SELECT 
            T1.fecha_hora_alerta, T1.tipo_alerta, T1.comentario_operador, T1.operador_registra,
            T4.nombre, T4.apellido
        FROM ALERTAS_SANCIONES AS T1
        JOIN EMPLEADO_VEHICULO_ASOCIACION AS T2 ON T1.fk_asociacion = T2.id_asociacion
        JOIN VEHICULOS AS T3 ON T2.fk_vehiculo = T3.id_vehiculo
        JOIN EMPLEADOS AS T4 ON T2.fk_empleado = T4.id_empleado
        WHERE T3.placa = ?
        ORDER BY T1.fecha_hora_alerta DESC
    """, (placa.upper(),)).fetchall()
    conn.close()
    return [dict(row) for row in alerts]

def get_all_alerts(query=None):
    conn = get_db_connection()
    sql = """
        SELECT 
            T1.id_alerta, T1.placa_asociada, T1.fecha_hora_alerta, T1.tipo_alerta, 
            T1.comentario_operador, T1.operador_registra,
            T4.nombre, T4.apellido, T4.telefono, T3.marca, T3.modelo, T4.puesto
        FROM ALERTAS_SANCIONES AS T1
        JOIN EMPLEADO_VEHICULO_ASOCIACION AS T2 ON T1.fk_asociacion = T2.id_asociacion
        JOIN VEHICULOS AS T3 ON T2.fk_vehiculo = T3.id_vehiculo
        JOIN EMPLEADOS AS T4 ON T2.fk_empleado = T4.id_empleado
    """
    params = []
    if query:
        sql += """
            WHERE T1.placa_asociada LIKE ? OR T4.nombre LIKE ? OR T4.apellido LIKE ?
        """
        search_term = f'%{query}%'
        params = [search_term, search_term, search_term]
    sql += " ORDER BY T1.fecha_hora_alerta DESC"
    alerts = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(row) for row in alerts]


def get_employee_id_by_phone(telefono):
    conn = get_db_connection()
    employee = conn.execute('SELECT id_empleado FROM EMPLEADOS WHERE telefono = ?', (telefono,)).fetchone()
    conn.close()
    return employee['id_empleado'] if employee else None

def get_vehicle_id_by_placa(placa):
    conn = get_db_connection()
    vehicle = conn.execute('SELECT id_vehiculo FROM VEHICULOS WHERE placa = ?', (placa,)).fetchone()
    conn.close()
    return vehicle['id_vehiculo'] if vehicle else None

def register_employee_vehicle(employee_data, vehicle_data):
    conn = get_db_connection()
    placa = vehicle_data['placa'].upper()
    try:
        fk_empleado = get_employee_id_by_phone(employee_data['telefono']) 
        if fk_empleado is None:
            cursor = conn.execute("""
                INSERT INTO EMPLEADOS (nombre, apellido, puesto, telefono) 
                VALUES (?, ?, ?, ?)
            """, (employee_data['nombre'], employee_data['apellido'], employee_data['puesto'], employee_data['telefono']))
            fk_empleado = cursor.lastrowid
            msg_empleado = f"Nuevo Empleado ({fk_empleado}) registrado."
        else:
            msg_empleado = f"Empleado ({fk_empleado}) existente."

        fk_vehiculo = get_vehicle_id_by_placa(placa)
        if fk_vehiculo is None:
            cursor = conn.execute("""
                INSERT INTO VEHICULOS (placa, marca, modelo, color) 
                VALUES (?, ?, ?, ?)
            """, (placa, vehicle_data['marca'], vehicle_data['modelo'], vehicle_data['color']))
            fk_vehiculo = cursor.lastrowid
            msg_vehiculo = f"Nuevo Vehículo ({placa}) registrado."
        else:
            msg_vehiculo = f"Vehículo ({placa}) existente."

        conn.execute("""
            INSERT INTO EMPLEADO_VEHICULO_ASOCIACION (fk_empleado, fk_vehiculo, estado_acceso, fecha_registro) 
            VALUES (?, ?, 'ACTIVO', DATETIME('now'))
        """, (fk_empleado, fk_vehiculo))
        
        conn.commit()
        return True, f"{msg_empleado}. {msg_vehiculo}. Asociación creada."
    except sqlite3.IntegrityError:
        conn.rollback()
        return False, f"La Placa {placa} ya está asociada con el empleado {employee_data['nombre']} {employee_data['apellido']}."
    except sqlite3.Error as e:
        conn.rollback()
        return False, f"Error de Base de Datos: {e}"
    finally:
        conn.close()

def count_alerts_for_association(asociacion_id):
    conn = get_db_connection()
    cursor = conn.execute(
        "SELECT COUNT(*) FROM ALERTAS_SANCIONES WHERE fk_asociacion = ?",
        (asociacion_id,)
    )
    count = cursor.fetchone()[0] 
    conn.close()
    return count

def get_employee_details_by_association(asociacion_id):
    conn = get_db_connection()
    info = conn.execute("""
        SELECT T2.telefono, T2.nombre 
        FROM EMPLEADO_VEHICULO_ASOCIACION AS T1
        JOIN EMPLEADOS AS T2 ON T1.fk_empleado = T2.id_empleado
        WHERE T1.id_asociacion = ?
    """, (asociacion_id,)).fetchone()
    conn.close()
    return dict(info) if info else None