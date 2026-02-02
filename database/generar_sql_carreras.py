import csv
import sys
from pathlib import Path

# ================= CONFIG =================

CSV_FILE = Path("carreras_exactas.csv")
SQL_OUT = Path("carreras_exactas.sql")

CATEGORIA_FIJA = "carrera"

FACULTADES_VALIDAS = {
    "exactas", "economicas", "naturales", "humanidades",
    "ingenieria", "salud", "oran", "tartagal"
}

NIVELES_VALIDOS = {"pregrado", "grado", "posgrado"}

# ================= UTILIDADES =================

def limpiar(texto: str) -> str:
    return texto.strip().replace("'", "''")

def validar_fila(fila, nro):
    errores = []

    if fila["facultad"] not in FACULTADES_VALIDAS:
        errores.append(f"facultad inválida: {fila['facultad']}")

    if fila["nivel"] not in NIVELES_VALIDOS:
        errores.append(f"nivel inválido: {fila['nivel']}")

    if not fila["nombre"]:
        errores.append("nombre vacío")

    if "ninguna" in fila["nombre"].lower():
        errores.append("contiene 'ninguna'")

    if errores:
        raise ValueError(f"Fila {nro}: " + ", ".join(errores))

# ================= MAIN =================

def main():
    if not CSV_FILE.exists():
        print(f"❌ No existe {CSV_FILE}")
        sys.exit(1)

    inserts = []

    with CSV_FILE.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t" if "\t" in f.readline() else ",")

        f.seek(0)
        reader = csv.DictReader(f)

        for i, fila in enumerate(reader, start=2):
            validar_fila(fila, i)

            nombre = limpiar(fila["nombre"])
            nivel = fila["nivel"]
            facultad = fila["facultad"]
            sede = fila["sede"]
            duracion = limpiar(fila["duracion"])

            keywords = [
                k.strip().lower()
                for k in fila["keywords"].split(",")
                if k.strip()
            ]

            contenido = (
                f"{nombre}. "
                f"Carrera de {nivel}. "
                f"Sede: {sede}. "
                f"Duración: {duracion}."
            )

            kw_sql = ", ".join(f"'{k}'" for k in keywords)

            sql = f"""INSERT INTO fragmentos_conocimiento
(contenido, categoria, facultad, palabras_clave)
VALUES (
  '{contenido}',
  '{CATEGORIA_FIJA}',
  '{facultad}',
  ARRAY[{kw_sql}]
);
"""
            inserts.append(sql)

    SQL_OUT.write_text("\n".join(inserts), encoding="utf-8")

    print(f"✅ Generado {SQL_OUT} con {len(inserts)} INSERTs")

# ================= RUN =================

if __name__ == "__main__":
    main()
