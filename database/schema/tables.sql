-- Tabla de facultades (dimension)
CREATE TABLE facultades (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL UNIQUE,
    sigla VARCHAR(20),
    sede VARCHAR(50) DEFAULT 'Central',
    descripcion TEXT,
    activo BOOLEAN DEFAULT TRUE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de categorías jerárquicas (dimension)
CREATE TABLE categorias (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    padre_id INTEGER REFERENCES categorias(id),
    nivel INTEGER DEFAULT 0,
    ruta VARCHAR(500), -- Para búsquedas jerárquicas rápidas
    descripcion TEXT,
    color VARCHAR(7) DEFAULT '#3498db',
    icono VARCHAR(50),
    activo BOOLEAN DEFAULT TRUE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(nombre, padre_id)
);

-- Tabla principal de fragmentos (hechos)
CREATE TABLE fragmentos_conocimiento (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contenido TEXT NOT NULL,
    contenido_vector TEXT, -- Para full-text search
    categoria_id INTEGER REFERENCES categorias(id),
    facultad_id INTEGER REFERENCES facultades(id),
    metadata JSONB DEFAULT '{}',
    palabras_clave VARCHAR(500)[], -- Array para búsqueda rápida
    embedding_vector FLOAT[], -- Para búsqueda vectorial (si agregas pgvector después)
    relevancia FLOAT DEFAULT 1.0,
    usado_count INTEGER DEFAULT 0,
    fecha_ingesta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1
);

-- Tabla de logs del sistema (sin datos de usuario)
CREATE TABLE sistema_logs (
    id BIGSERIAL PRIMARY KEY,
    nivel VARCHAR(20) NOT NULL CHECK (nivel IN ('DEBUG', 'INFO', 'WARNING', 'ERROR')),
    modulo VARCHAR(100),
    accion VARCHAR(50),
    mensaje TEXT NOT NULL,
    datos JSONB DEFAULT '{}',
    ip_hash VARCHAR(64), -- Hash para anonimizar IPs
    duracion_ms INTEGER,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de estadísticas anónimas para analítica
CREATE TABLE estadisticas_anonimas (
    id BIGSERIAL PRIMARY KEY,
    tipo_consulta VARCHAR(50),
    facultad_id INTEGER,
    categoria_id INTEGER,
    palabras_clave VARCHAR(100)[],
    hora_dia INTEGER, -- 0-23
    dia_semana INTEGER, -- 1-7
    mes INTEGER,
    año INTEGER,
    consultas_count INTEGER DEFAULT 1,
    sin_respuesta_count INTEGER DEFAULT 0,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tipo_consulta, facultad_id, categoria_id, hora_dia, dia_semana, mes, año)
);
