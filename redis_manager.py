# redis_manager.py - Versión mejorada para ComercioTech
import redis
import json
import secrets
from datetime import datetime, timedelta
from flask import session

class RedisManager:
    """
    Gestor mejorado de Redis para ComercioTech
    Versión optimizada con mejor manejo de errores y funcionalidades adicionales
    """
    
    def __init__(self, redis_client=None):
        self.client = redis_client
        self.available = redis_client is not None
        
        if self.available:
            print("✅ RedisManager inicializado con Redis")
        else:
            print("⚠️ RedisManager usando fallback a sesiones Flask")
    
    # ==========================================
    # GESTIÓN DEL CARRITO (MEJORADA)
    # ==========================================
    
    def get_carrito(self, user_id):
        """
        Obtiene el carrito del usuario con manejo de errores mejorado
        """
        if not self.available:
            return session.get("carrito", {})
        
        try:
            carrito_key = f"carrito:{user_id}"
            carrito_data = self.client.hgetall(carrito_key)
            
            # Convertir formato Redis a formato esperado
            carrito = {}
            for key, cantidad in carrito_data.items():
                if key.startswith("producto:"):
                    producto_id = key.replace("producto:", "")
                    carrito[producto_id] = int(cantidad)
                else:
                    # Compatibilidad con formato anterior
                    carrito[key] = int(cantidad)
            
            print(f"🛒 Carrito obtenido para usuario {user_id}: {len(carrito)} productos")
            return carrito
            
        except Exception as e:
            print(f"❌ Error obteniendo carrito: {e}")
            return session.get("carrito", {})
    
    def agregar_al_carrito(self, user_id, producto_id, cantidad=1):
        """
        Agrega producto al carrito con mejor manejo
        """
        if not self.available:
            carrito = session.get("carrito", {})
            producto_key = str(producto_id)
            carrito[producto_key] = carrito.get(producto_key, 0) + cantidad
            session["carrito"] = carrito
            session.permanent = True
            print(f"🛒 Producto {producto_id} agregado al carrito (Flask): cantidad {carrito[producto_key]}")
            return
        
        try:
            carrito_key = f"carrito:{user_id}"
            producto_key = f"producto:{producto_id}"
            
            # Incrementar cantidad
            nueva_cantidad = self.client.hincrby(carrito_key, producto_key, cantidad)
            
            # Establecer expiración (7 días)
            self.client.expire(carrito_key, 604800)
            
            print(f"🛒 Producto {producto_id} agregado al carrito (Redis): cantidad {nueva_cantidad}")
            
        except Exception as e:
            print(f"❌ Error agregando al carrito: {e}")
            # Fallback automático
            carrito = session.get("carrito", {})
            producto_key = str(producto_id)
            carrito[producto_key] = carrito.get(producto_key, 0) + cantidad
            session["carrito"] = carrito
    
    def actualizar_cantidad_carrito(self, user_id, producto_id, nueva_cantidad):
        """
        Actualiza cantidad específica de un producto
        """
        if nueva_cantidad <= 0:
            self.quitar_del_carrito(user_id, producto_id)
            return
        
        if not self.available:
            carrito = session.get("carrito", {})
            producto_key = str(producto_id)
            carrito[producto_key] = nueva_cantidad
            session["carrito"] = carrito
            return
        
        try:
            carrito_key = f"carrito:{user_id}"
            producto_key = f"producto:{producto_id}"
            self.client.hset(carrito_key, producto_key, nueva_cantidad)
            self.client.expire(carrito_key, 604800)
            print(f"🛒 Cantidad actualizada para producto {producto_id}: {nueva_cantidad}")
            
        except Exception as e:
            print(f"❌ Error actualizando cantidad: {e}")
    
    def quitar_del_carrito(self, user_id, producto_id):
        """
        Elimina producto del carrito
        """
        if not self.available:
            carrito = session.get("carrito", {})
            producto_key = str(producto_id)
            if producto_key in carrito:
                del carrito[producto_key]
                session["carrito"] = carrito
            print(f"🗑️ Producto {producto_id} eliminado del carrito (Flask)")
            return
        
        try:
            carrito_key = f"carrito:{user_id}"
            producto_key = f"producto:{producto_id}"
            result = self.client.hdel(carrito_key, producto_key)
            print(f"🗑️ Producto {producto_id} eliminado del carrito (Redis): {result}")
            
        except Exception as e:
            print(f"❌ Error eliminando del carrito: {e}")
    
    def vaciar_carrito(self, user_id):
        """
        Vacía completamente el carrito
        """
        if not self.available:
            session["carrito"] = {}
            print(f"🧹 Carrito vaciado para usuario {user_id} (Flask)")
            return
        
        try:
            carrito_key = f"carrito:{user_id}"
            result = self.client.delete(carrito_key)
            print(f"🧹 Carrito vaciado para usuario {user_id} (Redis): {result}")
            
        except Exception as e:
            print(f"❌ Error vaciando carrito: {e}")
    
    # ==========================================
    # CACHE DE PRODUCTOS (MEJORADO)
    # ==========================================
    
    def cache_productos(self, productos):
        """
        Cachea productos con mejor manejo
        """
        if not self.available:
            return
        
        try:
            cache_key = "cache:productos:all"
            productos_json = json.dumps(productos, default=str)
            
            # Cachear por 10 minutos
            self.client.setex(cache_key, 600, productos_json)
            print(f"⚡ {len(productos)} productos cacheados por 10 minutos")
            
        except Exception as e:
            print(f"❌ Error cacheando productos: {e}")
    
    def obtener_productos_cache(self):
        """
        Obtiene productos desde cache
        """
        if not self.available:
            return None
        
        try:
            cache_key = "cache:productos:all"
            cached_data = self.client.get(cache_key)
            
            if cached_data:
                productos = json.loads(cached_data)
                print(f"⚡ {len(productos)} productos obtenidos desde cache")
                return productos
            
            print("📦 Cache de productos vacío")
            return None
            
        except Exception as e:
            print(f"❌ Error obteniendo productos desde cache: {e}")
            return None
    
    def invalidar_cache_productos(self):
        """
        Invalida el cache de productos (cuando se modifican)
        """
        if not self.available:
            return
        
        try:
            cache_key = "cache:productos:all"
            result = self.client.delete(cache_key)
            print(f"🔄 Cache de productos invalidado: {result}")
            
        except Exception as e:
            print(f"❌ Error invalidando cache: {e}")
    
    # ==========================================
    # SESIONES DE USUARIO (MEJORADA)
    # ==========================================
    
    def crear_sesion(self, user_data):
        """
        Crea sesión de usuario con mejor manejo
        """
        if not self.available:
            for key, value in user_data.items():
                session[key] = value
            session.permanent = True
            return "flask_session"
        
        try:
            session_token = secrets.token_urlsafe(32)
            session_key = f"session:{session_token}"
            
            # Preparar datos de sesión
            session_data = {
                "user_id": str(user_data.get("user_id", "")),
                "nombre": user_data.get("nombre", ""),
                "email": user_data.get("email", ""),
                "rol": user_data.get("rol", "cliente"),
                "created_at": datetime.now().isoformat()
            }
            
            # Guardar sesión por 24 horas
            self.client.hmset(session_key, session_data)
            self.client.expire(session_key, 86400)
            
            print(f"🔐 Sesión creada para: {user_data.get('nombre')}")
            return session_token
            
        except Exception as e:
            print(f"❌ Error creando sesión: {e}")
            # Fallback
            for key, value in user_data.items():
                session[key] = value
            return "flask_session"
    
    def obtener_sesion(self, session_token):
        """
        Obtiene datos de sesión
        """
        if not self.available or session_token == "flask_session":
            return dict(session)
        
        try:
            session_key = f"session:{session_token}"
            session_data = self.client.hgetall(session_key)
            
            if session_data:
                print(f"🔐 Sesión encontrada: {session_data.get('nombre', 'Usuario')}")
                return session_data
            
            print("🔐 Sesión no encontrada o expirada")
            return None
            
        except Exception as e:
            print(f"❌ Error obteniendo sesión: {e}")
            return None
    
    def cerrar_sesion(self, session_token):
        """
        Cierra sesión
        """
        if not self.available or session_token == "flask_session":
            session.clear()
            print("🚪 Sesión Flask cerrada")
            return
        
        try:
            session_key = f"session:{session_token}"
            result = self.client.delete(session_key)
            print(f"🚪 Sesión Redis cerrada: {result}")
            
        except Exception as e:
            print(f"❌ Error cerrando sesión: {e}")
    
    # ==========================================
    # ESTADÍSTICAS Y MONITOREO
    # ==========================================
    
    def get_stats(self):
        """
        Obtiene estadísticas completas de Redis
        """
        if not self.available:
            return {
                "status": "Redis no disponible",
                "using_fallback": True,
                "carritos_activos": 0,
                "sesiones_activas": 0,
                "cache_productos": "No disponible"
            }
        
        try:
            info = self.client.info()
            
            # Contar elementos
            carritos_activos = len(self.client.keys("carrito:*"))
            sesiones_activas = len(self.client.keys("session:*"))
            cache_productos_existe = self.client.exists("cache:productos:all")
            
            # TTL del cache
            cache_ttl = self.client.ttl("cache:productos:all") if cache_productos_existe else 0
            
            stats = {
                "status": "Conectado",
                "carritos_activos": carritos_activos,
                "sesiones_activas": sesiones_activas,
                "cache_productos": f"Activo ({cache_ttl}s)" if cache_productos_existe else "Vacío",
                "memoria_usada": info.get("used_memory_human", "N/A"),
                "conexiones_activas": info.get("connected_clients", 0),
                "total_keys": self.client.dbsize(),
                "comandos_procesados": info.get("total_commands_processed", 0),
                "hit_ratio": self._calculate_hit_ratio(info)
            }
            
            return stats
            
        except Exception as e:
            return {"status": f"Error: {e}", "using_fallback": True}
    
    def _calculate_hit_ratio(self, info):
        """Calcula ratio de hits/misses"""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        
        if total == 0:
            return "0%"
        
        ratio = (hits / total) * 100
        return f"{ratio:.1f}%"
    
    # ==========================================
    # UTILIDADES DE LIMPIEZA
    # ==========================================
    
    def limpiar_datos_expirados(self):
        """
        Limpia datos expirados manualmente
        """
        if not self.available:
            return {"message": "Redis no disponible"}
        
        try:
            carritos_limpiados = 0
            sesiones_limpiadas = 0
            
            # Limpiar carritos expirados
            for key in self.client.keys("carrito:*"):
                ttl = self.client.ttl(key)
                if ttl == -2:  # Expirado
                    self.client.delete(key)
                    carritos_limpiados += 1
                elif ttl == -1:  # Sin expiración, agregar una
                    self.client.expire(key, 604800)  # 7 días
            
            # Limpiar sesiones expiradas
            for key in self.client.keys("session:*"):
                ttl = self.client.ttl(key)
                if ttl == -2:  # Expirado
                    self.client.delete(key)
                    sesiones_limpiadas += 1
                elif ttl == -1:  # Sin expiración, agregar una
                    self.client.expire(key, 86400)  # 24 horas
            
            result = {
                "carritos_limpiados": carritos_limpiados,
                "sesiones_limpiadas": sesiones_limpiadas,
                "message": "Limpieza completada"
            }
            
            print(f"🧹 Limpieza: {carritos_limpiados} carritos, {sesiones_limpiadas} sesiones")
            return result
            
        except Exception as e:
            print(f"❌ Error en limpieza: {e}")
            return {"error": str(e)}


def create_redis_manager(host='localhost', port=6379):
    """
    Factory function para crear RedisManager
    """
    try:
        redis_client = redis.Redis(
            host=host,
            port=port,
            db=0,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        
        # Probar conexión
        redis_client.ping()
        print(f"🎉 Redis conectado en {host}:{port}")
        return RedisManager(redis_client)
        
    except Exception as e:
        print(f"⚠️ Redis no disponible ({host}:{port}): {e}")
        print("📝 Usando fallback a sesiones Flask")
        return RedisManager(None)