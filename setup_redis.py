# setup_redis.py - Configuración inicial para ComercioTech
import redis
import json
from datetime import datetime

def setup_redis_for_comerciotech():
    """Configuración específica para tu proyecto"""
    
    print("🔧 Configurando Redis para ComercioTech...")
    
    # Tu IP de VM
    VM_IP = "192.168.1.17"
    
    try:
        # Conectar a Redis en tu VM
        r = redis.Redis(
            host=VM_IP, 
            port=6379, 
            db=0, 
            decode_responses=True,
            socket_connect_timeout=10
        )
        
        # Verificar conexión
        r.ping()
        print(f"✅ Conexión exitosa a Redis en {VM_IP}:6379")
        
        # Limpiar datos previos
        print("🧹 Limpiando datos previos...")
        for pattern in ["carrito:*", "session:*", "cache:*"]:
            keys = r.keys(pattern)
            if keys:
                r.delete(*keys)
                print(f"   Eliminadas {len(keys)} keys de {pattern}")
        
        # Configurar datos de prueba
        print("📦 Configurando datos de prueba...")
        
        # 1. Carrito de prueba para usuario 2 (Valentina)
        carrito_test = {
            "producto:1": "2",  # 2 Notebooks
            "producto:2": "1",  # 1 Mouse
        }
        
        r.hmset("carrito:2", carrito_test)
        r.expire("carrito:2", 604800)  # 7 días
        print("   ✅ Carrito de prueba creado para usuario 2")
        
        # 2. Cache de productos desde tu productos.json
        try:
            with open("productos.json", "r", encoding="utf-8") as f:
                productos = json.load(f)
            
            # Convertir formato para cache
            productos_cache = []
            for p in productos:
                producto_cache = {
                    "id": p["id"],
                    "id_producto": p["id"],
                    "nombre": p["nombre"],
                    "precio": p["precio"],
                    "imagen": p["imagen"],
                    "imagen_url": p["imagen"],
                    "descripcion": p.get("descripcion", "Producto de alta calidad"),
                    "stock": p.get("stock", 10),
                    "categoria": p.get("categoria", "Tecnología")
                }
                productos_cache.append(producto_cache)
            
            r.setex("cache:productos:all", 600, json.dumps(productos_cache))
            print(f"   ✅ Cache inicializado con {len(productos_cache)} productos")
            
        except FileNotFoundError:
            print("   ⚠️ No se encontró productos.json, creando productos de ejemplo...")
            
            productos_ejemplo = [
                {
                    "id": 1, "id_producto": 1, "nombre": "Notebook Gamer",
                    "precio": 434333, "imagen": "notebook.jpg", "imagen_url": "notebook.jpg",
                    "descripcion": "Laptop de alto rendimiento para gaming",
                    "stock": 10, "categoria": "Computadores"
                },
                {
                    "id": 2, "id_producto": 2, "nombre": "Mouse Inalámbrico",
                    "precio": 14990, "imagen": "mouse.jpg", "imagen_url": "mouse.jpg",
                    "descripcion": "Mouse ergonómico con conectividad Bluetooth",
                    "stock": 25, "categoria": "Periféricos"
                },
                {
                    "id": 3, "id_producto": 3, "nombre": "Teclado Mecánico",
                    "precio": 29990, "imagen": "teclado.jpg", "imagen_url": "teclado.jpg",
                    "descripcion": "Teclado mecánico RGB para gaming",
                    "stock": 15, "categoria": "Periféricos"
                }
            ]
            
            r.setex("cache:productos:all", 600, json.dumps(productos_ejemplo))
            print(f"   ✅ Cache inicializado con {len(productos_ejemplo)} productos de ejemplo")
        
        # 3. Configuración del sistema
        config_sistema = {
            "version": "1.0.0",
            "setup_date": datetime.now().isoformat(),
            "vm_ip": VM_IP,
            "features": json.dumps(["carrito", "cache", "sesiones"])
        }
        
        r.hmset("sistema:config", config_sistema)
        print("   ✅ Configuración del sistema guardada")
        
        # Mostrar estadísticas finales
        print("\n📊 ESTADO FINAL:")
        print(f"   🛒 Carritos activos: {len(r.keys('carrito:*'))}")
        print(f"   🔐 Sesiones activas: {len(r.keys('session:*'))}")
        print(f"   ⚡ Caches activos: {len(r.keys('cache:*'))}")
        print(f"   🔑 Total de keys: {r.dbsize()}")
        
        # Información de memoria
        info = r.info('memory')
        print(f"   💾 Memoria usada: {info.get('used_memory_human', 'N/A')}")
        
        print(f"\n🎉 ¡Redis configurado exitosamente en {VM_IP}!")
        print("💡 Puedes ejecutar tu aplicación con: python app.py")
        
        return True
        
    except redis.ConnectionError:
        print(f"❌ No se puede conectar a Redis en {VM_IP}:6379")
        print("🔧 Verifica que:")
        print("   1. La VM esté encendida")
        print("   2. Redis esté ejecutándose en la VM")
        print("   3. El firewall permita conexiones al puerto 6379")
        print("   4. La IP sea correcta en tu código")
        return False
        
    except Exception as e:
        print(f"❌ Error configurando Redis: {e}")
        return False

def test_redis_integration():
    """Prueba la integración completa"""
    print("\n🧪 PROBANDO INTEGRACIÓN...")
    
    VM_IP = "192.168.1.17"
    
    try:
        # Importar y probar tu RedisManager
        from redis_manager import create_redis_manager
        
        # Crear instancia
        redis_manager = create_redis_manager(host=VM_IP, port=6379)
        
        if not redis_manager.available:
            print("❌ RedisManager no se pudo conectar")
            return False
        
        print("✅ RedisManager conectado exitosamente")
        
        # Probar operaciones del carrito
        print("🛒 Probando operaciones del carrito...")
        
        # Agregar productos al carrito
        redis_manager.agregar_al_carrito(2, 1, 1)  # Usuario 2, Producto 1, 1 unidad
        redis_manager.agregar_al_carrito(2, 2, 2)  # Usuario 2, Producto 2, 2 unidades
        
        # Obtener carrito
        carrito = redis_manager.get_carrito(2)
        print(f"   Carrito usuario 2: {carrito}")
        
        # Probar cache
        print("⚡ Probando cache...")
        productos_cache = redis_manager.obtener_productos_cache()
        if productos_cache:
            print(f"   Cache encontrado: {len(productos_cache)} productos")
        else:
            print("   Cache vacío (normal si es la primera vez)")
        
        # Obtener estadísticas
        print("📊 Probando estadísticas...")
        stats = redis_manager.get_stats()
        print(f"   Stats: {stats}")
        
        print("🎉 ¡Todas las pruebas pasaron!")
        return True
        
    except ImportError:
        print("❌ No se pudo importar redis_manager.py")
        print("💡 Asegúrate de que el archivo redis_manager.py esté en el mismo directorio")
        return False
    except Exception as e:
        print(f"❌ Error en las pruebas: {e}")
        return False

def show_next_steps():
    """Muestra los próximos pasos"""
    print("\n" + "="*60)
    print("🎯 PRÓXIMOS PASOS:")
    print("="*60)
    print("1. 🚀 Ejecuta tu aplicación:")
    print("   python app.py")
    print()
    print("2. 🌐 Ve a tu navegador:")
    print("   http://localhost:5000")
    print()
    print("3. 🔐 Inicia sesión:")
    print("   Email: cliente@correo.cl")
    print("   Password: 1234")
    print()
    print("4. 🛒 Prueba el carrito:")
    print("   - Agrega productos")
    print("   - Cierra el navegador")
    print("   - Vuelve a abrir -> el carrito persiste!")
    print()
    print("5. 📊 Ve estadísticas de Redis:")
    print("   http://localhost:5000/debug/redis")
    print("   (Solo como admin: admin@tienda.cl / admin@tienda.cl)")
    print()
    print("6. 🔍 Monitorea Redis en tiempo real:")
    print("   python monitor_redis.py")
    print()
    print("7. 🧹 Limpia datos expirados:")
    print("   POST http://localhost:5000/admin/redis/cleanup")
    print("="*60)

if __name__ == "__main__":
    print("🚀 SETUP DE REDIS PARA COMERCIOTECH")
    print("="*60)
    
    # Ejecutar configuración
    if setup_redis_for_comerciotech():
        
        # Ejecutar pruebas
        if test_redis_integration():
            
            # Mostrar próximos pasos
            show_next_steps()
            
        else:
            print("\n❌ Las pruebas fallaron. Revisa la configuración.")
    else:
        print("\n❌ Configuración fallida. Revisa la conexión a Redis.")