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
    """
    Finalizar compra con invalidación de cache Redis
    """
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
            
            # 🎯 MEJORADO: Invalidar caches relacionados con pedidos
            try:
                # Limpiar cache de pedidos del usuario
                redis_manager.invalidar_cache_pedidos_usuario(user_id)
                
                # Limpiar estadísticas del usuario
                redis_manager.limpiar_cache_pedidos_usuario(user_id)
                
                # Crear notificación
                redis_manager.notificar_cambio_estado_pedido(pedido_id, user_id, "Pendiente")
                
                print(f"🔄 Cache invalidado correctamente para usuario {user_id}")
                
            except Exception as cache_error:
                print(f"⚠️ Error invalidando cache (no crítico): {cache_error}")
            
            # 🎯 MEJORADO: Vaciar carrito después de compra exitosa
            redis_manager.vaciar_carrito(user_id)
            
            # Cachear el nuevo pedido inmediatamente para mejor UX
            try:
                nuevo_pedido = {
                    "id_pedido": pedido_id,
                    "fecha_pedido": datetime.now(),
                    "direccion_envio": direccion,
                    "total": total,
                    "estado": "Pendiente",
                    "productos": ", ".join([f"{carrito[str(p['id_producto'])]}x {p['nombre']}" for p in productos]),
                    "detalles": [
                        {
                            "id_producto": p["id_producto"],
                            "nombre_producto": p["nombre"],
                            "cantidad": carrito[str(p['id_producto'])],
                            "precio_unitario": float(p["precio"])
                        } for p in productos
                    ]
                }
                
                # Cachear el detalle del nuevo pedido
                redis_manager.cache_detalle_pedido(pedido_id, user_id, nuevo_pedido)
                
            except Exception as cache_error:
                print(f"⚠️ Error cacheando nuevo pedido: {cache_error}")
            
            flash(f"¡Pedido #{pedido_id} creado exitosamente!", "success")
            return render_template("finalizado.html", pedido_id=pedido_id)
            
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


@app.route("/cancelar_pedido/<int:pedido_id>", methods=["POST"])
def cancelar_pedido(pedido_id):
    """
    Cancelar un pedido (solo si está en estado Pendiente)
    """
    if "user_id" not in session:
        return jsonify({"error": "No autorizado"}), 401
    
    user_id = session["user_id"]
    
    try:
        # Verificar que el pedido pertenece al usuario y se puede cancelar
        query_verificar = """
        SELECT id_pedido, estado FROM pedidos 
        WHERE id_pedido = %s AND id_usuario = %s AND estado = 'Pendiente'
        """
        
        pedido = db.execute_query(query_verificar, (pedido_id, user_id), fetch=True)
        
        if not pedido:
            return jsonify({"error": "Pedido no encontrado o no se puede cancelar"}), 400
        
        # Actualizar estado del pedido
        query_cancelar = """
        UPDATE pedidos 
        SET estado = 'Cancelado' 
        WHERE id_pedido = %s AND id_usuario = %s
        """
        
        result = db.execute_query(query_cancelar, (pedido_id, user_id))
        
        if result:
            # Invalidar caches relacionados
            redis_manager.invalidar_cache_pedidos_usuario(user_id)
            redis_manager.invalidar_cache_detalle_pedido(pedido_id, user_id)
            
            # Crear notificación de cancelación
            redis_manager.notificar_cambio_estado_pedido(pedido_id, user_id, "Cancelado")
            
            return jsonify({
                "success": True,
                "mensaje": "Pedido cancelado exitosamente"
            })
        else:
            return jsonify({"error": "No se pudo cancelar el pedido"}), 500
        
    except Exception as e:
        print(f"❌ Error cancelando pedido: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500

# ==========================================
# NUEVA RUTA PARA NOTIFICACIONES
# ==========================================

@app.route("/api/notificaciones")
def api_notificaciones():
    """
    Obtener notificaciones del usuario
    """
    if "user_id" not in session:
        return jsonify({"error": "No autorizado"}), 401
    
    user_id = session["user_id"]
    
    try:
        notificaciones = redis_manager.obtener_notificaciones_usuario(user_id, limit=20)
        
        return jsonify({
            "notificaciones": notificaciones,
            "total": len(notificaciones)
        })
        
    except Exception as e:
        print(f"❌ Error obteniendo notificaciones: {e}")
        return jsonify({"error": "Error interno"}), 500

@app.route("/api/notificaciones/marcar_leida/<int:pedido_id>", methods=["POST"])
def marcar_notificacion_leida(pedido_id):
    """
    Marcar una notificación como leída
    """
    if "user_id" not in session:
        return jsonify({"error": "No autorizado"}), 401
    
    user_id = session["user_id"]
    
    try:
        # Actualizar notificación en Redis
        notif_key = f"order_notification:{user_id}:{pedido_id}"
        notif_data = redis_manager.client.get(notif_key)
        
        if notif_data:
            notificacion = json.loads(notif_data)
            notificacion["leida"] = True
            redis_manager.client.setex(notif_key, 86400, json.dumps(notificacion))
            
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Notificación no encontrada"}), 404
        
    except Exception as e:
        print(f"❌ Error marcando notificación: {e}")
        return jsonify({"error": "Error interno"}), 500

# ==========================================
# MÉTRICAS Y ESTADÍSTICAS AVANZADAS
# ==========================================

@app.route("/admin/api/metricas_pedidos")
def admin_metricas_pedidos():
    """
    Métricas avanzadas de pedidos para administradores
    """
    if session.get("rol") != "admin":
        return jsonify({"error": "No autorizado"}), 403
    
    try:
        # Métricas de base de datos
        query_stats = """
        SELECT 
            COUNT(*) as total_pedidos,
            COUNT(CASE WHEN estado = 'Pendiente' THEN 1 END) as pendientes,
            COUNT(CASE WHEN estado = 'En preparación' THEN 1 END) as en_preparacion,
            COUNT(CASE WHEN estado = 'Enviado' THEN 1 END) as enviados,
            COUNT(CASE WHEN estado = 'Entregado' THEN 1 END) as entregados,
            COUNT(CASE WHEN estado = 'Cancelado' THEN 1 END) as cancelados,
            SUM(CASE WHEN estado != 'Cancelado' THEN total ELSE 0 END) as ventas_total,
            AVG(CASE WHEN estado != 'Cancelado' THEN total ELSE NULL END) as ticket_promedio,
            COUNT(CASE WHEN DATE(fecha_pedido) = CURDATE() THEN 1 END) as pedidos_hoy
        FROM pedidos
        """
        
        stats_db = db.execute_query(query_stats, fetch=True)
        
        # Métricas de Redis
        redis_stats = redis_manager.get_metricas_pedidos()
        
        # Pedidos por mes (últimos 6 meses)
        query_mensual = """
        SELECT 
            DATE_FORMAT(fecha_pedido, '%Y-%m') as mes,
            COUNT(*) as cantidad,
            SUM(CASE WHEN estado != 'Cancelado' THEN total ELSE 0 END) as ventas
        FROM pedidos 
        WHERE fecha_pedido >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(fecha_pedido, '%Y-%m')
        ORDER BY mes DESC
        """
        
        stats_mensual = db.execute_query(query_mensual, fetch=True)
        
        # Top productos más vendidos
        query_top_productos = """
        SELECT 
            pr.nombre,
            SUM(dp.cantidad) as total_vendido,
            SUM(dp.cantidad * dp.precio_unitario) as ingresos
        FROM detalles_pedido dp
        JOIN productos pr ON dp.id_producto = pr.id_producto
        JOIN pedidos p ON dp.id_pedido = p.id_pedido
        WHERE p.estado != 'Cancelado'
        GROUP BY pr.id_producto, pr.nombre
        ORDER BY total_vendido DESC
        LIMIT 10
        """
        
        top_productos = db.execute_query(query_top_productos, fetch=True)
        
        return jsonify({
            "estadisticas_generales": stats_db[0] if stats_db else {},
            "metricas_redis": redis_stats,
            "tendencia_mensual": stats_mensual,
            "top_productos": top_productos,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Error obteniendo métricas: {e}")
        return jsonify({"error": str(e)}), 500

# ==========================================
# OPTIMIZACIÓN DE CONSULTAS AUTOMÁTICA
# ==========================================

@app.route("/admin/api/optimizar_cache", methods=["POST"])
def admin_optimizar_cache():
    """
    Optimización manual del cache Redis
    """
    if session.get("rol") != "admin":
        return jsonify({"error": "No autorizado"}), 403
    
    try:
        # Configurar TTL automático
        redis_manager.configurar_expiracion_automatica()
        
        # Limpiar datos expirados
        resultado_limpieza = redis_manager.limpiar_datos_expirados()
        
        # Obtener métricas después de optimización
        metricas = redis_manager.get_metricas_pedidos()
        
        return jsonify({
            "success": True,
            "mensaje": "Cache optimizado exitosamente",
            "limpieza": resultado_limpieza,
            "metricas_actuales": metricas
        })
        
    except Exception as e:
        print(f"❌ Error optimizando cache: {e}")
        return jsonify({"error": str(e)}), 500

# ==========================================
# WEBHOOK PARA ACTUALIZACIONES DE ESTADO
# ==========================================

@app.route("/webhook/estado_pedido", methods=["POST"])
def webhook_estado_pedido():
    """
    Webhook para actualizar estado de pedidos desde sistemas externos
    """
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ["pedido_id", "nuevo_estado", "api_key"]):
            return jsonify({"error": "Datos incompletos"}), 400
        
        # Verificar API key (en producción usar algo más seguro)
        if data["api_key"] != "webhook_key_comerciotech_2025":
            return jsonify({"error": "API key inválida"}), 401
        
        pedido_id = data["pedido_id"]
        nuevo_estado = data["nuevo_estado"]
        
        # Estados válidos
        estados_validos = ["Pendiente", "En preparación", "Enviado", "Entregado", "Cancelado"]
        if nuevo_estado not in estados_validos:
            return jsonify({"error": "Estado inválido"}), 400
        
        # Actualizar estado en base de datos
        query_update = """
        UPDATE pedidos 
        SET estado = %s 
        WHERE id_pedido = %s
        """
        
        result = db.execute_query(query_update, (nuevo_estado, pedido_id))
        
        if result:
            # Obtener usuario del pedido para invalidar cache
            query_user = "SELECT id_usuario FROM pedidos WHERE id_pedido = %s"
            user_result = db.execute_query(query_user, (pedido_id,), fetch=True)
            
            if user_result:
                user_id = user_result[0]["id_usuario"]
                
                # Invalidar caches
                redis_manager.invalidar_cache_pedidos_usuario(user_id)
                redis_manager.invalidar_cache_detalle_pedido(pedido_id, user_id)
                
                # Crear notificación
                redis_manager.notificar_cambio_estado_pedido(pedido_id, user_id, nuevo_estado)
                
                print(f"🔄 Estado actualizado via webhook: Pedido {pedido_id} -> {nuevo_estado}")
                
                return jsonify({
                    "success": True,
                    "mensaje": f"Estado actualizado a {nuevo_estado}",
                    "pedido_id": pedido_id
                })
            else:
                return jsonify({"error": "Pedido no encontrado"}), 404
        else:
            return jsonify({"error": "No se pudo actualizar el estado"}), 500
        
    except Exception as e:
        print(f"❌ Error en webhook: {e}")
        return jsonify({"error": "Error interno"}), 500

# ==========================================
# TAREA EN SEGUNDO PLANO PARA LIMPIEZA
# ==========================================

import threading
import time

def tarea_limpieza_automatica():
    """
    Tarea que se ejecuta en segundo plano para limpiar cache expirado
    """
    while True:
        try:
            time.sleep(3600)  # Ejecutar cada hora
            print("🧹 Iniciando limpieza automática de cache...")
            
            redis_manager.configurar_expiracion_automatica()
            resultado = redis_manager.limpiar_datos_expirados()
            
            print(f"🧹 Limpieza completada: {resultado}")
            
        except Exception as e:
            print(f"❌ Error en limpieza automática: {e}")

# Iniciar tarea de limpieza al arrancar la aplicación
def iniciar_tareas_segundo_plano():
    """
    Iniciar tareas en segundo plano
    """
    if redis_manager.available:
        limpieza_thread = threading.Thread(target=tarea_limpieza_automatica, daemon=True)
        limpieza_thread.start()
        print("🚀 Tarea de limpieza automática iniciada")

# Llamar al final del archivo principal

# ==========================================
# NUEVAS RUTAS API PARA CARRITO (Agregar a app.py)
# ==========================================

@app.route("/api/carrito/agregar", methods=["POST"])
def api_agregar_carrito():
    """
    API para agregar producto al carrito sin recargar página
    """
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "error": "Debes iniciar sesión para agregar productos al carrito",
            "redirect": url_for("login")
        }), 401
    
    try:
        data = request.get_json()
        producto_id = data.get("producto_id")
        cantidad = data.get("cantidad", 1)
        
        if not producto_id:
            return jsonify({
                "success": False,
                "error": "ID de producto requerido"
            }), 400
        
        user_id = session["user_id"]
        
        # Verificar que el producto existe
        if db.available:
            query = "SELECT nombre, precio, stock FROM productos WHERE id_producto = %s AND activo = TRUE"
            producto = db.execute_query(query, (producto_id,), fetch=True)
            
            if not producto:
                return jsonify({
                    "success": False,
                    "error": "Producto no encontrado"
                }), 404
            
            producto_info = producto[0]
        else:
            # Fallback a JSON
            import os
            if os.path.exists("productos.json"):
                with open("productos.json", "r", encoding="utf-8") as f:
                    productos = json.load(f)
                producto_info = next((p for p in productos if p["id"] == producto_id), None)
                if not producto_info:
                    return jsonify({
                        "success": False,
                        "error": "Producto no encontrado"
                    }), 404
            else:
                return jsonify({
                    "success": False,
                    "error": "No hay productos disponibles"
                }), 500
        
        # Agregar al carrito
        redis_manager.agregar_al_carrito(user_id, producto_id, cantidad)
        
        # Obtener información actualizada del carrito
        carrito = redis_manager.get_carrito(user_id)
        total_items = sum(carrito.values()) if carrito else 0
        
        return jsonify({
            "success": True,
            "message": f"¡{producto_info['nombre']} agregado al carrito!",
            "producto": {
                "id": producto_id,
                "nombre": producto_info["nombre"],
                "cantidad_agregada": cantidad,
                "cantidad_total": carrito.get(str(producto_id), 0)
            },
            "carrito": {
                "total_items": total_items,
                "productos_count": len(carrito) if carrito else 0
            }
        })
        
    except Exception as e:
        print(f"❌ Error en API agregar carrito: {e}")
        return jsonify({
            "success": False,
            "error": "Error interno del servidor"
        }), 500

@app.route("/api/carrito/actualizar", methods=["POST"])
def api_actualizar_carrito():
    """
    API para actualizar cantidad de producto en carrito
    """
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "error": "No autorizado"
        }), 401
    
    try:
        data = request.get_json()
        producto_id = data.get("producto_id")
        accion = data.get("accion")  # "incrementar", "disminuir", "eliminar", "actualizar"
        cantidad = data.get("cantidad", 1)
        
        if not producto_id or not accion:
            return jsonify({
                "success": False,
                "error": "Datos incompletos"
            }), 400
        
        user_id = session["user_id"]
        carrito_actual = redis_manager.get_carrito(user_id)
        
        if str(producto_id) not in carrito_actual:
            return jsonify({
                "success": False,
                "error": "Producto no está en el carrito"
            }), 404
        
        cantidad_actual = carrito_actual[str(producto_id)]
        nueva_cantidad = cantidad_actual
        mensaje = ""
        
        if accion == "incrementar":
            nueva_cantidad = cantidad_actual + 1
            redis_manager.agregar_al_carrito(user_id, producto_id, 1)
            mensaje = "Cantidad incrementada"
        
        elif accion == "disminuir":
            nueva_cantidad = cantidad_actual - 1
            if nueva_cantidad > 0:
                redis_manager.actualizar_cantidad_carrito(user_id, producto_id, nueva_cantidad)
                mensaje = "Cantidad actualizada"
            else:
                redis_manager.quitar_del_carrito(user_id, producto_id)
                mensaje = "Producto eliminado del carrito"
                nueva_cantidad = 0
        
        elif accion == "eliminar":
            redis_manager.quitar_del_carrito(user_id, producto_id)
            mensaje = "Producto eliminado del carrito"
            nueva_cantidad = 0
        
        elif accion == "actualizar":
            if cantidad > 0:
                redis_manager.actualizar_cantidad_carrito(user_id, producto_id, cantidad)
                nueva_cantidad = cantidad
                mensaje = "Cantidad actualizada"
            else:
                redis_manager.quitar_del_carrito(user_id, producto_id)
                mensaje = "Producto eliminado del carrito"
                nueva_cantidad = 0
        
        # Obtener información actualizada del carrito
        carrito_actualizado = redis_manager.get_carrito(user_id)
        total_items = sum(carrito_actualizado.values()) if carrito_actualizado else 0
        
        # Calcular nuevo total del carrito (simplificado)
        total_precio = 0
        if carrito_actualizado and db.available:
            producto_ids = list(carrito_actualizado.keys())
            if producto_ids:
                placeholders = ','.join(['%s'] * len(producto_ids))
                query = f"SELECT id_producto, precio FROM productos WHERE id_producto IN ({placeholders})"
                productos_db = db.execute_query(query, producto_ids, fetch=True)
                
                for producto_db in productos_db:
                    cantidad_en_carrito = carrito_actualizado[str(producto_db['id_producto'])]
                    total_precio += float(producto_db["precio"]) * cantidad_en_carrito
        
        return jsonify({
            "success": True,
            "message": mensaje,
            "producto": {
                "id": producto_id,
                "nueva_cantidad": nueva_cantidad,
                "eliminado": nueva_cantidad == 0
            },
            "carrito": {
                "total_items": total_items,
                "productos_count": len(carrito_actualizado) if carrito_actualizado else 0,
                "total_precio": total_precio
            }
        })
        
    except Exception as e:
        print(f"❌ Error en API actualizar carrito: {e}")
        return jsonify({
            "success": False,
            "error": "Error interno del servidor"
        }), 500

@app.route("/api/carrito/vaciar", methods=["POST"])
def api_vaciar_carrito():
    """
    API para vaciar carrito completamente
    """
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "error": "No autorizado"
        }), 401
    
    try:
        user_id = session["user_id"]
        redis_manager.vaciar_carrito(user_id)
        
        return jsonify({
            "success": True,
            "message": "Carrito vaciado correctamente",
            "carrito": {
                "total_items": 0,
                "productos_count": 0,
                "total_precio": 0
            }
        })
        
    except Exception as e:
        print(f"❌ Error en API vaciar carrito: {e}")
        return jsonify({
            "success": False,
            "error": "Error interno del servidor"
        }), 500

@app.route("/api/carrito/info")
def api_info_carrito():
    """
    API para obtener información del carrito
    """
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "error": "No autorizado"
        }), 401
    
    try:
        user_id = session["user_id"]
        carrito = redis_manager.get_carrito(user_id)
        
        if not carrito:
            return jsonify({
                "success": True,
                "carrito": {
                    "total_items": 0,
                    "productos_count": 0,
                    "total_precio": 0,
                    "productos": []
                }
            })
        
        # Obtener detalles de productos
        productos_carrito = []
        total_precio = 0
        
        if db.available:
            producto_ids = list(carrito.keys())
            if producto_ids:
                placeholders = ','.join(['%s'] * len(producto_ids))
                query = f"SELECT * FROM productos WHERE id_producto IN ({placeholders})"
                productos_db = db.execute_query(query, producto_ids, fetch=True)
                
                for producto_db in productos_db:
                    cantidad = carrito[str(producto_db['id_producto'])]
                    subtotal = float(producto_db["precio"]) * cantidad
                    
                    productos_carrito.append({
                        "id": producto_db["id_producto"],
                        "nombre": producto_db["nombre"],
                        "precio": float(producto_db["precio"]),
                        "cantidad": cantidad,
                        "subtotal": subtotal,
                        "imagen": producto_db["imagen_url"]
                    })
                    total_precio += subtotal
        
        return jsonify({
            "success": True,
            "carrito": {
                "total_items": sum(carrito.values()),
                "productos_count": len(carrito),
                "total_precio": total_precio,
                "productos": productos_carrito
            }
        })
        
    except Exception as e:
        print(f"❌ Error en API info carrito: {e}")
        return jsonify({
            "success": False,
            "error": "Error interno del servidor"
        }), 500

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