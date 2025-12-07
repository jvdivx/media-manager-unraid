#!/usr/bin/python3
import os
import sys
import shutil
import sqlite3
from datetime import datetime

# ==============================================================================
# CONFIGURACI脫N GENERAL Y RUTAS
# ==============================================================================

# Detectar si estamos en Docker (/app/datos existe) o en local
BASE_LOGS_DIR = "/app/datos"
if not os.path.exists(BASE_LOGS_DIR):
    BASE_LOGS_DIR = os.getcwd() # Fallback para pruebas locales

# --- RUTA DE DESTINO FINAL ---
DESTINO_ROOT = "/mnt/user/peliculas/BajaCalidad"

# --- CAMBIO AQUI: Nombre del script .sh ---
SCRIPT_SALIDA_SH = os.path.join(BASE_LOGS_DIR, "script_10_peliculas_move_sd.sh")
REPORTE_HTML = os.path.join(BASE_LOGS_DIR, "report_10_peliculas_sd.html")

# Rutas de la Base de Datos (Mapeada en el contenedor)
PLEX_DB_PATH = "/mnt/user/appdata/plex/Library/Application Support/Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db"
TEMP_DB_PATH = "/tmp/plex_scan_sd_temp.db"

# Prefijos para correcci贸n de rutas
DOCKER_PREFIX = "/data" 
UNRAID_PREFIX = "/mnt/user"

# Colores para consola
RESET = "\033[0m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RED = "\033[91m"
GRAY = "\033[90m"

# ==============================================================================
# ESTILOS CSS Y JAVASCRIPT (MODO OSCURO)
# ==============================================================================
CSS_STYLE = """
<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
<style>
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #1e1e1e; color: #e0e0e0; margin: 20px; }
    h1 { text-align: center; color: #4da6ff; margin-bottom: 10px; }
    h2 { border-bottom: 2px solid #4da6ff; padding-bottom: 5px; color: #ffffff; margin-top: 40px; }
    .container { max-width: 95%; margin: 0 auto; background: #252526; padding: 20px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
    table.dataTable { width: 100% !important; border-collapse: collapse; font-size: 0.95em; color: #e0e0e0; }
    table.dataTable thead th { background-color: #333337; color: #4da6ff; border-bottom: 1px solid #4da6ff; padding: 12px; text-align: left; }
    table.dataTable tbody td { background-color: #252526; border-bottom: 1px solid #3e3e42; padding: 10px; vertical-align: middle; }
    table.dataTable tbody tr:hover td { background-color: #2d2d30 !important; }
    .badge { padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; color: white; letter-spacing: 0.5px; }
    .res-low { background-color: #ef4444; } 
    .res-med { background-color: #f59e0b; color: black; } 
    .codec { background-color: #3b82f6; } 
    .disk { background-color: #6366f1; }
    .path-cell { font-family: 'Consolas', monospace; font-size: 0.85em; color: #9ca3af; word-break: break-all; }
    .alert { background: #333337; color: #e0e0e0; padding: 15px; border-radius: 5px; margin-bottom: 20px; border-left: 5px solid #f59e0b; }
    .alert code { background: #000; padding: 2px 5px; border-radius: 3px; color: #10b981; font-family: monospace; }
    .dataTables_wrapper .dataTables_length, .dataTables_wrapper .dataTables_filter, 
    .dataTables_wrapper .dataTables_info, .dataTables_wrapper .dataTables_paginate { color: #e0e0e0 !important; }
    .dataTables_wrapper .dataTables_filter input { background-color: #333337; color: #e0e0e0; border: 1px solid #4da6ff; padding: 5px; border-radius: 4px; }
</style>
"""

JS_SCRIPT = """
<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
<script>
$(document).ready(function() {
    $('#moviesTable').DataTable({
        "pageLength": 25,
        "lengthMenu": [ [10, 25, 50, 100, -1], [10, 25, 50, 100, "Todos"] ],
        "order": [[ 2, "desc" ]],
        "language": {
            "search": "馃攳 Buscar:",
            "lengthMenu": "Mostrar _MENU_ registros",
            "info": "Mostrando _START_ a _END_ de _TOTAL_",
            "paginate": { "first": "<<", "last": ">>", "next": ">", "previous": "<" }
        }
    });
});
</script>
"""

# ==============================================================================
# FUNCIONES AUXILIARES
# ==============================================================================

def human_size(bytes_val):
    try:
        val = float(bytes_val)
        if val > 1073741824: return f"{val/1073741824:.2f} GB"
        if val > 1048576: return f"{val/1048576:.2f} MB"
        return f"{val:.0f} B"
    except: return "0 B"

def obtener_disco(ruta):
    if "/mnt/cache/" in ruta: return "Cache (SSD)"
    if "/mnt/disk" in ruta: 
        try: return ruta.split('/')[2].capitalize()
        except: return "Array"
    return "User Share"

def obtener_datos_plex():
    if not os.path.exists(PLEX_DB_PATH):
        print(f"{RED}ERROR CR脥TICO: No encuentro la DB en: {PLEX_DB_PATH}{RESET}")
        sys.exit(1)

    print(f"{BLUE}--> Copiando base de datos a entorno temporal...{RESET}")
    try:
        if os.path.exists(TEMP_DB_PATH): os.remove(TEMP_DB_PATH)
        shutil.copy2(PLEX_DB_PATH, TEMP_DB_PATH)
    except Exception as e:
        print(f"{RED}Error copiando DB: {e}{RESET}")
        sys.exit(1)

    print(f"{BLUE}--> Ejecutando consulta SQL nativa...{RESET}")
    query = (
        "SELECT mi.title, mi.year, mp.file, m.width, m.height, mp.size, m.video_codec "
        "FROM metadata_items mi "
        "JOIN media_items m ON m.metadata_item_id = mi.id "
        "JOIN media_parts mp ON mp.media_item_id = m.id "
        "WHERE mi.metadata_type = 1 "
        "AND (m.width < 1000 AND m.height < 600) "
        "ORDER BY m.width DESC;"
    )
    
    resultados = []
    conn = None
    try:
        conn = sqlite3.connect(TEMP_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(query)
        resultados = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"{RED}Error SQL: {e}{RESET}")
    finally:
        if conn: conn.close()
        if os.path.exists(TEMP_DB_PATH): os.remove(TEMP_DB_PATH)
        
    return resultados

def generate_html_report(data_list):
    script_basename = os.path.basename(SCRIPT_SALIDA_SH)
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Reporte Pel铆culas SD</title>
        {CSS_STYLE}
    </head>
    <body>
        <div class="container">
            <h1>馃搲 Reporte: Pel铆culas Baja Resoluci贸n (SD)</h1>
            <div class="alert">
                <strong>Acci贸n Generada:</strong> Se ha creado el script de>{script_basename}</code> 
                con <strong>{len(data_list)}</strong> movimientos programados hacia la carpeta:
                <br>de>{DESTINO_ROOT}</code>
            </div>
            <table id="moviesTable" class="display responsive nowrap" style="width:100%">
                <thead>
                    <tr>
                        <th>T铆tulo</th><th>A帽o</th><th>Resoluci贸n</th><th>Codec</th><th>Tama帽o</th><th>Disco</th><th>Ruta Archivo</th>
                    </tr>
                </thead>
                <tbody>
    """
    for item in data_list:
        width = int(item['width']) if item['width'] else 0
        res_class = "res-low" if width < 640 else "res-med"
        html_content += f"""
            <tr>
                <td><strong>{item['title']}</strong></td><td>{item['year']}</td>
                <td><span class="badge {res_class}">{item['width']}x{item['height']}</span></td>
                <td><span class="badge codec">{item['codec']}</span></td>
                <td data-order="{item['raw_size']}">{item['size_str']}</td>
                <td><span class="badge disk">{item['disk']}</span></td>
                <td class="path-cell">{item['path_unraid']}</td>
            </tr>"""
    html_content += f"""</tbody></table></div>{JS_SCRIPT}</body></html>"""
    
    try:
        with open(REPORTE_HTML, "w", encoding='utf-8') as f: f.write(html_content)
        print(f"{GREEN}[HTML] Reporte guardado en: {REPORTE_HTML}{RESET}")
    except IOError as e: print(f"{RED}Error guardando HTML: {e}{RESET}")

def main():
    print(f"{'='*60}\n GENERADOR MOVIMIENTOS SD (PYTHON NATIVO)\n{'='*60}")
    print(f"--> Directorio Logs: {BASE_LOGS_DIR}")
    print(f"--> Destino Base:    {DESTINO_ROOT}")

    rows = obtener_datos_plex()
    if not rows: return

    comandos_mv = []
    data_list = []
    categorias_detectadas = set()

    print(f"{BLUE}--> Procesando {len(rows)} archivos...{RESET}")

    for row in rows:
        title, year, path_raw, width, height, size_bytes, codec = row
        if not path_raw: continue
        if not width: width = 0
        if not height: height = 0

        # Correcci贸n ruta
        if path_raw.startswith(DOCKER_PREFIX):
            path_unraid = path_raw.replace(DOCKER_PREFIX, UNRAID_PREFIX, 1)
        else:
            path_unraid = path_raw

        dir_origen = os.path.dirname(path_unraid)      
        try: categoria = os.path.basename(os.path.dirname(dir_origen)) 
        except: categoria = "Desconocido"
        
        data_list.append({
            'title': title, 'year': year, 'width': width, 'height': height,
            'codec': codec, 'raw_size': size_bytes, 'size_str': human_size(size_bytes),
            'path_unraid': path_unraid, 'disk': obtener_disco(path_unraid)
        })

        ruta_destino_cat = os.path.join(DESTINO_ROOT, categoria)
        categorias_detectadas.add(ruta_destino_cat)
        
        src = f'"{dir_origen}"'
        dst = f'"{ruta_destino_cat}"'
        comandos_mv.append(f"# {title} ({width}x{height})\nmv -n -v {src} {dst}/")

    try:
        with open(SCRIPT_SALIDA_SH, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write(f"# Script generado el {datetime.now()}\n")
            f.write(f"# Destino base: {DESTINO_ROOT}\n\n")
            for cat in sorted(categorias_detectadas): f.write(f'mkdir -p "{cat}"\n')
            f.write("\n" + '\n'.join(comandos_mv) + "\n")
        os.chmod(SCRIPT_SALIDA_SH, 0o755)
        print(f"{GREEN}[SH] Script Bash guardado en: {SCRIPT_SALIDA_SH}{RESET}")
    except IOError as e: print(f"{RED}Error escribiendo SH: {e}{RESET}")
    
    generate_html_report(data_list)
    print("-" * 50)
    print(f"{YELLOW}RESUMEN: {len(data_list)} pel铆culas detectadas.{RESET}")
    print(f"1. Ver Reporte: {os.path.basename(REPORTE_HTML)}")
    print(f"2. Script Bash: {os.path.basename(SCRIPT_SALIDA_SH)}")

if __name__ == "__main__":
    main()
