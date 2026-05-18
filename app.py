from flask import Flask, render_template, request, redirect, url_for
import pyodbc

app = Flask(__name__)

# Configuración de la conexión a SQL Server
def get_db_connection():
    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=localhost;'
        'DATABASE=STB_DB;'
        'Trusted_Connection=yes;'
    )
    return conn

# 1. RUTA PRINCIPAL: Dashboard
@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id_producto, nombre, precio, stock FROM Productos')
    productos = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('index.html', productos=productos)


# 2. RUTA DE INVENTARIO: Ver lista de productos y formularios
@app.route('/inventario')
def inventario():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id_producto, nombre, descripcion, precio, stock FROM Productos')
    productos = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('inventario.html', productos=productos)


# 3. ACCIÓN: Registrar un Producto Nuevo
@app.route('/inventario/agregar', methods=['POST'])
def agregar_producto():
    nombre = request.form['nombre']
    descripcion = request.form['descripcion']
    precio = request.form['precio']
    stock = request.form['stock']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO Productos (nombre, descripcion, precio, stock)
        VALUES (?, ?, ?, ?)
    ''', (nombre, descripcion, precio, stock))
    conn.commit() # Guarda los cambios de forma permanente en SQL Server
    cursor.close()
    conn.close()
    
    return redirect(url_for('inventario')) # Nos regresa a la pantalla de inventario


# 4. ACCIÓN: Actualizar el Stock de un producto existente
@app.route('/inventario/actualizar_stock', methods=['POST'])
def actualizar_stock():
    id_producto = request.form['id_producto']
    nuevo_stock = request.form['stock']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE Productos
        SET stock = ?
        WHERE id_producto = ?
    ''', (nuevo_stock, id_producto))
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('inventario'))

# 5. ACCIÓN: Eliminar un producto del inventario
@app.route('/inventario/eliminar/<int:id_producto>', methods=['POST'])
def eliminar_producto(id_producto):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM Productos WHERE id_producto = ?', (id_producto,))
        conn.commit()
    except pyodbc.Error as e:
        # Si da error por llave foránea (porque ya se vendió), no truena la app
        print(f"No se pudo eliminar el producto debido a restricciones de ventas: {e}")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('inventario'))

if __name__ == '__main__':
    app.run(debug=True)