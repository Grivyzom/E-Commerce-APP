from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta
import os
import hashlib
import secrets
import json

# Importaciones con manejo de errores
try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    print("Advertencia: mysql-connector-python no está instalado")

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("Advertencia: redis no está instalado")

try:
    from werkzeug.security import generate_password_hash, check_password_hash
    WERKZEUG_SECURITY_AVAILABLE = True
except ImportError:
    WERKZEUG_SECURITY_AVAILABLE = False
    print("Advertencia: werkzeug.security no está disponible")

app = Flask(__name__)
app.secret_key = "supersecret_comerciotech_2025"

# Configuración de base de datos - VM Ubuntu
VM_IP = "192.168.1.17"  # IP de tu VM Ubuntu

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

# Configuración de Redis
if REDIS_AVAILABLE:
    try:
        redis_client = redis.Redis(
            host=VM_IP,  # IP de tu VM Ubuntu
            port=6379, 
            db=0, 
            decode_responses=True,
            socket_connect_timeout=10,
            socket_timeout=10
        )
        # Probar conexión
        redis_client.ping()
        print("✅ Conexión a Redis (VM) establecida")
    except Exception as e:
        print(f"❌ Error conectando a Redis en VM: {e}")
        redis_client = None
        REDIS_AVAILABLE = False
else:
    redis_client = None

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
            # Fallback a archivos JSON
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
        
        # Cargar datos desde archivos JSON existentes
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
        
        # Para otras consultas, retornar lista vacía
        return [] if fetch else 0

class RedisManager:
    def __init__(self, redis_client):
        self.client = redis_client
        self.available = redis_client is not None
    
    def get_carrito(self, user_id):
        """Obtener carrito del usuario desde Redis o sesión"""
        if not self.available:
            # Fallback a sesión Flask
            return session.get("carrito", {})
        
        carrito_key = f"carrito:{user_id}"
        carrito_data = self.client.hgetall(carrito_key)
        return {k: int(v) for k, v in carrito_data.items()}
    
    def agregar_al_carrito(self, user_id, producto_id, cantidad=1):
        """Agregar producto al carrito"""
        if not self.available:
            # Fallback a sesión Flask
            carrito = session.get("carrito", {})
            producto_key = str(producto_id)
            carrito[producto_key] = carrito.get(producto_key, 0) + cantidad
            session["carrito"] = carrito
            return
        
        carrito_key = f"carrito:{user_id}"
        self.client.hincrby(carrito_key, f"producto:{producto_id}", cantidad)
        self.client.expire(carrito_key, 86400)  # 24 horas
    
    def quitar_del_carrito(self, user_id, producto_id):
        """Quitar producto del carrito"""
        if not self.available:
            # Fallback a sesión Flask
            carrito = session.get("carrito", {})
            producto_key = str(producto_id)
            if producto_key in carrito:
                del carrito[producto_key]
                session["carrito"] = carrito
            return
        
        carrito_key = f"carrito:{user_id}"
        self.client.hdel(carrito_key, f"producto:{producto_id}")
    
    def vaciar_carrito(self, user_id):
        """Vaciar carrito del usuario"""
        if not self.available:
            # Fallback a sesión Flask
            session["carrito"] = {}
            return
        
        carrito_key = f"carrito:{user_id}"
        self.client.delete(carrito_key)
    
    def crear_sesion(self, user_data):
        """Crear sesión de usuario"""
        if not self.available:
            # Usar sesión Flask estándar
            for key, value in user_data.items():
                session[key] = value
            return "flask_session"
        
        session_token = secrets.token_urlsafe(32)
        session_key = f"session:{session_token}"
        
        self.client.hmset(session_key, user_data)
        self.client.expire(session_key, 3600)  # 1 hora
        
        return session_token
    
    def obtener_sesion(self, session_token):
        """Obtener datos de sesión"""
        if not self.available:
            return dict(session)
        
        session_key = f"session:{session_token}"
        return self.client.hgetall(session_key)
    
    def cache_productos(self, productos):
        """Cachear lista de productos"""
        if not self.available:
            return
        
        try:
            self.client.setex("cache:productos:all", 300, json.dumps(productos, default=str))
        except:
            pass
    
    def obtener_productos_cache(self):
        """Obtener productos desde cache"""
        if not self.available:
            return None
        
        try:
            cached = self.client.get("cache:productos:all")
            return json.loads(cached) if cached else None
        except:
            return None

# Instancias globales
db = DatabaseManager()
redis_manager = RedisManager(redis_client)

@app.route("/")
def index():
    if "rol" in session and session["rol"] == "admin":
        return redirect(url_for("admin_dashboard"))
    
    # Intentar obtener productos desde cache
    productos = redis_manager.obtener_productos_cache()
    
    if not productos:
        # Si no están en cache, obtener de base de datos
        if db.available:
            query = "SELECT * FROM productos WHERE activo = TRUE"
            productos_db = db.execute_query(query, fetch=True)
            
            # Convertir nombres de campos de BD a formato esperado por template
            productos = []
            for p in productos_db:
                producto = {
                    "id": p["id_producto"],  # Para URLs de agregar al carrito
                    "id_producto": p["id_producto"],  # Compatibilidad
                    "nombre": p["nombre"],
                    "precio": int(float(p["precio"])),  # Convertir a int para evitar decimales
                    "imagen": p["imagen_url"],  # Mapear imagen_url -> imagen
                    "imagen_url": p["imagen_url"],  # Mantener también imagen_url
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
                    import json
                    productos = json.load(f)
            else:
                productos = []
        
        # Cachear productos si Redis está disponible
        if productos:
            redis_manager.cache_productos(productos)
    
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
            
            # Crear sesión en Redis
            session_data = {
                "user_id": str(user["id_usuario"]),
                "nombre": user["nombre"],
                "email": user["email"],
                "rol": user["rol"]
            }
            
            session_token = redis_manager.crear_sesion(session_data)
            
            # Guardar en sesión Flask
            session["usuario"] = user["nombre"]
            session["user_id"] = user["id_usuario"]
            session["rol"] = user["rol"]
            session["session_token"] = session_token
            
            flash("Sesión iniciada correctamente")
            
            if user["rol"] == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("index"))
        
        flash("Credenciales inválidas")
        return redirect(url_for("login"))
    
    return render_template("login.html")

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        # Validar si ya existe el correo
        email = request.form["email"]
        query_check = "SELECT id_usuario FROM usuarios WHERE email = %s"
        existing_user = db.execute_query(query_check, (email,), fetch=True)
        
        if existing_user:
            flash("Ya existe un usuario con este correo.")
            return redirect(url_for("registro"))
        
        # Insertar nuevo usuario
        query_insert = """
        INSERT INTO usuarios (nombre, apellidos, email, contraseña, rut, telefono, direccion, rol)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'cliente')
        """
        
        params = (
            request.form["nombre"],
            request.form["apellidos"],
            request.form["email"],
            request.form["password"],  # En producción, usar hash
            request.form["rut"],
            request.form["telefono"],
            request.form["direccion"]
        )
        
        db.execute_query(query_insert, params)
        flash("Usuario registrado exitosamente")
        return redirect(url_for("login"))
    
    return render_template("registro.html")

@app.route("/logout")
def logout():
    # Eliminar sesión de Redis si existe
    if "session_token" in session:
        session_key = f"session:{session['session_token']}"
        redis_client.delete(session_key)
    
    session.clear()
    flash("Sesión cerrada.")
    return redirect(url_for("index"))

@app.route("/agregar/<int:producto_id>")
def agregar(producto_id):
    if "user_id" not in session:
        flash("Debes iniciar sesión para agregar productos al carrito")
        return redirect(url_for("login"))
    
    user_id = session["user_id"]
    redis_manager.agregar_al_carrito(user_id, producto_id)
    
    return redirect(url_for("index"))

@app.route("/carrito")
def ver_carrito():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user_id = session["user_id"]
    carrito_redis = redis_manager.get_carrito(user_id)
    
    productos_carrito = []
    total = 0
    
    if carrito_redis:
        if db.available:
            # Obtener detalles de productos del carrito desde BD
            if redis_manager.available:
                # Redis está disponible, usar formato Redis
                producto_ids = [pid.split(':')[1] for pid in carrito_redis.keys()]
            else:
                # Redis no disponible, usar formato de sesión Flask
                producto_ids = list(carrito_redis.keys())
            
            if producto_ids:
                placeholders = ','.join(['%s'] * len(producto_ids))
                query = f"SELECT * FROM productos WHERE id_producto IN ({placeholders})"
                productos_db = db.execute_query(query, producto_ids, fetch=True)
                
                for producto_db in productos_db:
                    if redis_manager.available:
                        cantidad = carrito_redis[f"producto:{producto_db['id_producto']}"]
                    else:
                        cantidad = carrito_redis[str(producto_db['id_producto'])]
                    
                    item = {
                        "id": producto_db["id_producto"],  # Mapear id_producto -> id
                        "nombre": producto_db["nombre"],
                        "precio": float(producto_db["precio"]),  # Convertir Decimal a float
                        "cantidad": cantidad,
                        "imagen": producto_db["imagen_url"]  # Mapear imagen_url -> imagen
                    }
                    productos_carrito.append(item)
                    total += item["precio"] * cantidad
        else:
            # Fallback a archivos JSON
            import os, json
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
        redis_manager.agregar_al_carrito(session["user_id"], producto_id, 1)
    return redirect(url_for("ver_carrito"))

@app.route("/pedido/<int:pedido_id>")
def detalle_pedido(pedido_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user_id = session["user_id"]
    
    # Obtener el pedido específico del usuario
    query_pedido = """
    SELECT p.*, u.nombre as cliente
    FROM pedidos p
    JOIN usuarios u ON p.id_usuario = u.id_usuario
    WHERE p.id_pedido = %s AND p.id_usuario = %s
    """
    
    pedidos = db.execute_query(query_pedido, (pedido_id, user_id), fetch=True)
    
    if not pedidos:
        flash("Pedido no encontrado")
        return redirect(url_for("mis_pedidos"))
    
    pedido = pedidos[0]
    
    # Obtener detalles del pedido
    query_detalles = """
    SELECT dp.*, pr.nombre as nombre_producto
    FROM detalles_pedido dp
    JOIN productos pr ON dp.id_producto = pr.id_producto
    WHERE dp.id_pedido = %s
    """
    
    detalles = db.execute_query(query_detalles, (pedido_id,), fetch=True)
    pedido['detalles'] = detalles
    
    return render_template("detalle_pedido.html", pedido=pedido)

@app.route("/disminuir/<int:producto_id>", methods=["POST"])
def disminuir(producto_id):
    if "user_id" in session:
        user_id = session["user_id"]
        carrito = redis_manager.get_carrito(user_id)
        producto_key = f"producto:{producto_id}"
        
        if producto_key in carrito:
            if carrito[producto_key] > 1:
                redis_manager.agregar_al_carrito(user_id, producto_id, -1)
            else:
                redis_manager.quitar_del_carrito(user_id, producto_id)
    
    return redirect(url_for("ver_carrito"))

@app.route("/eliminar/<int:producto_id>", methods=["POST"])
def eliminar(producto_id):
    if "user_id" in session:
        redis_manager.quitar_del_carrito(session["user_id"], producto_id)
    return redirect(url_for("ver_carrito"))

@app.route("/vaciar", methods=["POST"])
def vaciar_carrito():
    if "user_id" in session:
        redis_manager.vaciar_carrito(session["user_id"])
    return redirect(url_for("ver_carrito"))

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

# Rutas para gestión de productos
@app.route("/admin/productos")
def admin_productos():
    if session.get("rol") != "admin":
        return redirect(url_for("index"))
    
    if db.available:
        query = "SELECT * FROM productos ORDER BY id_producto"
        productos_db = db.execute_query(query, fetch=True)
        
        # Mapear campos para compatibilidad con template
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
        
        flash("Producto creado exitosamente")
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
            flash("Producto no encontrado")
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
                flash("Producto no encontrado")
                return redirect(url_for("admin_productos"))
        else:
            flash("No se encontraron productos")
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
        
        flash("Producto actualizado exitosamente")
        return redirect(url_for("admin_productos"))
    
    return render_template("admin_editar_producto.html", producto=producto)

@app.route("/admin/producto/<int:producto_id>/eliminar", methods=["POST"])
def admin_eliminar_producto(producto_id):
    if session.get("rol") != "admin":
        return redirect(url_for("index"))
    
    if db.available:
        # Marcar como inactivo en lugar de eliminar
        query = "UPDATE productos SET activo = FALSE WHERE id_producto = %s"
        db.execute_query(query, (producto_id,))
    else:
        # Eliminar del JSON
        import os
        if os.path.exists("productos.json"):
            with open("productos.json", "r", encoding="utf-8") as f:
                productos = json.load(f)
            
            productos = [p for p in productos if p["id"] != producto_id]
            
            with open("productos.json", "w", encoding="utf-8") as f:
                json.dump(productos, f, indent=4, ensure_ascii=False)
    
    flash("Producto eliminado exitosamente")
    return redirect(url_for("admin_productos"))

@app.route("/finalizar_compra")
def finalizar_compra():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user_id = session["user_id"]
    carrito = redis_manager.get_carrito(user_id)
    
    if not carrito:
        flash("Tu carrito está vacío")
        return redirect(url_for("ver_carrito"))
    
    try:
        # Obtener productos del carrito
        if redis_manager.available:
            producto_ids = [pid.split(':')[1] for pid in carrito.keys()]
        else:
            producto_ids = list(carrito.keys())
        
        if not producto_ids:
            flash("Tu carrito está vacío")
            return redirect(url_for("ver_carrito"))
        
        # Verificar que los productos existen
        placeholders = ','.join(['%s'] * len(producto_ids))
        query = f"SELECT * FROM productos WHERE id_producto IN ({placeholders})"
        productos = db.execute_query(query, producto_ids, fetch=True)
        
        if not productos:
            flash("Error: productos no encontrados")
            return redirect(url_for("ver_carrito"))
        
        # Obtener dirección del usuario
        query_user = "SELECT direccion FROM usuarios WHERE id_usuario = %s"
        user_data = db.execute_query(query_user, (user_id,), fetch=True)
        direccion = user_data[0]["direccion"] if user_data else "Dirección no especificada"
        
        # Calcular total
        total = 0
        for producto in productos:
            if redis_manager.available:
                cantidad = carrito[f"producto:{producto['id_producto']}"]
            else:
                cantidad = carrito[str(producto['id_producto'])]
            total += float(producto["precio"]) * cantidad
        
        # Usar una conexión específica sin autocommit
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
            
            # 2. Obtener el ID del pedido
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
                if redis_manager.available:
                    cantidad = carrito[f"producto:{producto['id_producto']}"]
                else:
                    cantidad = carrito[str(producto['id_producto'])]
                
                print(f"📦 Insertando: pedido={pedido_id}, producto={producto['id_producto']}, cantidad={cantidad}")
                
                cursor.execute(query_detalle, (
                    pedido_id,
                    producto["id_producto"],
                    cantidad,
                    float(producto["precio"])
                ))
            
            # 4. Confirmar todo
            conn.commit()
            print(f"✅ Pedido #{pedido_id} creado exitosamente")
            
            # 5. Vaciar carrito
            redis_manager.vaciar_carrito(user_id)
            
            flash(f"¡Pedido #{pedido_id} creado exitosamente!")
            
            return render_template("finalizado.html")
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Error en transacción: {e}")
            raise e
        finally:
            cursor.close()
            conn.close()
        
    except Exception as e:
        flash(f"Error al procesar el pedido: {str(e)}")
        print(f"❌ Error general: {e}")
        return redirect(url_for("ver_carrito"))

if __name__ == "__main__":
    print("🚀 Iniciando ComercioTech...")
    print(f"🔧 MySQL disponible: {'✅' if MYSQL_AVAILABLE else '❌'}")
    print(f"🔧 Redis disponible: {'✅' if REDIS_AVAILABLE else '❌'}")
    
    if not MYSQL_AVAILABLE:
        print("📝 Usando archivos JSON como fallback para datos")
    
    if not REDIS_AVAILABLE:
        print("📝 Usando sesiones Flask como fallback para cache")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
    
# MOVER ESTAS RUTAS ANTES DEL if __name__ == "__main__":

@app.route("/admin/pedido/<int:pedido_id>")
def admin_ver_pedido(pedido_id):
    if session.get("rol") != "admin":
        return redirect(url_for("index"))
    
    # Obtener pedido específico
    query_pedido = """
    SELECT p.*, u.nombre as cliente, u.email
    FROM pedidos p
    JOIN usuarios u ON p.id_usuario = u.id_usuario
    WHERE p.id_pedido = %s
    """
    
    pedidos = db.execute_query(query_pedido, (pedido_id,), fetch=True)
    
    if not pedidos:
        flash("Pedido no encontrado")
        return redirect(url_for("admin_pedidos"))
    
    pedido = pedidos[0]
    
    # Obtener detalles del pedido
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
        
        flash("Estado del pedido actualizado exitosamente")
        return redirect(url_for("admin_ver_pedido", pedido_id=pedido_id))
    
    return redirect(url_for("admin_ver_pedido", pedido_id=pedido_id))


# Ruta para API JSON (para el panel moderno)
@app.route("/admin/api/pedidos")
def admin_api_pedidos():
    if session.get("rol") != "admin":
        return jsonify({"error": "No autorizado"}), 403
    
    try:
        query = """
        SELECT p.id_pedido, u.nombre as cliente, u.email, 
               p.fecha_pedido, p.total, p.estado, p.direccion_envio
        FROM pedidos p
        JOIN usuarios u ON p.id_usuario = u.id_usuario
        ORDER BY p.fecha_pedido DESC
        """
        
        pedidos_db = db.execute_query(query, fetch=True)
        
        # Convertir a formato JSON serializable
        pedidos = []
        for p in pedidos_db:
            pedido = {
                "id": p["id_pedido"],
                "cliente": p["cliente"],
                "email": p["email"],
                "fecha": p["fecha_pedido"].strftime('%Y-%m-%d %H:%M') if hasattr(p["fecha_pedido"], 'strftime') else str(p["fecha_pedido"]),
                "estado": p["estado"],
                "total": float(p["total"]),
                "direccion": p["direccion_envio"]
            }
            
            # Obtener productos del pedido
            query_productos = """
            SELECT dp.cantidad, dp.precio_unitario, pr.nombre as nombre_producto
            FROM detalles_pedido dp
            JOIN productos pr ON dp.id_producto = pr.id_producto
            WHERE dp.id_pedido = %s
            """
            productos_db = db.execute_query(query_productos, (p["id_pedido"],), fetch=True)
            
            pedido["productos"] = []
            for prod in productos_db:
                pedido["productos"].append({
                    "nombre": prod["nombre_producto"],
                    "cantidad": prod["cantidad"],
                    "precio": float(prod["precio_unitario"])
                })
            
            pedidos.append(pedido)
        
        return jsonify(pedidos)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/api/pedido/<int:pedido_id>/estado", methods=["PUT"])
def admin_api_cambiar_estado(pedido_id):
    if session.get("rol") != "admin":
        return jsonify({"error": "No autorizado"}), 403
    
    try:
        data = request.get_json()
        nuevo_estado = data.get("estado")
        
        if not nuevo_estado:
            return jsonify({"error": "Estado requerido"}), 400
        
        query = "UPDATE pedidos SET estado = %s WHERE id_pedido = %s"
        result = db.execute_query(query, (nuevo_estado, pedido_id))
        
        if result > 0:
            return jsonify({"success": True, "mensaje": f"Estado actualizado a {nuevo_estado}"})
        else:
            return jsonify({"error": "Pedido no encontrado"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Ruta para estadísticas del dashboard
@app.route("/admin/api/estadisticas")
def admin_api_estadisticas():
    if session.get("rol") != "admin":
        return jsonify({"error": "No autorizado"}), 403
    
    try:
        # Total de pedidos
        query_total = "SELECT COUNT(*) as total FROM pedidos"
        total_result = db.execute_query(query_total, fetch=True)
        total_pedidos = total_result[0]["total"] if total_result else 0
        
        # Pedidos pendientes
        query_pendientes = "SELECT COUNT(*) as pendientes FROM pedidos WHERE estado = 'Pendiente'"
        pendientes_result = db.execute_query(query_pendientes, fetch=True)
        pedidos_pendientes = pendientes_result[0]["pendientes"] if pendientes_result else 0
        
        # Pedidos entregados
        query_entregados = "SELECT COUNT(*) as entregados FROM pedidos WHERE estado = 'Entregado'"
        entregados_result = db.execute_query(query_entregados, fetch=True)
        pedidos_entregados = entregados_result[0]["entregados"] if entregados_result else 0
        
        # Ventas totales
        query_ventas = "SELECT SUM(total) as ventas_total FROM pedidos WHERE estado != 'Cancelado'"
        ventas_result = db.execute_query(query_ventas, fetch=True)
        ventas_total = float(ventas_result[0]["ventas_total"]) if ventas_result and ventas_result[0]["ventas_total"] else 0
        
        return jsonify({
            "total_pedidos": total_pedidos,
            "pedidos_pendientes": pedidos_pendientes,
            "pedidos_entregados": pedidos_entregados,
            "ventas_total": ventas_total
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# AQUÍ VA EL if __name__ == "__main__":
if __name__ == "__main__":
    print("🚀 Iniciando ComercioTech...")
    print(f"🔧 MySQL disponible: {'✅' if MYSQL_AVAILABLE else '❌'}")
    print(f"🔧 Redis disponible: {'✅' if REDIS_AVAILABLE else '❌'}")
    
    if not MYSQL_AVAILABLE:
        print("📝 Usando archivos JSON como fallback para datos")
    
    if not REDIS_AVAILABLE:
        print("📝 Usando sesiones Flask como fallback para cache")
    
    app.run(debug=True, host='0.0.0.0', port=5000)

