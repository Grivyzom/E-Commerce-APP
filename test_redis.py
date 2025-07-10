# test_redis.py
# Script simple para verificar que Redis funciona

import redis
import json
from datetime import datetime

def test_redis_connection():
    """Prueba básica de conexión a Redis"""
    try:
        # Conectar a Redis local
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
        # Hacer ping
        if r.ping():
            print("✅ Redis está funcionando correctamente")
            
            # Prueba de escritura y lectura
            r.set("test_key", "¡Hola Redis!")
            value = r.get("test_key")
            print(f"✅ Test write/read: {value}")
            
            # Prueba con datos JSON
            user_data = {
                "name": "Juan Pérez",
                "email": "juan@email.com",
                "carrito": ["producto1", "producto2"]
            }
            r.set("user:123", json.dumps(user_data))
            stored_data = json.loads(r.get("user:123"))
            print(f"✅ Test JSON: {stored_data['name']}")
            
            # Limpiar datos de prueba
            r.delete("test_key", "user:123")
            print("✅ Todas las pruebas pasaron")
            return True
        else:
            print("❌ Redis no responde al ping")
            return False
            
    except redis.ConnectionError:
        print("❌ No se puede conectar a Redis")
        print("💡 Asegúrate de que Redis esté ejecutándose:")
        print("   - Windows: redis-server")
        print("   - macOS/Linux: redis-server o sudo systemctl start redis")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Probando conexión a Redis...")
    test_redis_connection()