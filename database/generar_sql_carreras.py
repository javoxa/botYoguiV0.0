# generar_sql_carreras.py
import csv
import sys
from pathlib import Path

# ================= CONFIG =================
CSV_FILE = Path("carreras_exactas.csv") # Nombre del archivo CSV de entrada
SQL_OUT = Path("carreras_exactas.sql") # Nombre del archivo SQL de salida
CATEGORIA_FIJA = "carrera" # La categoría para todas las carreras
FACULTADES_VALIDAS = {"exactas", "economicas", "naturales", "humanidades", "ingenieria", "salud", "oran", "tartagal"}
NIVELES_VALIDOS = {"pregrado", "grado", "posgrado"}

# ================= UTILIDADES =================
def limpiar(texto: str) -> str:
    """Limpia un string para ser usado en SQL (escapa comillas simples)."""
    if texto is None:
        return ""
    return texto.strip().replace("'", "''")

def validar_fila(fila, nro):
    """Valida los campos de una fila del CSV."""
    errores = []
    if fila["facultad"] not in FACULTADES_VALIDAS:
        errores.append(f"facultad inválida: {fila['facultad']}")
    if fila["nivel"] not in NIVELES_VALIDOS:
        errores.append(f"nivel inválido: {fila['nivel']}")
    if not fila["nombre"]:
        errores.append("nombre vacío")
    if not fila["sede"]:
        errores.append("sede vacía")
    if not fila["duracion"]:
        errores.append("duración vacía")

    if errores:
        print(f"⚠️  Fila {nro}: {', '.join(errores)}")
        sys.exit(1)

# ================= MAIN =================
def main():
    if not CSV_FILE.exists():
        print(f"❌ CSV no encontrado: {CSV_FILE}")
        sys.exit(1)

    # Asumiendo que tu CSV ahora tiene las columnas: nombre,nivel,facultad,sede,duracion,descripcion,keywords
    COLUMNAS_ESPERADAS = {"nombre", "nivel", "facultad", "sede", "duracion", "descripcion", "keywords"}

    inserts = []
    with open(CSV_FILE, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=',')

        # Validar columnas
        if not set(reader.fieldnames).issuperset(COLUMNAS_ESPERADAS):
            print(f"❌ El CSV debe contener las columnas: {COLUMNAS_ESPERADAS}")
            print(f"Columnas encontradas: {set(reader.fieldnames)}")
            sys.exit(1)

        for i, fila in enumerate(reader, start=2):
            validar_fila(fila, i)

            nombre = limpiar(fila["nombre"])
            nivel = limpiar(fila["nivel"])
            facultad = limpiar(fila["facultad"])
            sede = limpiar(fila["sede"])
            duracion = limpiar(fila["duracion"])
            # Nueva línea: Obtener la descripción
            descripcion_raw = fila.get("descripcion", "").strip() # Manejar posibles valores vacíos
            descripcion = limpiar(descripcion_raw) if descripcion_raw else "" # Limpiarla si existe, sino dejar string vacío
            keywords = [limpiar(k) for k in fila["keywords"].split(",") if k.strip()]

            # Opción A: Incluir la descripción en el contenido principal (opcional)
            contenido_detalle = f" {descripcion}" if descripcion else ""
            contenido = f"{nombre}. Carrera de {nivel}. Sede: {sede}. Duración: {duracion}.{contenido_detalle}".strip()

            # Opción B: Dejar el contenido principal como antes, y solo usar 'descripcion' como campo extra (Recomendado)
            # contenido = f"{nombre}. Carrera de {nivel}. Sede: {sede}. Duración: {duracion}."


            kw_sql = ", ".join(f"'{k}'" for k in keywords)
            # Modificar la sentencia INSERT para incluir la columna descripcion
            # Usamos COALESCE para manejar el caso donde descripcion sea una cadena vacía, insertándola como NULL si es necesario.
            # Pero para la base de datos y el retriever, probablemente sea mejor insertar la cadena vacía si no hay descripción.
            # Si se prefiere NULL: sql = f"""... VALUES ('{contenido}', '{CATEGORIA_FIJA}', '{facultad}', ARRAY[{kw_sql}], {'NULL' if not descripcion else f"'{descripcion}'"});"""
            # Versión que inserta la cadena vacía si no hay descripción:
            sql = f"""INSERT INTO fragmentos_conocimiento(contenido, categoria, facultad, palabras_clave, descripcion) -- Añadida descripcion
                      VALUES ('{contenido}', '{CATEGORIA_FIJA}', '{facultad}', ARRAY[{kw_sql}], '{descripcion}');""" # Usar descripcion
            inserts.append(sql)

    # Escribir el archivo SQL
    try:
        SQL_OUT.write_text("\n".join(inserts), encoding="utf-8")
        print(f"✅ Generado {SQL_OUT} con {len(inserts)} INSERTs")
    except Exception as e:
        print(f"❌ Error escribiendo archivo SQL: {e}")
        sys.exit(1)

# ================= RUN =================
if __name__ == "__main__":
    main()
