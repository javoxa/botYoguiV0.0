#!/usr/bin/env python3
"""
Inicializar PostgreSQL desde cualquier directorio
"""
import os
import sys
from pathlib import Path
import asyncio
import asyncpg

# Ir al directorio raíz
project_root = Path(__file__).parent.parent
os.chdir(project_root)

from dotenv import load_dotenv
load_dotenv('.env')

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://unsa_admin:unsa_password@localhost/unsa_knowledge_db")

async def init_db():
    print("📦 Inicializando base de datos UNSA...")

    try:
        # Conectar
        conn = await asyncpg.connect(DATABASE_URL)

        # Crear tabla simple
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS fragmentos_conocimiento (
                id SERIAL PRIMARY KEY,
                contenido TEXT NOT NULL,
                categoria VARCHAR(100) DEFAULT 'General',
                facultad VARCHAR(100) DEFAULT 'General',
                metadata JSONB DEFAULT '{}',
                fecha_ingesta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Crear índice para búsqueda
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_fragmentos_busqueda
            ON fragmentos_conocimiento USING gin(to_tsvector('spanish', contenido))
        """)

        # Contar registros existentes
        count = await conn.fetchval("SELECT COUNT(*) FROM fragmentos_conocimiento")

        if count == 0:
            # Insertar ejemplos si está vacía
            ejemplos = [
                ("La Universidad Nacional de Salta (UNSA) fue creada en 1972", "General", "UNSA"),
                ("Preinscripciones 2026: del 1 al 30 de septiembre", "Inscripción", "General"),
                ("Carrera de Medicina: 7 años de duración", "Carrera", "Salud"),
                ("Facultad de Ciencias Exactas ofrece Ingeniería en Informática", "Carrera", "Exactas"),
                ("Becas de ayuda económica disponibles para estudiantes", "Beca", "General"),
                ("Inicio de clases: marzo de cada año", "Calendario", "General"),
                ("Contacto administrativo: consultas@unsa.edu.ar", "Contacto", "General"),
                ("UNSA tiene sedes en Salta, Orán y Tartagal", "Ubicación", "General"),
            ]

            for contenido, categoria, facultad in ejemplos:
                await conn.execute("""
                    INSERT INTO fragmentos_conocimiento (contenido, categoria, facultad)
                    VALUES ($1, $2, $3)
                """, contenido, categoria, facultad)

            print(f"✅ Base de datos creada con {len(ejemplos)} ejemplos")
        else:
            print(f"✅ Base de datos ya tiene {count} registros")

        await conn.close()

    except asyncpg.InvalidCatalogNameError:
        print("❌ ERROR: La base de datos 'unsa_knowledge_db' no existe")
        print("\n📋 EJECUTA ESTOS COMANDOS PRIMERO (como usuario postgres):")
        print("""
su - postgres  # O: sudo -u postgres psql

# Luego en psql:
CREATE DATABASE unsa_knowledge_db;
CREATE USER unsa_admin WITH PASSWORD 'unsa_password';
GRANT ALL PRIVILEGES ON DATABASE unsa_knowledge_db TO unsa_admin;

# Conectarte a la DB:
\\c unsa_knowledge_db

# Dar permisos adicionales:
GRANT ALL ON SCHEMA public TO unsa_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO unsa_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO unsa_admin;
        """)
        sys.exit(1)

    except Exception as e:
        print(f"❌ ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(init_db())
