-- Índices optimizados para PostgreSQL
-- Índices para fragmentos_conocimiento
CREATE INDEX idx_fragmentos_contenido_fts
ON fragmentos_conocimiento USING gin(to_tsvector('spanish', contenido_vector));

CREATE INDEX idx_fragmentos_palabras_clave
ON fragmentos_conocimiento USING gin(palabras_clave);

CREATE INDEX idx_fragmentos_metadata
ON fragmentos_conocimiento USING gin(metadata);

CREATE INDEX idx_fragmentos_categoria
ON fragmentos_conocimiento(categoria_id);

CREATE INDEX idx_fragmentos_facultad
ON fragmentos_conocimiento(facultad_id);

CREATE INDEX idx_fragmentos_fecha_ingesta
ON fragmentos_conocimiento(fecha_ingesta DESC);

CREATE INDEX idx_fragmentos_relevancia
ON fragmentos_conocimiento(relevancia DESC, usado_count DESC);

-- Índices para categorías (búsqueda jerárquica)
CREATE INDEX idx_categorias_padre
ON categorias(padre_id);

CREATE INDEX idx_categorias_ruta
ON categorias(ruta);

CREATE INDEX idx_categorias_nivel
ON categorias(nivel);

-- Índices para estadísticas
CREATE INDEX idx_estadisticas_fecha
ON estadisticas_anonimas(fecha DESC);

CREATE INDEX idx_estadisticas_tipo
ON estadisticas_anonimas(tipo_consulta);

-- Índices para logs
CREATE INDEX idx_logs_fecha
ON sistema_logs(fecha DESC);

CREATE INDEX idx_logs_nivel
ON sistema_logs(nivel);

CREATE INDEX idx_logs_modulo
ON sistema_logs(modulo);

-- Función para actualizar ruta automáticamente (opcional)
CREATE OR REPLACE FUNCTION actualizar_ruta_categorias()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
        WITH RECURSIVE ruta_cte AS (
            SELECT id, nombre, CAST(nombre AS VARCHAR(500)) AS ruta
            FROM categorias
            WHERE padre_id IS NULL
            UNION ALL
            SELECT c.id, c.nombre, rc.ruta || ' > ' || c.nombre
            FROM categorias c
            JOIN ruta_cte rc ON c.padre_id = rc.id
        )
        UPDATE categorias c
        SET ruta = rc.ruta
        FROM ruta_cte rc
        WHERE c.id = rc.id
        AND c.id = NEW.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para mantener rutas actualizadas
DROP TRIGGER IF EXISTS trigger_actualizar_ruta ON categorias;
CREATE TRIGGER trigger_actualizar_ruta
AFTER INSERT OR UPDATE ON categorias
FOR EACH ROW
EXECUTE FUNCTION actualizar_ruta_categorias();
