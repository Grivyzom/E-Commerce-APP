# monitor_redis.py - Monitor simple para ComercioTech
import redis
import json
import time
import os
from datetime import datetime

class RedisMonitorSimple:
    def __init__(self, vm_ip="192.168.1.17"):
        self.vm_ip = vm_ip
        try:
            self.r = redis.Redis(
                host=vm_ip, 
                port=6379, 
                db=0, 
                decode_responses=True,
                socket_connect_timeout=10
            )
            self.r.ping()
            self.connected = True
            print(f"✅ Conectado a Redis en {vm_ip}:6379")
        except:
            self.connected = False
            print(f"❌ No se puede conectar a Redis en {vm_ip}:6379")
    
    def clear_screen(self):
        """Limpiar pantalla"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def get_carrito_info(self):
        """Información de carritos"""
        carritos = []
        for key in self.r.keys("carrito:*"):
            user_id = key.split(":")[-1]
            carrito_data = self.r.hgetall(key)
            ttl = self.r.ttl(key)
            
            total_productos = 0
            productos_detalle = []
            
            for prod_key, cantidad in carrito_data.items():
                cantidad_int = int(cantidad)
                total_productos += cantidad_int
                
                # Extraer ID del producto
                if prod_key.startswith("producto:"):
                    prod_id = prod_key.replace("producto:", "")
                else:
                    prod_id = prod_key
                
                productos_detalle.append(f"Producto {prod_id}: {cantidad_int}")
            
            carritos.append({
                "user_id": user_id,
                "total_items": total_productos,
                "productos": productos_detalle,
                "ttl": ttl
            })
        
        return carritos
    
    def get_cache_info(self):
        """Información de cache"""
        cache_key = "cache:productos:all"
        if self.r.exists(cache_key):
            ttl = self.r.ttl(cache_key)
            cache_data = self.r.get(cache_key)
            
            try:
                productos = json.loads(cache_data)
                return {
                    "activo": True,
                    "productos_count": len(productos),
                    "ttl": ttl,
                    "size_kb": len(cache_data) / 1024
                }
            except:
                return {"activo": False, "error": "Cache corrupto"}
        else:
            return {"activo": False}
    
    def get_session_info(self):
        """Información de sesiones"""
        sesiones = []
        for key in self.r.keys("session:*"):
            session_data = self.r.hgetall(key)
            ttl = self.r.ttl(key)
            
            sesiones.append({
                "user": session_data.get("nombre", "Unknown"),
                "email": session_data.get("email", "Unknown"),
                "rol": session_data.get("rol", "Unknown"),
                "ttl": ttl
            })
        
        return sesiones
    
    def format_ttl(self, ttl):
        """Formatear TTL"""
        if ttl == -1:
            return "Sin expiración"
        elif ttl == -2:
            return "Expirado"
        else:
            hours = ttl // 3600
            minutes = (ttl % 3600) // 60
            seconds = ttl % 60
            
            if hours > 0:
                return f"{hours}h {minutes}m"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
    
    def display_dashboard(self):
        """Dashboard principal"""
        if not self.connected:
            print("❌ Redis no está conectado")
            return
        
        self.clear_screen()
        
        # Header
        print("🎯 REDIS MONITOR - COMERCIOTECH")
        print("="*50)
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔗 Conectado a: {self.vm_ip}:6379")
        print("="*50)
        
        # Estadísticas generales
        try:
            info = self.r.info()
            total_keys = self.r.dbsize()
            
            print("📊 ESTADÍSTICAS GENERALES:")
            print(f"   🔑 Total de keys: {total_keys}")
            print(f"   💾 Memoria usada: {info.get('used_memory_human', 'N/A')}")
            print(f"   🔗 Conexiones: {info.get('connected_clients', 0)}")
            print()
        except Exception as e:
            print(f"❌ Error obteniendo estadísticas: {e}")
            print()
        
        # Carritos
        try:
            carritos = self.get_carrito_info()
            print("🛒 CARRITOS ACTIVOS:")
            if carritos:
                for carrito in carritos:
                    print(f"   👤 Usuario {carrito['user_id']}: {carrito['total_items']} items")
                    print(f"      Expira en: {self.format_ttl(carrito['ttl'])}")
                    for producto in carrito['productos']:
                        print(f"      • {producto}")
                    print()
            else:
                print("   (No hay carritos activos)")
            print()
        except Exception as e:
            print(f"❌ Error obteniendo carritos: {e}")
            print()
        
        # Cache
        try:
            cache_info = self.get_cache_info()
            print("⚡ CACHE DE PRODUCTOS:")
            if cache_info.get("activo"):
                print(f"   📦 {cache_info['productos_count']} productos cacheados")
                print(f"   💾 Tamaño: {cache_info['size_kb']:.1f} KB")
                print(f"   ⏱️ Expira en: {self.format_ttl(cache_info['ttl'])}")
            else:
                print("   (Cache vacío)")
            print()
        except Exception as e:
            print(f"❌ Error obteniendo cache: {e}")
            print()
        
        # Sesiones
        try:
            sesiones = self.get_session_info()
            print("👥 SESIONES ACTIVAS:")
            if sesiones:
                for sesion in sesiones:
                    print(f"   🔐 {sesion['user']} ({sesion['rol']})")
                    print(f"      Email: {sesion['email']}")
                    print(f"      Expira en: {self.format_ttl(sesion['ttl'])}")
                    print()
            else:
                print("   (No hay sesiones activas)")
            print()
        except Exception as e:
            print(f"❌ Error obteniendo sesiones: {e}")
            print()
        
        print("="*50)
        print("🔄 Actualizando cada 5 segundos...")
        print("💡 Presiona Ctrl+C para salir")
    
    def run_monitor(self):
        """Ejecutar monitor en bucle"""
        if not self.connected:
            print("🔧 Para usar este monitor:")
            print("   1. Verifica que Redis esté ejecutándose en tu VM")
            print("   2. Verifica que la IP sea correcta")
            print("   3. Verifica que el puerto 6379 esté abierto")
            return
        
        try:
            while True:
                self.display_dashboard()
                time.sleep(5)
        except KeyboardInterrupt:
            print("\n👋 Monitor detenido")
    
    def show_manual_commands(self):
        """Mostrar comandos manuales de Redis"""
        print("\n📚 COMANDOS ÚTILES DE REDIS:")
        print("="*50)
        print("Ver todas las keys:")
        print(f"  redis-cli -h {self.vm_ip} KEYS '*'")
        print()
        print("Ver carritos:")
        print(f"  redis-cli -h {self.vm_ip} KEYS 'carrito:*'")
        print()
        print("Ver contenido de carrito:")
        print(f"  redis-cli -h {self.vm_ip} HGETALL carrito:2")
        print()
        print("Ver cache de productos:")
        print(f"  redis-cli -h {self.vm_ip} GET cache:productos:all")
        print()
        print("Ver estadísticas:")
        print(f"  redis-cli -h {self.vm_ip} INFO")
        print()
        print("Limpiar todo:")
        print(f"  redis-cli -h {self.vm_ip} FLUSHDB")
        print("="*50)
    
    def interactive_menu(self):
        """Menú interactivo simple"""
        while True:
            print(f"\n🎯 REDIS MONITOR - {self.vm_ip}:6379")
            print("="*40)
            print("1. 📊 Ver dashboard en tiempo real")
            print("2. 📚 Ver comandos útiles")
            print("3. 🧪 Probar conexión")
            print("4. 🧹 Limpiar datos expirados")
            print("5. 🚪 Salir")
            print("="*40)
            
            choice = input("Selecciona una opción (1-5): ")
            
            if choice == "1":
                print("\n🔄 Iniciando monitor (Ctrl+C para detener)...")
                self.run_monitor()
                
            elif choice == "2":
                self.show_manual_commands()
                input("\nPresiona Enter para continuar...")
                
            elif choice == "3":
                self.test_connection()
                input("\nPresiona Enter para continuar...")
                
            elif choice == "4":
                self.clean_expired_data()
                input("\nPresiona Enter para continuar...")
                
            elif choice == "5":
                print("👋 ¡Hasta luego!")
                break
                
            else:
                print("❌ Opción inválida")
    
    def test_connection(self):
        """Probar conexión a Redis"""
        print("\n🧪 PROBANDO CONEXIÓN...")
        
        if not self.connected:
            print("❌ No hay conexión a Redis")
            return
        
        try:
            # Test básico
            self.r.set("test:monitor", "funcionando")
            value = self.r.get("test:monitor")
            assert value == "funcionando"
            self.r.delete("test:monitor")
            print("✅ Test básico: OK")
            
            # Test hash (carrito)
            self.r.hset("test:carrito", "producto:1", 5)
            cantidad = self.r.hget("test:carrito", "producto:1")
            assert int(cantidad) == 5
            self.r.delete("test:carrito")
            print("✅ Test hash (carrito): OK")
            
            # Test JSON (cache)
            data = {"test": "cache"}
            self.r.set("test:cache", json.dumps(data))
            retrieved = json.loads(self.r.get("test:cache"))
            assert retrieved["test"] == "cache"
            self.r.delete("test:cache")
            print("✅ Test JSON (cache): OK")
            
            # Test TTL
            self.r.setex("test:ttl", 10, "expira")
            ttl = self.r.ttl("test:ttl")
            assert ttl > 0
            self.r.delete("test:ttl")
            print("✅ Test TTL: OK")
            
            print("🎉 Todas las pruebas pasaron!")
            
        except Exception as e:
            print(f"❌ Error en pruebas: {e}")
    
    def clean_expired_data(self):
        """Limpiar datos expirados"""
        print("\n🧹 LIMPIANDO DATOS EXPIRADOS...")
        
        if not self.connected:
            print("❌ No hay conexión a Redis")
            return
        
        try:
            expired_count = 0
            
            # Revisar carritos
            for key in self.r.keys("carrito:*"):
                ttl = self.r.ttl(key)
                if ttl == -2:  # Expirado
                    self.r.delete(key)
                    expired_count += 1
                elif ttl == -1:  # Sin expiración, agregar una
                    self.r.expire(key, 604800)  # 7 días
            
            # Revisar sesiones
            for key in self.r.keys("session:*"):
                ttl = self.r.ttl(key)
                if ttl == -2:  # Expirado
                    self.r.delete(key)
                    expired_count += 1
                elif ttl == -1:  # Sin expiración, agregar una
                    self.r.expire(key, 86400)  # 24 horas
            
            print(f"✅ Limpieza completada: {expired_count} elementos eliminados")
            
        except Exception as e:
            print(f"❌ Error en limpieza: {e}")

def main():
    print("🚀 MONITOR DE REDIS PARA COMERCIOTECH")
    print("="*50)
    
    # Detectar IP de la VM
    vm_ip = "192.168.1.17"  # Tu IP por defecto
    
    # Permitir cambiar la IP
    user_ip = input(f"IP de tu VM Redis (Enter para usar {vm_ip}): ").strip()
    if user_ip:
        vm_ip = user_ip
    
    # Crear monitor
    monitor = RedisMonitorSimple(vm_ip)
    
    if monitor.connected:
        monitor.interactive_menu()
    else:
        print(f"\n🔧 Para conectar a Redis en {vm_ip}:")
        print("1. Verifica que la VM esté encendida")
        print("2. Verifica que Redis esté ejecutándose:")
        print("   sudo systemctl status redis-server")
        print("3. Si no está ejecutándose:")
        print("   sudo systemctl start redis-server")
        print("4. Verifica el firewall:")
        print("   sudo ufw allow 6379")

if __name__ == "__main__":
    main()