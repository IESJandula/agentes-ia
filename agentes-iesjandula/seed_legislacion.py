"""
seed_legislacion.py — CLI para carga masiva de documentos legislativos.

Uso básico (indexa data/legislacion/ por defecto):
    python seed_legislacion.py

Carpeta personalizada:
    python seed_legislacion.py --carpeta /ruta/a/mis/docs

Solo listar qué hay sin indexar:
    python seed_legislacion.py --listar

Forzar reindexado aunque el archivo ya exista:
    python seed_legislacion.py --forzar

Indexar un único archivo:
    python seed_legislacion.py --archivo decreto-123-2025.pdf
"""

import sys
import os
import argparse

# Fix sqlite3 en Linux (mismo que main.py)
if sys.platform.startswith("linux"):
    __import__("pysqlite3")
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")

# Asegurar que el directorio raíz esté en el path
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from dotenv import load_dotenv
load_dotenv()

from data.data import (
    seed_legislacion_folder,
    procesar_y_añadir,
    listar_documentos_en_coleccion,
    RUTA_LEGISLACION_DEFAULT,
    _EXTENSIONES_SEED,
)


def cmd_listar(carpeta: str):
    """Muestra el estado de cada archivo en la carpeta vs. lo que está indexado."""
    if not os.path.isdir(carpeta):
        print(f"❌ La carpeta no existe: {carpeta}")
        return

    archivos_carpeta = sorted(
        f for f in os.listdir(carpeta)
        if os.path.splitext(f)[1].lower() in _EXTENSIONES_SEED
    )
    if not archivos_carpeta:
        print(f"ℹ️ Carpeta vacía: {carpeta}")
        return

    print(f"\n📂 Carpeta: {carpeta}")
    print(f"   {len(archivos_carpeta)} archivo(s) encontrado(s)\n")

    # Documentos ya indexados en conocimiento_web
    indexados = set(listar_documentos_en_coleccion("conocimiento"))

    print(f"{'ARCHIVO':<55} {'ESTADO'}")
    print("-" * 70)
    for f in archivos_carpeta:
        estado = "✅ indexado" if f in indexados else "⏳ pendiente"
        print(f"  {f:<53} {estado}")

    pendientes = [f for f in archivos_carpeta if f not in indexados]
    print(f"\n  {len(pendientes)} pendiente(s) de indexar · {len(archivos_carpeta)-len(pendientes)} ya indexado(s)")


def cmd_forzar(carpeta: str):
    """Reindexar TODOS los archivos aunque ya estén en ChromaDB."""
    if not os.path.isdir(carpeta):
        print(f"❌ La carpeta no existe: {carpeta}")
        return

    archivos = sorted(
        f for f in os.listdir(carpeta)
        if os.path.splitext(f)[1].lower() in _EXTENSIONES_SEED
    )
    if not archivos:
        print("ℹ️ Carpeta vacía, nada que indexar.")
        return

    print(f"⚡ Modo FORZAR: se reindexarán los {len(archivos)} archivos (pueden crearse duplicados si ya existían).")
    confirmacion = input("¿Continuar? [s/N] ").strip().lower()
    if confirmacion != "s":
        print("Cancelado.")
        return

    total_frags = 0
    errores = 0
    for i, nombre in enumerate(archivos, 1):
        ruta = os.path.join(carpeta, nombre)
        print(f"\n[{i}/{len(archivos)}] {nombre}")
        try:
            n = procesar_y_añadir(ruta, "conocimiento", nombre)
            print(f"   ✅ {n} fragmentos indexados")
            total_frags += n
        except Exception as e:
            print(f"   ❌ Error: {e}")
            errores += 1

    print(f"\n📊 Forzado completo — {total_frags} fragmentos · {errores} errores")


def cmd_archivo(ruta_archivo: str):
    """Indexar un único archivo."""
    if not os.path.isfile(ruta_archivo):
        print(f"❌ Archivo no encontrado: {ruta_archivo}")
        return

    nombre = os.path.basename(ruta_archivo)
    ext = os.path.splitext(nombre)[1].lower()
    if ext not in _EXTENSIONES_SEED:
        print(f"⚠️ Extensión '{ext}' no soportada. Usa: {', '.join(_EXTENSIONES_SEED)}")
        return

    print(f"📄 Indexando: {nombre}")
    try:
        n = procesar_y_añadir(ruta_archivo, "conocimiento", nombre)
        if n > 0:
            print(f"✅ {n} fragmentos indexados en conocimiento_web")
        else:
            print("⚠️ El archivo no produjo fragmentos (texto vacío o no extraíble)")
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Carga masiva de documentos legislativos en ChromaDB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--carpeta",
        default=RUTA_LEGISLACION_DEFAULT,
        help=f"Ruta a la carpeta con los documentos (por defecto: {RUTA_LEGISLACION_DEFAULT})",
    )
    parser.add_argument(
        "--listar",
        action="store_true",
        help="Solo listar el estado de los archivos, sin indexar.",
    )
    parser.add_argument(
        "--forzar",
        action="store_true",
        help="Reindexar todos los archivos aunque ya estén en ChromaDB.",
    )
    parser.add_argument(
        "--archivo",
        metavar="RUTA",
        help="Indexar un único archivo en lugar de la carpeta completa.",
    )

    args = parser.parse_args()

    if args.archivo:
        cmd_archivo(args.archivo)
    elif args.listar:
        cmd_listar(args.carpeta)
    elif args.forzar:
        cmd_forzar(args.carpeta)
    else:
        resultado = seed_legislacion_folder(args.carpeta)
        if resultado["docs_nuevos"] == 0 and resultado["omitidos"] > 0:
            print("\n✅ Todos los documentos ya estaban indexados.")
        elif resultado["docs_nuevos"] == 0 and resultado["errores"] == 0:
            print("\nℹ️ Nada que hacer (carpeta vacía o todo ya indexado).")


if __name__ == "__main__":
    main()
