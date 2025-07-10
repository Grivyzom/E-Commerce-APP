# app.py - ComercioTech con Redis mejorado
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta
import os
import hashlib
import secrets
import json

# Importar el nuevo RedisManager
from redis_manager import create_redis_manager

# Importaciones con manejo de errores
try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    print("Advertencia: mysql-connector-python no está instalado")

try:
    from werkzeug.security import generate_password_hash, check_password_hash
    WERKZEUG_SECURITY_AVAILABLE = True
except ImportError:
    WERKZEUG_SECURITY_AVAILABLE = False
    print("Advertencia: werkzeug.security no está disponible")

app = Flask(__name__)
app.secret_key = "supersecret_comerciotech_2025"

# Configuración de base de datos
VM_IP = "192.168.1.17"  # Tu IP de VM Ubuntu

DB_CONFIG = {
    'host': VM_IP,
    'database': 'comerciotech_db',
    'user': 'root',
    'password': '1234',
    'charset': 'utf8mb4',
    'autocommit': True,
    'port': 3306,
    'connection_timeout': 10
}

# ==========================================
# INICIALIZACIÓN MEJORADA DE REDIS
# ==========================================

# Crear instancia global del gestor de Redis mejorado
redis_manager = create_redis_manager(host=VM_IP, port=6379)

class DatabaseManager:
    def __init__(self):
        self.config = DB_CONFIG
        self.available = MYSQL_AVAILABLE
    
    def get_connection(self):
        if not self.available:
            raise Exception("MySQL no está disponible")
        return mysql.connector.connect(**self.config)
    
    def execute_query(self, query, params=None, fetch=False):
        if not self.available:
            return self._json_fallback(query, params, fetch)
        
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(query, params or ())
            if fetch:
                result = cursor.fetchall()
            else:
                result = cursor.rowcount
            conn.commit()
            return result
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()
    
    def _json_fallback(self, query, params, fetch):
        """Fallback a archivos JSON cuando MySQL no está disponible"""
        import os
        
        if "SELECT * FROM productos" in query:
            if os.path.exists("productos.json"):
                with open("productos.json", "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        
        if "SELECT * FROM usuarios" in query:
            if os.path.exists("usuarios.json"):
                with open("usuarios.json", "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        
        return [] if fetch else 0

# Instancia global de la base de datos
db = DatabaseManager()

# ==========================================
# RUTAS PRINCIPALES (MEJORADAS)
# ==========================================

@app.route("/")
def index():
    if "rol" in session and session["rol"] == "admin":
        return redirect(url_for("admin_dashboard"))
    
    # 🎯 MEJORADO: Intentar obtener productos desde cache
    productos = redis_manager.obtener_productos_cache()
    
    if not productos:
        print("📦 Cache miss - consultando base de datos...")
        
        if db.available:
            query = "SELECT * FROM productos WHERE activo = TRUE"
            productos_db = db.execute_query(query, fetch=True)
            
            # Convertir formato para compatibilidad
            productos = []
            for p in productos_db:
                producto = {
                    "id": p["id_producto"],
                    "id_producto": p["id_producto"],
                    "nombre": p["nombre"],
                    "precio": int(float(p["precio"])),
                    "imagen": p["imagen_url"],
                    "imagen_url": p["imagen_url"],
                    "descripcion": p.get("descripcion", ""),
                    "stock": p.get("stock", 0),
                    "categoria": p.get("categoria", "")
                }
                productos.append(producto)
        else:
            # Fallback a archivos JSON
            import os
            if os.path.exists("productos.json"):
                with open("productos.json", "r", encoding="utf-8") as f:
                    productos = json.load(f)
            else:
                productos = []
        
        # 🎯 MEJORADO: Cachear productos
        if productos:
            redis_manager.cache_productos(productos)
    else:
        print("⚡ Cache hit - productos obtenidos desde Redis")
    
    return render_template("index.html", productos=productos)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        
        query = "SELECT * FROM usuarios WHERE email = %s AND activo = TRUE"
        usuarios = db.execute_query(query, (email,), fetch=True)
        
        if usuarios and usuarios[0]["contraseña"] == password:
            user = usuarios[0]
            
            # 🎯 MEJORADO: Crear sesión mejorada
            session_data = {
                "user_id": user["id_usuario"],
                "nombre": user["nombre"],
                "email": user["email"],
                "rol": user["rol"]
            }
            
            session_token = redis_manager.crear_sesion(session_data)
            
            # Mantener sesión Flask para compatibilidad
            session["usuario"] = user["nombre"]
            session["user_id"] = user["id_usuario"]
            session["rol"] = user["rol"]
            session["session_token"] = session_token
            session.permanent = True
            
            flash("Sesión iniciada correctamente", "success")
            
            if user["rol"] == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("index"))
        
        flash("Credenciales inválidas", "error")
        return redirect(url_for("login"))
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    # 🎯 MEJORADO: Cerrar sesión mejorada
    if "session_token" in session:
        redis_manager.cerrar_sesion(session["session_token"])
    
    session.clear()
    flash("Sesión cerrada correctamente", "info")
    return redirect(url_for("index"))

# ==========================================
# RUTAS DEL CARRITO (MEJORADAS)
# ==========================================

@app.route("/agregar/<int:producto_id>")
def agregar(producto_id):
    if "user_id" not in session:
        flash("Debes iniciar sesión para agregar productos al carrito", "warning")
        return redirect(url_for("login"))
    
    user_id = session["user_id"]
    
    # 🎯 MEJORADO: Agregar con mejor logging
    redis_manager.agregar_al_carrito(user_id, producto_id, 1)
    
    flash("Producto agregado al carrito", "success")
    return redirect(url_for("index"))

@app.route("/carrito")
def ver_carrito():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user_id = session["user_id"]
    
    # 🎯 MEJORADO: Obtener carrito con mejor manejo
    carrito_redis = redis_manager.get_carrito(user_id)
    
    productos_carrito = []
    total = 0
    
    if carrito_redis:
        # Obtener IDs de productos
        producto_ids = list(carrito_redis.keys())
        
        if producto_ids and db.available:
            placeholders = ','.join(['%s'] * len(producto_ids))
            query = f"SELECT * FROM productos WHERE id_producto IN ({placeholders})"
            productos_db = db.execute_query(query, producto_ids, fetch=True)
            
            for producto_db in productos_db:
                cantidad = carrito_redis[str(producto_db['id_producto'])]
                
                item = {
                    "id": producto_db["id_producto"],
                    "nombre": producto_db["nombre"],
                    "precio": float(producto_db["precio"]),
                    "cantidad": cantidad,
                    "imagen": producto_db["imagen_url"]
                }
                productos_carrito.append(item)
                total += item["precio"] * cantidad
        
        elif producto_ids:
            # Fallback a JSON
            import os
            if os.path.exists("productos.json"):
                with open("productos.json", "r", encoding="utf-8") as f:
                    productos_db = json.load(f)
                
                for producto_id, cantidad in carrito_redis.items():
                    for p in productos_db:
                        if str(p["id"]) == str(producto_id):
                            item = {
                                "id": p["id"],
                                "nombre": p["nombre"],
                                "precio": p["precio"],
                                "cantidad": cantidad,
                                "imagen": p["imagen"]
                            }
                            productos_carrito.append(item)
                            total += p["precio"] * cantidad
                            break
    
    return render_template("carrito.html", carrito=productos_carrito, total=total)

@app.route("/incrementar/<int:producto_id>", methods=["POST"])
def incrementar(producto_id):
    if "user_id" in session:
        user_id = session["user_id"]
        redis_manager.agregar_al_carrito(user_id, producto_id, 1)
        flash("Cantidad incrementada", "success")
    return redirect(url_for("ver_carrito"))

@app.route("/disminuir/<int:producto_id>", methods=["POST"])
def disminuir(producto_id):
    if "user_id" in session:
        user_id = session["user_id"]
        carrito = redis_manager.get_carrito(user_id)
        producto_key = str(producto_id)
        
        if producto_key in carrito:
            nueva_cantidad = carrito[producto_key] - 1
            if nueva_cantidad > 0:
                redis_manager.actualizar_cantidad_carrito(user_id, producto_id, nueva_cantidad)
                flash("Cantidad actualizada", "success")
            else:
                redis_manager.quitar_del_carrito(user_id, producto_id)
                flash("Producto eliminado del carrito", "info")
    
    return redirect(url_for("ver_carrito"))

@app.route("/eliminar/<int:producto_id>", methods=["POST"])
def eliminar(producto_id):
    if "user_id" in session:
        user_id = session["user_id"]
        redis_manager.quitar_del_carrito(user_id, producto_id)
        flash("Producto eliminado del carrito", "info")
    return redirect(url_for("ver_carrito"))

@app.route("/vaciar", methods=["POST"])
def vaciar_carrito():
    if "user_id" in session:
        user_id = session["user_id"]
        redis_manager.vaciar_carrito(user_id)
        flash("Carrito vaciado", "info")
    return redirect(url_for("ver_carrito"))

@app.route("/finalizar_compra")
def finalizar_compra():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user_id = session["user_id"]
    carrito = redis_manager.get_carrito(user_id)
    
    if not carrito:
        flash("Tu carrito está vacío", "warning")
        return redirect(url_for("ver_carrito"))
    
    try:
        # Obtener productos del carrito
        producto_ids = list(carrito.keys())
        
        if not producto_ids:
            flash("Tu carrito está vacío", "warning")
            return redirect(url_for("ver_carrito"))
        
        # Verificar productos
        placeholders = ','.join(['%s'] * len(producto_ids))
        query = f"SELECT * FROM productos WHERE id_producto IN ({placeholders})"
        productos = db.execute_query(query, producto_ids, fetch=True)
        
        if not productos:
            flash("Error: productos no encontrados", "error")
            return redirect(url_for("ver_carrito"))
        
        # Obtener dirección del usuario
        query_user = "SELECT direccion FROM usuarios WHERE id_usuario = %s"
        user_data = db.execute_query(query_user, (user_id,), fetch=True)
        direccion = user_data[0]["direccion"] if user_data else "Dirección no especificada"
        
        # Calcular total
        total = 0
        for producto in productos:
            cantidad = carrito[str(producto['id_producto'])]
            total += float(producto["precio"]) * cantidad
        
        # Transacción de base de datos
        config_transaction = DB_CONFIG.copy()
        config_transaction['autocommit'] = False
        
        conn = mysql.connector.connect(**config_transaction)
        cursor = conn.cursor(dictionary=True)
        
        try:
            # 1. Insertar pedido
            query_pedido = """
            INSERT INTO pedidos (id_usuario, direccion_envio, total, estado)
            VALUES (%s, %s, %s, 'Pendiente')
            """
            cursor.execute(query_pedido, (user_id, direccion, total))
            
            # 2. Obtener ID del pedido
            pedido_id = cursor.lastrowid
            print(f"🆔 Pedido ID creado: {pedido_id}")
            
            if not pedido_id:
                raise Exception("No se pudo obtener el ID del pedido")
            
            # 3. Insertar detalles del pedido
            query_detalle = """
            INSERT INTO detalles_pedido (id_pedido, id_producto, cantidad, precio_unitario)
            VALUES (%s, %s, %s, %s)
            """
            
            for producto in productos:
                cantidad = carrito[str(producto['id_producto'])]
                
                cursor.execute(query_detalle, (
                    pedido_id,
                    producto["id_producto"],
                    cantidad,
                    float(producto["precio"])
                ))
            
            # 4. Confirmar transacción
            conn.commit()
            print(f"✅ Pedido #{pedido_id} creado exitosamente")
            
            # 🎯 MEJORADO: Vaciar carrito después de compra exitosa
            redis_manager.vaciar_carrito(user_id)
            
            flash(f"¡Pedido #{pedido_id} creado exitosamente!", "success")
            return render_template("finalizado.html")
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Error en transacción: {e}")
            raise e
        finally:
            cursor.close()
            conn.close()
        
    except Exception as e:
        flash(f"Error al procesar el pedido: {str(e)}", "error")
        print(f"❌ Error general: {e}")
        return redirect(url_for("ver_carrito"))

# ==========================================
# RUTAS DE ADMINISTRACIÓN (MEJORADAS)
# ==========================================

@app.route("/admin/productos")
def admin_productos():
    if session.get("rol") != "admin":
        return redirect(url_for("index"))
    
    if db.available:
        query = "SELECT * FROM productos ORDER BY id_producto"
        productos_db = db.execute_query(query, fetch=True)
        
        productos = []
        for p in productos_db:
            producto = {
                "id": p["id_producto"],
                "nombre": p["nombre"],
                "precio": int(float(p["precio"])),
                "imagen": p["imagen_url"],
                "descripcion": p.get("descripcion", ""),
                "stock": p.get("stock", 0),
                "categoria": p.get("categoria", "")
            }
            productos.append(producto)
    else:
        # Fallback a JSON
        import os
        if os.path.exists("productos.json"):
            with open("productos.json", "r", encoding="utf-8") as f:
                productos = json.load(f)
        else:
            productos = []
    
    return render_template("admin_productos.html", productos=productos)

@app.route("/admin/producto/nuevo", methods=["GET", "POST"])
def admin_nuevo_producto():
    if session.get("rol") != "admin":
        return redirect(url_for("index"))
    
    if request.method == "POST":
        if db.available:
            query = """
            INSERT INTO productos (nombre, precio, imagen_url, descripcion, stock, categoria, activo)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                request.form["nombre"],
                float(request.form["precio"]),
                request.form.get("imagen", ""),
                request.form.get("descripcion", ""),
                int(request.form.get("stock", 0)),
                request.form.get("categoria", ""),
                True
            )
            db.execute_query(query, params)
            
            # 🎯 MEJORADO: Invalidar cache al agregar producto
            redis_manager.invalidar_cache_productos()
            
        else:
            # Fallback a JSON
            import os
            if os.path.exists("productos.json"):
                with open("productos.json", "r", encoding="utf-8") as f:
                    productos = json.load(f)
            else:
                productos = []
            
            nuevo_producto = {
                "id": len(productos) + 1,
                "nombre": request.form["nombre"],
                "precio": int(request.form["precio"]),
                "imagen": request.form.get("imagen", ""),
                "descripcion": request.form.get("descripcion", ""),
                "stock": int(request.form.get("stock", 0)),
                "categoria": request.form.get("categoria", "")
            }
            productos.append(nuevo_producto)
            
            with open("productos.json", "w", encoding="utf-8") as f:
                json.dump(productos, f, indent=4, ensure_ascii=False)
        
        flash("Producto creado exitosamente", "success")
        return redirect(url_for("admin_productos"))
    
    return render_template("admin_nuevo_productos.html")

@app.route("/admin/producto/<int:producto_id>/editar", methods=["GET", "POST"])
def admin_editar_producto(producto_id):
    if session.get("rol") != "admin":
        return redirect(url_for("index"))
    
    if db.available:
        # Obtener producto actual
        query = "SELECT * FROM productos WHERE id_producto = %s"
        productos_db = db.execute_query(query, (producto_id,), fetch=True)
        
        if not productos_db:
            flash("Producto no encontrado", "error")
            return redirect(url_for("admin_productos"))
        
        producto_db = productos_db[0]
        producto = {
            "id": producto_db["id_producto"],
            "nombre": producto_db["nombre"],
            "precio": int(float(producto_db["precio"])),
            "imagen": producto_db["imagen_url"],
            "descripcion": producto_db.get("descripcion", ""),
            "stock": producto_db.get("stock", 0),
            "categoria": producto_db.get("categoria", "")
        }
    else:
        # Fallback a JSON
        import os
        if os.path.exists("productos.json"):
            with open("productos.json", "r", encoding="utf-8") as f:
                productos = json.load(f)
            producto = next((p for p in productos if p["id"] == producto_id), None)
            if not producto:
                flash("Producto no encontrado", "error")
                return redirect(url_for("admin_productos"))
        else:
            flash("No se encontraron productos", "error")
            return redirect(url_for("admin_productos"))
    
    if request.method == "POST":
        if db.available:
            query = """
            UPDATE productos 
            SET nombre = %s, precio = %s, imagen_url = %s, descripcion = %s, stock = %s, categoria = %s
            WHERE id_producto = %s
            """
            params = (
                request.form["nombre"],
                float(request.form["precio"]),
                request.form.get("imagen", ""),
                request.form.get("descripcion", ""),
                int(request.form.get("stock", 0)),
                request.form.get("categoria", ""),
                producto_id
            )
            db.execute_query(query, params)
            
            # 🎯 MEJORADO: Invalidar cache al editar producto
            redis_manager.invalidar_cache_productos()
            
        else:
            # Actualizar en JSON
            for p in productos:
                if p["id"] == producto_id:
                    p["nombre"] = request.form["nombre"]
                    p["precio"] = int(request.form["precio"])
                    p["imagen"] = request.form.get("imagen", "")
                    p["descripcion"] = request.form.get("descripcion", "")
                    p["stock"] = int(request.form.get("stock", 0))
                    p["categoria"] = request.form.get("categoria", "")
                    break
            
            with open("productos.json", "w", encoding="utf-8") as f:
                json.dump(productos, f, indent=4, ensure_ascii=False)
        
        flash("Producto actualizado exitosamente", "success")
        return redirect(url_for("admin_productos"))
    
    return render_template("admin_editar_producto.html", producto=producto)

@app.route("/admin/producto/<int:producto_id>/eliminar", methods=["POST"])
def admin_eliminar_producto(producto_id):
    if session.get("rol") != "admin":
        return redirect(url_for("index"))
    
    if db.available:
        # Marcar como inactivo
        query = "UPDATE productos SET activo = FALSE WHERE id_producto = %s"
        db.execute_query(query, (producto_id,))
        
        # 🎯 MEJORADO: Invalidar cache al eliminar producto
        redis_manager.invalidar_cache_productos()
        
    else:
        # Eliminar del JSON
        import os
        if os.path.exists("productos.json"):
            with open("productos.json", "r", encoding="utf-8") as f:
                productos = json.load(f)
            
            productos = [p for p in productos if p["id"] != producto_id]
            
            with open("productos.json", "w", encoding="utf-8") as f:
                json.dump(productos, f, indent=4, ensure_ascii=False)
    
    flash("Producto eliminado exitosamente", "success")
    return redirect(url_for("admin_productos"))

# ==========================================
# RUTAS RESTANTES (SIN CAMBIOS)
# ==========================================

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        email = request.form["email"]
        query_check = "SELECT id_usuario FROM usuarios WHERE email = %s"
        existing_user = db.execute_query(query_check, (email,), fetch=True)
        
        if existing_user:
            flash("Ya existe un usuario con este correo.", "error")
            return redirect(url_for("registro"))
        
        query_insert = """
        INSERT INTO usuarios (nombre, apellidos, email, contraseña, rut, telefono, direccion, rol)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'cliente')
        """
        
        params = (
            request.form["nombre"],
            request.form["apellidos"],
            request.form["email"],
            request.form["password"],
            request.form["rut"],
            request.form["telefono"],
            request.form["direccion"]
        )
        
        db.execute_query(query_insert, params)
        flash("Usuario registrado exitosamente", "success")
        return redirect(url_for("login"))
    
    return render_template("registro.html")

@app.route("/mis_pedidos")
def mis_pedidos():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user_id = session["user_id"]
    query = """
    SELECT p.*, GROUP_CONCAT(CONCAT(dp.cantidad, 'x ', pr.nombre) SEPARATOR ', ') as productos
    FROM pedidos p
    LEFT JOIN detalles_pedido dp ON p.id_pedido = dp.id_pedido
    LEFT JOIN productos pr ON dp.id_producto = pr.id_producto
    WHERE p.id_usuario = %s
    GROUP BY p.id_pedido
    ORDER BY p.fecha_pedido DESC
    """
    
    pedidos = db.execute_query(query, (user_id,), fetch=True)
    return render_template("mis_pedidos.html", pedidos=pedidos)

@app.route("/pedido/<int:pedido_id>")
def detalle_pedido(pedido_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user_id = session["user_id"]
    
    query_pedido = """
    SELECT p.*, u.nombre as cliente
    FROM pedidos p
    JOIN usuarios u ON p.id_usuario = u.id_usuario
    WHERE p.id_pedido = %s AND p.id_usuario = %s
    """
    
    pedidos = db.execute_query(query_pedido, (pedido_id, user_id), fetch=True)
    
    if not pedidos:
        flash("Pedido no encontrado", "error")
        return redirect(url_for("mis_pedidos"))
    
    pedido = pedidos[0]
    
    query_detalles = """
    SELECT dp.*, pr.nombre as nombre_producto
    FROM detalles_pedido dp
    JOIN productos pr ON dp.id_producto = pr.id_producto
    WHERE dp.id_pedido = %s
    """
    
    detalles = db.execute_query(query_detalles, (pedido_id,), fetch=True)
    pedido['detalles'] = detalles
    
    return render_template("detalle_pedido.html", pedido=pedido)

@app.route("/admin")
def admin_dashboard():
    if session.get("rol") != "admin":
        return redirect(url_for("index"))
    return render_template("admin_dashboard.html")

@app.route("/admin/pedidos")
def admin_pedidos():
    if session.get("rol") != "admin":
        return redirect(url_for("index"))
    
    query = """
    SELECT p.id_pedido, u.nombre as cliente, p.fecha_pedido, p.total, p.estado
    FROM pedidos p
    JOIN usuarios u ON p.id_usuario = u.id_usuario
    ORDER BY p.fecha_pedido DESC
    """
    
    pedidos = db.execute_query(query, fetch=True)
    return render_template("admin_pedidos.html", pedidos=pedidos)

@app.route("/admin/pedido/<int:pedido_id>")
def admin_ver_pedido(pedido_id):
    if session.get("rol") != "admin":
        return redirect(url_for("index"))
    
    query_pedido = """
    SELECT p.*, u.nombre as cliente, u.email
    FROM pedidos p
    JOIN usuarios u ON p.id_usuario = u.id_usuario
    WHERE p.id_pedido = %s
    """
    
    pedidos = db.execute_query(query_pedido, (pedido_id,), fetch=True)
    
    if not pedidos:
        flash("Pedido no encontrado", "error")
        return redirect(url_for("admin_pedidos"))
    
    pedido = pedidos[0]
    
    query_detalles = """
    SELECT dp.*, pr.nombre as nombre_producto
    FROM detalles_pedido dp
    JOIN productos pr ON dp.id_producto = pr.id_producto
    WHERE dp.id_pedido = %s
    """
    
    detalles = db.execute_query(query_detalles, (pedido_id,), fetch=True)
    pedido['productos'] = detalles
    
    return render_template("admin_detalle_pedido.html", pedido=pedido)

@app.route("/admin/pedido/<int:pedido_id>/cambiar-estado", methods=["GET", "POST"])
def admin_cambiar_estado(pedido_id):
    if session.get("rol") != "admin":
        return redirect(url_for("index"))
    
    if request.method == "POST":
        nuevo_estado = request.form["nuevo_estado"]
        
        query = "UPDATE pedidos SET estado = %s WHERE id_pedido = %s"
        db.execute_query(query, (nuevo_estado, pedido_id))
        
        flash("Estado del pedido actualizado exitosamente", "success")
        return redirect(url_for("admin_ver_pedido", pedido_id=pedido_id))
    
    return redirect(url_for("admin_ver_pedido", pedido_id=pedido_id))

# ==========================================
# API ROUTES (MEJORADAS CON REDIS STATS)
# ==========================================

@app.route("/admin/api/estadisticas")
def admin_api_estadisticas():
    if session.get("rol") != "admin":
        return jsonify({"error": "No autorizado"}), 403
    
    try:
        # Estadísticas de base de datos
        query_total = "SELECT COUNT(*) as total FROM pedidos"
        total_result = db.execute_query(query_total, fetch=True)
        total_pedidos = total_result[0]["total"] if total_result else 0
        
        query_pendientes = "SELECT COUNT(*) as pendientes FROM pedidos WHERE estado = 'Pendiente'"
        pendientes_result = db.execute_query(query_pendientes, fetch=True)
        pedidos_pendientes = pendientes_result[0]["pendientes"] if pendientes_result else 0
        
        query_entregados = "SELECT COUNT(*) as entregados FROM pedidos WHERE estado = 'Entregado'"
        entregados_result = db.execute_query(query_entregados, fetch=True)
        pedidos_entregados = entregados_result[0]["entregados"] if entregados_result else 0
        
        query_ventas = "SELECT SUM(total) as ventas_total FROM pedidos WHERE estado != 'Cancelado'"
        ventas_result = db.execute_query(query_ventas, fetch=True)
        ventas_total = float(ventas_result[0]["ventas_total"]) if ventas_result and ventas_result[0]["ventas_total"] else 0
        
        # 🎯 MEJORADO: Incluir estadísticas de Redis
        redis_stats = redis_manager.get_stats()
        
        return jsonify({
            "total_pedidos": total_pedidos,
            "pedidos_pendientes": pedidos_pendientes,
            "pedidos_entregados": pedidos_entregados,
            "ventas_total": ventas_total,
            "redis_stats": redis_stats
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# RUTAS DE DEBUG Y MONITOREO
# ==========================================

@app.route("/debug/redis")
def debug_redis():
    """Ruta de debugging para Redis (solo admins)"""
    if session.get("rol") != "admin":
        return jsonify({"error": "Solo admins pueden ver esta información"}), 403
    
    stats = redis_manager.get_stats()
    return jsonify({
        "redis_status": stats,
        "session_info": {
            "user_id": session.get("user_id"),
            "session_token": session.get("session_token", "No token"),
            "flask_session_keys": list(session.keys())
        }
    })

@app.route("/admin/redis/cleanup", methods=["POST"])
def admin_redis_cleanup():
    """Limpieza manual de Redis (solo admins)"""
    if session.get("rol") != "admin":
        return jsonify({"error": "No autorizado"}), 403
    
    try:
        resultado = redis_manager.limpiar_datos_expirados()
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# INICIALIZACIÓN
# ==========================================

if __name__ == "__main__":
    print("🚀 Iniciando ComercioTech con Redis mejorado...")
    print(f"🔧 MySQL disponible: {'✅' if MYSQL_AVAILABLE else '❌'}")
    print(f"🔧 Redis disponible: {'✅' if redis_manager.available else '❌'}")
    
    if not MYSQL_AVAILABLE:
        print("📝 Usando archivos JSON como fallback para datos")
    
    if not redis_manager.available:
        print("📝 Usando sesiones Flask como fallback para cache/carrito")
    
    # Mostrar estadísticas iniciales
    if redis_manager.available:
        stats = redis_manager.get_stats()
        print(f"📊 Redis Stats: {stats}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)