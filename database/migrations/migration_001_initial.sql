-- ====================================================
-- MIGRACIÓN 001: Esquema inicial en esquema dedicado
-- ====================================================

-- Si no existe el esquema, créalo (pero ya lo creamos antes)
CREATE SCHEMA IF NOT EXISTS unsa_esquema;

-- Cambiar al esquema unsa_esquema
SET search_path TO unsa_esquema;

-- ==================== TABLAS PRINCIPALES ====================

-- Tabla de facultades
CREATE TABLE facultades (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL UNIQUE,
    sigla VARCHAR(20),
    sede VARCHAR(50) DEFAULT 'Central',
    descripcion TEXT,
    activo BOOLEAN DEFAULT TRUE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de categorías jerárquicas
CREATE TABLE categorias (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    padre_id INTEGER REFERENCES categorias(id),
    nivel INTEGER DEFAULT 0,
    ruta VARCHAR(500),
    descripcion TEXT,
    color VARCHAR(7) DEFAULT '#3498db',
    activo BOOLEAN DEFAULT TRUE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(nombre, padre_id)
);

-- Tabla principal de conocimiento
CREATE TABLE fragmentos_conocimiento (
    id SERIAL PRIMARY KEY,
    contenido TEXT NOT NULL,
    contenido_tsvector TSVECTOR, -- Para full-text search
    categoria_id INTEGER REFERENCES categorias(id),
    facultad_id INTEGER REFERENCES facultades(id),
    metadata JSONB DEFAULT '{}',
    palabras_clave TEXT[],
    relevancia FLOAT DEFAULT 1.0,
    usado_count INTEGER DEFAULT 0,
    fuente VARCHAR(100) DEFAULT 'manual',
    fecha_ingesta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla para logs del sistema (sin datos personales)
CREATE TABLE sistema_logs (
    id BIGSERIAL PRIMARY KEY,
    nivel VARCHAR(20) NOT NULL CHECK (nivel IN ('DEBUG', 'INFO', 'WARNING', 'ERROR')),
    modulo VARCHAR(100),
    accion VARCHAR(50),
    mensaje TEXT NOT NULL,
    datos JSONB DEFAULT '{}',
    ip_hash VARCHAR(64), -- Hash anónimo de IP
    duracion_ms INTEGER,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== ÍNDICES OPTIMIZADOS ====================

-- Índices para fragmentos_conocimiento
CREATE INDEX idx_fragmentos_contenido_fts
ON fragmentos_conocimiento USING GIN(contenido_tsvector);

CREATE INDEX idx_fragmentos_palabras_clave
ON fragmentos_conocimiento USING GIN(palabras_clave);

CREATE INDEX idx_fragmentos_metadata
ON fragmentos_conocimiento USING GIN(metadata);

CREATE INDEX idx_fragmentos_categoria
ON fragmentos_conocimiento(categoria_id);

CREATE INDEX idx_fragmentos_facultad
ON fragmentos_conocimiento(facultad_id);

CREATE INDEX idx_fragmentos_fecha
ON fragmentos_conocimiento(fecha_ingesta DESC);

CREATE INDEX idx_fragmentos_relevancia
ON fragmentos_conocimiento(relevancia DESC, usado_count DESC);

-- Índices para categorías
CREATE INDEX idx_categorias_padre ON categorias(padre_id);
CREATE INDEX idx_categorias_nivel ON categorias(nivel);
CREATE INDEX idx_categorias_ruta ON categorias(ruta);

-- ==================== FUNCIONES Y TRIGGERS ====================

-- Función para actualizar el tsvector automáticamente
CREATE OR REPLACE FUNCTION actualizar_tsvector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.contenido_tsvector = to_tsvector('spanish_unaccent', NEW.contenido);
    NEW.fecha_actualizacion = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para mantener el tsvector actualizado
CREATE TRIGGER trigger_actualizar_tsvector
BEFORE INSERT OR UPDATE ON fragmentos_conocimiento
FOR EACH ROW EXECUTE FUNCTION actualizar_tsvector();

-- Función para actualizar rutas jerárquicas de categorías
CREATE OR REPLACE FUNCTION actualizar_ruta_categoria()
RETURNS TRIGGER AS $$
BEGIN
    NEW.ruta = (
        WITH RECURSIVE ruta_cte AS (
            SELECT id, nombre, CAST(nombre AS VARCHAR(500)) AS path
            FROM categorias
            WHERE id = NEW.id AND padre_id IS NULL
            UNION ALL
            SELECT c.id, c.nombre, rc.path || ' > ' || c.nombre
            FROM categorias c
            JOIN ruta_cte rc ON c.padre_id = rc.id
            WHERE c.id = NEW.id
        )
        SELECT path FROM ruta_cte ORDER BY LENGTH(path) DESC LIMIT 1
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para rutas de categorías
CREATE TRIGGER trigger_actualizar_ruta
BEFORE INSERT OR UPDATE ON categorias
FOR EACH ROW EXECUTE FUNCTION actualizar_ruta_categoria();

-- ==================== DATOS INICIALES ====================

-- Facultades de la UNSA
INSERT INTO facultades (nombre, sigla, sede, descripcion) VALUES
('Facultad de Ciencias Exactas', 'FCE', 'Central', 'Ciencias básicas, informática, matemáticas'),
('Facultad de Ingeniería', 'FI', 'Central', 'Ingenierías civil, industrial, electrónica'),
('Facultad de Ciencias de la Salud', 'FCS', 'Central', 'Medicina, enfermería, farmacia'),
('Facultad de Ciencias Económicas, Jurídicas y Sociales', 'FCEJS', 'Central', 'Derecho, economía, administración'),
('Facultad de Humanidades', 'FH', 'Central', 'Letras, filosofía, historia'),
('Facultad Regional Orán', 'FRO', 'Orán', 'Carreras regionales en Orán'),
('Facultad Regional Tartagal', 'FRT', 'Tartagal', 'Carreras regionales en Tartagal')
ON CONFLICT (nombre) DO NOTHING;

-- Categorías jerárquicas
INSERT INTO categorias (nombre, padre_id, nivel) VALUES
('UNSA', NULL, 0),
('Académico', 1, 1),
('Administrativo', 1, 1),
('Investigación', 1, 1),
('Extensión', 1, 1),
('Carreras de Grado', 2, 2),
('Carreras de Pregrado', 2, 2),
('Posgrado', 2, 2),
('Ingenierías', 6, 3),
('Licenciaturas', 6, 3),
('Tecnicaturas', 7, 3),
('Inscripción', 3, 2),
('Becas', 3, 2),
('Trámites', 3, 2),
('Calendario', 3, 2),
('Contacto', 3, 2)
ON CONFLICT (nombre, padre_id) DO NOTHING;

-- Fragmentos de conocimiento iniciales
INSERT INTO fragmentos_conocimiento (contenido, categoria_id, facultad_id, palabras_clave) VALUES
('La Universidad Nacional de Salta (UNSA) fue creada en 1972. Es una institución pública autónoma con sede central en Salta capital.', 1, 1, ARRAY['UNSA', 'universidad', 'creación', '1972', 'pública']),
('Las preinscripciones para el ciclo lectivo 2026 son del 1 al 30 de septiembre de 2025. Deben realizarse a través del sistema online en https://inscripciones.unsa.edu.ar', 12, 1, ARRAY['preinscripciones', '2026', 'septiembre', 'online', 'fechas']),
('La carrera de Medicina tiene una duración de 7 años (14 semestres) y se dicta en la Facultad de Ciencias de la Salud. Titulo: Médico.', 6, 3, ARRAY['medicina', 'carrera', '7 años', 'salud', 'médico']),
('La Facultad de Ciencias Exactas ofrece la carrera de Ingeniería en Informática con título intermedio de Analista Universitario en Sistemas (5 años).', 9, 1, ARRAY['ingeniería', 'informática', 'exactas', 'analista', 'sistemas']),
('Existen becas de ayuda económica para estudiantes de bajos recursos. Las solicitudes se abren en marzo de cada año. Requisitos: promedio mayor a 7, situación socioeconómica.', 13, 1, ARRAY['becas', 'ayuda económica', 'estudiantes', 'marzo', 'requisitos']),
('El inicio de clases para el ciclo 2026 está previsto para la primera semana de marzo. El calendario académico completo se publica en diciembre.', 15, 1, ARRAY['inicio', 'clases', 'marzo', '2026', 'calendario']),
('Para consultas administrativas: consultas@unsa.edu.ar - Teléfono: (0387) 425-5000. Horario de atención: Lunes a Viernes 8:00 a 20:00 hs.', 16, 1, ARRAY['contacto', 'email', 'teléfono', 'horario', 'consultas']),
('La UNSA cuenta con sedes en: Salta capital (Av. Bolivia 5150), Orán (Sarmiento 790) y Tartagal (Av. San Martín 825).', 1, 1, ARRAY['sedes', 'salta', 'orán', 'tartagal', 'direcciones']),
('La Facultad de Ingeniería ofrece las carreras de: Ingeniería Civil (5 años), Ingeniería Industrial (5 años), Ingeniería Electrónica (5 años).', 9, 2, ARRAY['ingeniería', 'civil', 'industrial', 'electrónica', 'carreras']),
('El calendario académico 2026 incluye: Inicio clases (marzo), Receso invernal (2 semanas en julio), Finalización (diciembre), Exámenes (febrero/marzo 2027).', 15, 1, ARRAY['calendario', 'académico', '2026', 'receso', 'exámenes'])
ON CONFLICT DO NOTHING;

-- ==================== VISTAS ÚTILES ====================

-- Vista para búsqueda rápida
CREATE OR REPLACE VIEW v_conocimiento_completo AS
SELECT
    fc.id,
    fc.contenido,
    fc.palabras_clave,
    c.nombre as categoria,
    c.ruta as categoria_ruta,
    f.nombre as facultad,
    f.sigla as facultad_sigla,
    fc.relevancia,
    fc.usado_count,
    fc.fecha_ingesta
FROM fragmentos_conocimiento fc
LEFT JOIN categorias c ON fc.categoria_id = c.id
LEFT JOIN facultades f ON fc.facultad_id = f.id
WHERE fc.activo = TRUE;

-- Vista para estadísticas
CREATE OR REPLACE VIEW v_estadisticas_uso AS
SELECT
    categoria,
    facultad,
    COUNT(*) as total_fragmentos,
    SUM(usado_count) as total_usos,
    AVG(relevancia) as relevancia_promedio
FROM v_conocimiento_completo
GROUP BY categoria, facultad
ORDER BY total_usos DESC;

-- ==================== FUNCIONES DE BÚSQUEDA ====================

-- Función para búsqueda semántica con ranking
CREATE OR REPLACE FUNCTION buscar_conocimiento(
    p_query TEXT,
    p_limit INTEGER DEFAULT 5
)
RETURNS TABLE (
    id INTEGER,
    contenido TEXT,
    categoria TEXT,
    facultad TEXT,
    score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        fc.id,
        fc.contenido,
        c.nombre,
        f.nombre,
        ts_rank(fc.contenido_tsvector, plainto_tsquery('spanish_unaccent', p_query)) as rank_score
    FROM fragmentos_conocimiento fc
    LEFT JOIN categorias c ON fc.categoria_id = c.id
    LEFT JOIN facultades f ON fc.facultad_id = f.id
    WHERE fc.contenido_tsvector @@ plainto_tsquery('spanish_unaccent', p_query)
    OR p_query ILIKE ANY(fc.palabras_clave)
    OR EXISTS (
        SELECT 1 FROM unnest(fc.palabras_clave) as kw
        WHERE p_query ILIKE '%' || kw || '%'
    )
    ORDER BY rank_score DESC, fc.usado_count DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Función para incrementar contador de uso
CREATE OR REPLACE FUNCTION incrementar_uso(
    p_fragmento_id INTEGER
)
RETURNS VOID AS $$
BEGIN
    UPDATE fragmentos_conocimiento
    SET usado_count = usado_count + 1,
        fecha_actualizacion = CURRENT_TIMESTAMP
    WHERE id = p_fragmento_id;
END;
$$ LANGUAGE plpgsql;

-- ==================== PERMISOS FINALES ====================

-- Dar permisos al usuario en todas las tablas del esquema
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA unsa_esquema TO unsa_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA unsa_esquema TO unsa_admin;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA unsa_esquema TO unsa_admin;
GRANT ALL PRIVILEGES ON ALL PROCEDURES IN SCHEMA unsa_esquema TO unsa_admin;

-- Configurar búsqueda de texto en español
ALTER DATABASE unsa_knowledge_db SET default_text_search_config = 'spanish_unaccent';

-- Mensaje final
SELECT '✅ ESQUEMA CREADO EXITOSAMENTE' as mensaje;
SELECT '📊 Estadísticas:' as titulo;
SELECT COUNT(*) as total_facultades FROM facultades;
SELECT COUNT(*) as total_categorias FROM categorias;
SELECT COUNT(*) as total_fragmentos FROM fragmentos_conocimiento;
