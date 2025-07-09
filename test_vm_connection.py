# test_vm_connection.py
# Script para probar conectividad con la VM

import socket
import sys

def test_port(host, port, service_name):
    """Probar conexión a un puerto específico"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✅ {service_name} ({host}:{port}) - CONECTADO")
            return True
        else:
            print(f"❌ {service_name} ({host}:{port}) - NO DISPONIBLE")
            return False
    except Exception as e:
        print(f"❌ {service_name} ({host}:{port}) - ERROR: {e}")
        return False

def test_mysql_connection(host):
    """Probar conexión específica a MySQL"""
    configs = [
        {
            'host': host,
            'user': 'root',
            'password': '1234',
            'database': 'comerciotech_db',
            'port': 3306,
            'connection_timeout': 5
        }
    ]
    
    for i, config in enumerate(configs):
        try:
            import mysql.connector
            
            conn = mysql.connector.connect(**config)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM usuarios")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            user = config['user']
            print(f"✅ MySQL - CONEXIÓN EXITOSA con usuario '{user}' - {result[0]} usuarios encontrados")
            return True
            
        except Exception as e:
            user = config['user']
            print(f"❌ MySQL - ERROR con usuario '{user}': {e}")
            return False
    
    return False

def test_redis_connection(host):
    """Probar conexión específica a Redis"""
    try:
        import redis
        
        r = redis.Redis(host=host, port=6379, db=0, decode_responses=True, socket_connect_timeout=5)
        response = r.ping()
        
        if response:
            print(f"✅ Redis - CONEXIÓN EXITOSA")
            # Probar escribir y leer
            r.set("test_key", "ComercioTech")
            value = r.get("test_key")
            print(f"✅ Redis - Test write/read: {value}")
            r.delete("test_key")
            return True
        else:
            print(f"❌ Redis - SIN RESPUESTA")
            return False
            
    except Exception as e:
        print(f"❌ Redis - ERROR: {e}")
        return False

def main():
    # IP de tu VM Ubuntu
    VM_IP = "192.168.1.6"
    
    print(f"🔍 Probando conectividad con VM {VM_IP}...\n")
    
    # Probar conectividad básica
    print("📡 Probando conectividad de puertos:")
    mysql_port_ok = test_port(VM_IP, 3306, "MariaDB")
    redis_port_ok = test_port(VM_IP, 6379, "Redis")
    
    print("\n🔐 Probando autenticación y funcionalidad:")
    
    # Probar conexiones específicas
    if mysql_port_ok:
        mysql_ok = test_mysql_connection(VM_IP)
    else:
        mysql_ok = False
    
    if redis_port_ok:
        redis_ok = test_redis_connection(VM_IP)
    else:
        redis_ok = False
    
    print(f"\n📊 RESUMEN:")
    print(f"   MySQL: {'✅ FUNCIONANDO' if mysql_ok else '❌ CON PROBLEMAS'}")
    print(f"   Redis: {'✅ FUNCIONANDO' if redis_ok else '❌ CON PROBLEMAS'}")
    
    if mysql_ok and redis_ok:
        print(f"\n🎉 ¡CONEXIÓN COMPLETA EXITOSA!")
        print(f"💡 Puedes actualizar tu app.py con VM_IP = '{VM_IP}'")
    else:
        print(f"\n⚠️  Hay problemas de conectividad.")
        print(f"🔧 Verifica que la VM esté encendida")
        print(f"🔧 Verifica firewall: sudo ufw status")

if __name__ == "__main__":
    main()