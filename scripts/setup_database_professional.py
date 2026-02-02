#!/usr/bin/env python3
"""
Setup simplificado para base de datos
"""
import asyncpg
import asyncio
import sys

async def main():
    print("🗄️  Configurando base de datos UNSA...")

    db_config = {
        "host": "localhost",
        "database": "unsa_knowledge_db",
        "user": "unsa_admin",
        "password": "unsa_password"
    }

    try:
        # Intentar conectar
        conn = await asyncpg.connect(**db_config)
        print("✅ Conectado a la base de datos")

        # Aplicar migración
        with open("database/migrations/migration_001_initial.sql", "r") as f:
            sql = f.read()

        await conn.execute(sql)
        print("✅ Esquema creado")

        # Aplicar índices
        with open("database/schema/indexes.sql", "r") as f:
            sql = f.read()

        await conn.execute(sql)
        print("✅ Índices creados")

        # Verificar
        count = await conn.fetchval("SELECT COUNT(*) FROM fragmentos_conocimiento")
        print(f"📊 Fragmentos en DB: {count}")

        await conn.close()

    except asyncpg.InvalidCatalogNameError:
        print("❌ La base de datos no existe")
        print("\n📋 Ejecuta primero:")
        print("su - postgres -c 'createdb unsa_knowledge_db'")
        print("su - postgres -c \"psql -c \\\"CREATE USER unsa_admin WITH PASSWORD 'unsa_password';\\\"\"")
        print("su - postgres -c 'psql -c \"GRANT ALL PRIVILEGES ON DATABASE unsa_knowledge_db TO unsa_admin;\"'")

    except FileNotFoundError as e:
        print(f"❌ Archivo no encontrado: {e}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
