import csv
from pathlib import Path

CSV_FILE = Path("becas.csv")
SQL_OUT = Path("becas.sql")

def limpiar(t):
    return t.strip().replace("'", "''")

with CSV_FILE.open(encoding="utf-8") as f:
    reader = csv.DictReader(f)
    inserts = []

    for fila in reader:
        nombre = limpiar(fila["nombre"])
        tipo = fila["tipo"]
        descripcion = limpiar(fila["descripcion"])
        requisitos = limpiar(fila["requisitos"])
        dirigido = limpiar(fila["dirigido_a"])
        facultad = fila["facultad"]
        sede = fila["sede"]
        fa = fila["fecha_apertura"]
        fc = fila["fecha_cierre"]
        link = fila["link"]

        keywords = [k.strip().lower() for k in fila["keywords"].split(",") if k.strip()]
        kw_sql = ", ".join(f"'{k}'" for k in keywords)

        contenido = (
            f"{nombre}. "
            f"Tipo: {tipo}. "
            f"Descripción: {descripcion}. "
            f"Requisitos: {requisitos}. "
            f"Dirigido a: {dirigido}. "
            f"Sede: {sede}. "
            f"Inscripción: del {fa} al {fc}. "
            f"Más info: {link}"
        )

        sql = f"""INSERT INTO fragmentos_conocimiento
(contenido, categoria, facultad, palabras_clave)
VALUES (
  '{contenido}',
  'beca',
  '{facultad}',
  ARRAY[{kw_sql}]
);
"""
        inserts.append(sql)

SQL_OUT.write_text("\n".join(inserts), encoding="utf-8")
print(f"✅ Generado {SQL_OUT}")
