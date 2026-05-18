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

# 1. RUTA PRINCIPAL (CLIENTE): Solo ve productos activos (1)
@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id_producto, nombre, precio, stock FROM Productos WHERE activo = 1')
    productos = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('index.html', productos=productos)


# 2. RUTA DE INVENTARIO (ADMIN): Ve TODOS los productos (activos e inactivos)
@app.route('/inventario')
def inventario():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Seleccionamos también la columna 'activo' para usarla en el HTML
    cursor.execute('SELECT id_producto, nombre, descripcion, precio, stock, activo FROM Productos')
    productos = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('inventario.html', productos=productos)


# 3. ACCIÓN: Registrar un Producto Nuevo (Con validación automática de stock cero)
@app.route('/inventario/agregar', methods=['POST'])
def agregar_producto():
    nombre = request.form['nombre']
    descripcion = request.form['descripcion']
    precio = request.form['precio']
    stock = int(request.form['stock']) # Lo convertimos a entero para poder evaluarlo
    
    # Si ingresan un producto nuevo con 0 stock, nace desactivado (0), si no, activo (1)
    activo = 0 if stock <= 0 else 1
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO Productos (nombre, descripcion, precio, stock, activo)
        VALUES (?, ?, ?, ?, ?)
    ''', (nombre, descripcion, precio, stock, activo)) # Añadimos 'activo' explícitamente aquí
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('inventario'))


# 4. ACCIÓN: Actualizar el Stock (Con desactivación automática si llega a 0)
@app.route('/inventario/actualizar_stock', methods=['POST'])
def actualizar_stock():
    id_producto = request.form['id_producto']
    nuevo_stock = int(request.form['stock']) # Lo convertimos a entero
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # PASO A: Actualizamos el stock numérico como siempre
    cursor.execute('''
        UPDATE Productos
        SET stock = ?
        WHERE id_producto = ?
    ''', (nuevo_stock, id_producto))
    
    # PASO B: Si el nuevo stock es 0 o menor, automáticamente ponemos activo = 0
    if nuevo_stock <= 0:
        cursor.execute('''
            UPDATE Productos
            SET activo = 0
            WHERE id_producto = ?
        ''', (id_producto,))
        
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('inventario'))


# 5. ACCIÓN NUEVA: Cambiar disponibilidad (Alterna entre 1 y 0)
@app.route('/inventario/cambiar_estado/<int:id_producto>', methods=['POST'])
def cambiar_estado(id_producto):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Si está en 1 lo pasa a 0, si está en 0 lo pasa a 1 de forma automática
    cursor.execute('''
        UPDATE Productos 
        SET activo = CASE WHEN activo = 1 THEN 0 ELSE 1 END 
        WHERE id_producto = ?
    ''', (id_producto,))
    
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('inventario'))

# 6. RUTA DE VENTAS: Mostrar el formulario para nueva venta
@app.route('/registrar_venta')
def ventas():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Solo mandamos al formulario los productos activos que tengan stock disponible
    cursor.execute('SELECT id_producto, nombre, precio, stock FROM Productos WHERE activo = 1 AND stock > 0')
    productos = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('ventas.html', productos=productos)

# 7. ACCIÓN: Procesar la transacción de venta (SOPORTA MÚLTIPLES PRODUCTOS SIMULTÁNEOS)
@app.route('/registrar_venta/guardar', methods=['POST'])
def guardar_venta():
    # Recorremos los datos usando getlist debido a los corchetes [] del formulario HTML
    lista_productos_ids = request.form.getlist('id_producto[]')
    lista_cantidades = request.form.getlist('cantidad[]')
    
    direccion = request.form['direccion']
    nombre_cliente = request.form['nombre_cliente']

    # Abrimos la conexión
    conn = get_db_connection()
    cursor = conn.cursor()

    # --- FASE 1: VALIDACIÓN DE SEGURIDAD GENERAL Y CÁLCULO DEL TOTAL ---
    total_venta = 0.0
    datos_productos_procesados = []

    # Iteramos sobre los arreglos en paralelo usando un índice
    for i in range(len(lista_productos_ids)):
        id_prod = lista_productos_ids[i]
        cant = int(lista_cantidades[i])
        
        # Consultamos stock y precio de cada elemento seleccionado
        cursor.execute('SELECT precio, stock, nombre FROM Productos WHERE id_producto = ?', (id_prod,))
        item = cursor.fetchone()
        
        if not item:
            cursor.close()
            conn.close()
            return f"Error: Uno de los productos seleccionados no existe."
            
        precio_unitario = float(item.precio)
        stock_actual = int(item.stock)
        nombre_producto = item.nombre

        # Rompemos el ciclo si algún producto supera las existencias físicas
        if cant > stock_actual:
            cursor.close()
            conn.close()
            return f"Error: No hay suficiente stock para el producto '{nombre_producto}'. Disponible: {stock_actual}, Solicitado: {cant}."

        subtotal = precio_unitario * cant
        total_venta += subtotal
        
        # Guardamos en una lista temporal los datos listos para no volver a consultar la BD después
        datos_productos_procesados.append({
            'id_producto': id_prod,
            'cantidad': cant,
            'precio_unitario': precio_unitario,
            'stock_actual': stock_actual
        })

    # --- FASE 2: INSERCIÓN GENERAL MAESTRO (1 Sola Venta Compartida) ---
    cursor.execute('''
        INSERT INTO Ventas (fecha, total)
        OUTPUT Inserted.id_venta
        VALUES (GETDATE(), ?)
    ''', (total_venta,))
    id_venta = cursor.fetchone()[0]

    # --- FASE 3: INSERCIÓN DEL DETALLE Y ACTUALIZACIÓN DE STOCK (Ciclo de Guardado) ---
    for item in datos_productos_procesados:
        # A. Guardamos cada renglón del pedido ligado al mismo id_venta
        cursor.execute('''
            INSERT INTO DetalleVentas (id_venta, id_producto, cantidad, precio_unitario)
            VALUES (?, ?, ?, ?)
        ''', (id_venta, item['id_producto'], item['cantidad'], item['precio_unitario']))

        # B. Restamos el inventario correspondiente de forma individual
        nuevo_stock = item['stock_actual'] - item['cantidad']
        nuevo_activo = 0 if nuevo_stock <= 0 else 1

        cursor.execute('''
            UPDATE Productos
            SET stock = ?, activo = ?
            WHERE id_producto = ?
        ''', (nuevo_stock, nuevo_activo, item['id_producto']))

    # --- FASE 4: CREACIÓN DEL PEDIDO LOGÍSTICO (1 Solo envío para toda la compra) ---
    cursor.execute('''
        INSERT INTO Pedidos (id_venta, estado, direccion_entrega, nombre, fecha_actualizacion)
        VALUES (?, 'Pendiente', ?, ?, GETDATE())
    ''', (id_venta, direccion, nombre_cliente))

    # Guardamos definitivamente todos los movimientos en SQL Server
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('index'))

# 8. RUTA DE PEDIDOS: Mostrar el listado completo con detalles de logística
@app.route('/pedidos')
def pedidos():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Añadimos p.fecha_salida y p.fecha_entrega a la consulta SQL
    cursor.execute('''
        SELECT 
            p.id_pedido, 
            p.nombre AS cliente, 
            prod.nombre AS producto, 
            dv.cantidad, 
            v.total, 
            p.direccion_entrega, 
            p.estado,
            p.fecha_salida,
            p.fecha_entrega
        FROM Pedidos p
        JOIN Ventas v ON p.id_venta = v.id_venta
        JOIN DetalleVentas dv ON v.id_venta = dv.id_venta
        JOIN Productos prod ON dv.id_producto = prod.id_producto
        ORDER BY p.id_pedido DESC
    ''')
    pedidos_lista = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('pedidos.html', pedidos=pedidos_lista)


# 9. ACCIÓN: Actualizar los datos del pedido (Campos de texto, selectores y fechas)
@app.route('/pedidos/actualizar/<int:id_pedido>', methods=['POST'])
def actualizar_pedido(id_pedido):
    nuevo_nombre = request.form['nombre']
    nueva_direccion = request.form['direccion']
    nuevo_estado = request.form['estado']
    
    # Capturamos los campos de fecha de HTML
    f_salida = request.form['fecha_salida']
    f_entrega = request.form['fecha_entrega']
    
    # Si el input de fecha está vacío en el navegador, Python lo recibe como "" (cadena vacía)
    # Debemos transformarlo en None para que en SQL Server se inserte de forma correcta como un NULL
    fecha_salida_db = f_salida if f_salida != "" else None
    fecha_entrega_db = f_entrega if f_entrega != "" else None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    # Modificamos la sentencia incluyendo las nuevas columnas de fecha_salida y fecha_entrega
    cursor.execute('''
        UPDATE Pedidos
        SET nombre = ?, 
            direccion_entrega = ?, 
            estado = ?, 
            fecha_salida = ?, 
            fecha_entrega = ?, 
            fecha_actualizacion = GETDATE()
        WHERE id_pedido = ?
    ''', (nuevo_nombre, nueva_direccion, nuevo_estado, fecha_salida_db, fecha_entrega_db, id_pedido))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('pedidos'))

# 10. RUTA DE HISTORIAL: Consulta y consolidación del registro de ventas
@app.route('/historial')
def historial():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Usamos JOINs robustos para armar el reporte financiero detallado
    cursor.execute('''
        SELECT 
            v.id_venta,
            CONVERT(VARCHAR, v.fecha, 120) AS fecha,
            p.nombre AS cliente,
            prod.nombre AS producto,
            dv.cantidad,
            v.total
        FROM Ventas v
        JOIN DetalleVentas dv ON v.id_venta = dv.id_venta
        JOIN Productos prod ON dv.id_producto = prod.id_producto
        JOIN Pedidos p ON v.id_venta = p.id_venta
        ORDER BY v.id_venta DESC
    ''')
    historial_lista = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('historial.html', historial_lista=historial_lista)

if __name__ == '__main__':
    app.run(debug=True)