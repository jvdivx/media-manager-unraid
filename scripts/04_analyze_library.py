#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import time
import html
import signal
import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ==========================================
# CONFIGURACIÓN
# ==========================================
PATHS = {
    "1": {"nombre": "Series", "ruta": "/mnt/user/series"},
    "2": {"nombre": "Películas", "ruta": "/mnt/user/peliculas"}
}
CARPETA_EXCLUIDA = "Uploads"
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".m2ts", ".mpg", ".m4v", ".vob", ".ts", ".iso"}

RESOLUCIONES_VALIDAS = ["2160p", "1440p", "1080p", "720p", "576p", "540p", "480p", "360p", "SD"]
ORDEN_RESOL = {r: i for i, r in enumerate(RESOLUCIONES_VALIDAS)}

# Rutas Normalizadas
SCRIPT_DIR = Path("/mnt/user/appdata/media-manager/datos")
SCRIPT_DIR.mkdir(parents=True, exist_ok=True)

# ==========================================
# CLASES DE UTILIDAD
# ==========================================
class Color:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def signal_handler(signum, frame):
    print(f"\n\n{Color.FAIL}🛑 Operación cancelada.{Color.ENDC}")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def print_header(text):
    print(f"\n{Color.HEADER}╔{'═'*60}╗", flush=True)
    print(f"║ {text:^58} ║", flush=True)
    print(f"╚{'═'*60}╝{Color.ENDC}", flush=True)

# ==========================================
# LÓGICA DE VIDEO
# ==========================================
def extraer_resolucion(nombre):
    nombre = nombre.lower()
    if "2160p" in nombre or "4k" in nombre: return "2160p"
    if "1080p" in nombre: return "1080p"
    if "720p" in nombre: return "720p"
    match = re.search(r'(\d{3,4}p)', nombre)
    if match and match.group(1) in RESOLUCIONES_VALIDAS:
        return match.group(1)
    return "SD/Desc"

def extraer_codec(nombre):
    n = nombre.lower()
    if any(x in n for x in ["x265", "h265", "hevc"]): return "HEVC (x265)"
    if any(x in n for x in ["x264", "h264", "avc"]): return "AVC (x264)"
    if "av1" in n: return "AV1"
    if "vp9" in n: return "VP9"
    if any(x in n for x in ["xvid", "divx"]): return "XviD/DivX"
    if any(x in n for x in ["mpeg", "mpg"]): return "MPEG"
    return "Otros"

def formatear_tamano(b):
    if b < 1024: return f"{b} B"
    if b < 1024**2: return f"{b/1024:.1f} KB"
    if b < 1024**3: return f"{b/1024**2:.1f} MB"
    return f"{b/1024**3:.2f} GB"

# ==========================================
# GENERADOR HTML PRO
# ==========================================
def generar_html_pro(filtrados, config, stats, filters_info):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    # Nombre normalizado según el tipo de librería
    safe_name = config['nombre'].lower().replace("películas", "peliculas") # Asegurar sin tildes en filename
    filename_html = SCRIPT_DIR / f"report_04_library_{safe_name}.html"
    
    total_size_bytes = sum(d['size'] for d in filtrados)
    total_size_fmt = formatear_tamano(total_size_bytes)
    
    # Top resolución
    top_res = "N/A"
    res_counts = defaultdict(int)
    for f in filtrados: res_counts[f['res']] += 1
    if res_counts: top_res = max(res_counts, key=res_counts.get)

    rows_html = ""
    for d in filtrados:
        res_class = "res-4k" if "2160p" in d['res'] else ("res-1080p" if "1080p" in d['res'] else "res-sd")
        safe_name = html.escape(d['nombre'])
        safe_path = html.escape(d['ruta'].replace(config['ruta'], ""))
        
        rows_html += f"""
        <tr>
            <td><span class="badge {res_class}">{d['res']}</span></td>
            <td>{d['cod']}</td>
            <td data-order="{d['size']}" class="text-right font-mono">{d['size_fmt']}</td>
            <td>
                <div class="file-title">{safe_name}</div>
                <div class="path-cell">{safe_path}</div>
            </td>
        </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Informe {config['nombre']}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.4/css/jquery.dataTables.min.css">
    <style>
        :root {{ --bg: #0f1115; --card: #181b21; --accent: #6366f1; --text: #e2e8f0; --border: #334155; }}
        body {{ background-color: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; margin: 0; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; border-bottom: 1px solid var(--border); padding-bottom: 20px; }}
        h1 {{ margin: 0; font-weight: 600; color: #fff; letter-spacing: -1px; }}
        .meta {{ color: #94a3b8; font-size: 0.9rem; }}
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .kpi-card {{ background: var(--card); padding: 20px; border-radius: 12px; border: 1px solid var(--border); }}
        .kpi-label {{ color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; font-weight: bold; }}
        .kpi-value {{ font-size: 2rem; font-weight: 700; color: #fff; margin-top: 5px; }}
        .kpi-card.main {{ border-left: 4px solid var(--accent); }}
        #libraryTable {{ width: 100% !important; border-collapse: collapse; margin-top: 20px; }}
        table.dataTable thead th {{ background-color: #1e293b !important; color: #fff !important; padding: 15px !important; border-bottom: 2px solid var(--accent) !important; }}
        table.dataTable tbody td {{ background-color: var(--card) !important; color: var(--text) !important; border-bottom: 1px solid var(--border) !important; padding: 12px !important; vertical-align: middle; }}
        table.dataTable tbody tr:hover td {{ background-color: #222 !important; }}
        .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 800; display: inline-block; min-width: 60px; text-align: center; }}
        .res-4k {{ background: rgba(255, 215, 0, 0.15); color: #ffd700; border: 1px solid rgba(255, 215, 0, 0.3); }}
        .res-1080p {{ background: rgba(0, 255, 255, 0.15); color: #00ffff; border: 1px solid rgba(0, 255, 255, 0.3); }}
        .res-sd {{ background: rgba(255, 99, 71, 0.15); color: #ff6347; border: 1px solid rgba(255, 99, 71, 0.3); }}
        .file-title {{ font-weight: 600; color: #fff; margin-bottom: 2px; }}
        .path-cell {{ font-family: 'Courier New', monospace; color: #64748b; font-size: 0.8rem; }}
        .text-right {{ text-align: right; }} .font-mono {{ font-family: monospace; }}
        .dataTables_wrapper .dataTables_length, .dataTables_wrapper .dataTables_filter, .dataTables_wrapper .dataTables_info, .dataTables_wrapper .dataTables_paginate {{ color: #94a3b8 !important; margin-bottom: 10px; }}
        .dataTables_wrapper .dataTables_filter input {{ background: #0f1115; border: 1px solid var(--border); color: #fff; padding: 5px 10px; border-radius: 4px; margin-left: 5px; outline: none; }}
        .dataTables_wrapper .dataTables_length select {{ background: #0f1115; border: 1px solid var(--border); color: #fff; padding: 5px; border-radius: 4px; margin-right: 5px; }}
        .paginate_button {{ color: #fff !important; border-radius: 4px !important; }}
        .paginate_button.current {{ background: var(--accent) !important; border: none !important; color: white !important; }}
        .paginate_button:hover {{ background: #333 !important; border: none !important; color: white !important; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div><h1>📊 Informe de {config['nombre']}</h1><div class="meta">Filtros: {filters_info}</div></div>
            <div class="meta">{ts}</div>
        </div>
        <div class="kpi-grid">
            <div class="kpi-card main"><div class="kpi-label">Total Archivos</div><div class="kpi-value">{len(filtrados)}</div></div>
            <div class="kpi-card"><div class="kpi-label">Tamaño Total</div><div class="kpi-value">{total_size_fmt}</div></div>
            <div class="kpi-card"><div class="kpi-label">Resolución Dominante</div><div class="kpi-value">{top_res}</div></div>
        </div>
        <table id="libraryTable" class="display">
            <thead><tr><th width="10%">Res</th><th width="10%">Codec</th><th width="15%">Tamaño</th><th>Nombre / Ruta</th></tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>
    <script>
        $(document).ready(function() {{
            $('#libraryTable').DataTable({{ "pageLength": 25, "order": [[ 2, "desc" ]], "language": {{ "search": "🔍 Buscar:", "lengthMenu": "Mostrar _MENU_ registros", "info": "Mostrando _START_ a _END_ de _TOTAL_", "paginate": {{ "first": "«", "last": "»", "next": "Sig", "previous": "Ant" }}, "zeroRecords": "No se encontraron resultados" }} }});
        }});
    </script>
</body>
</html>"""
    
    with open(filename_html, "w", encoding="utf-8") as f: f.write(html_content)
    return filename_html

# ==========================================
# MAIN
# ==========================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lib", choices=["1", "2"], help="ID de librería")
    parser.add_argument("--res", default="", help="Filtro de resolución")
    parser.add_argument("--codec", default="", help="Filtro de codec")
    parser.add_argument("--sort", default="1", choices=["1", "2", "3", "4"], help="Método de ordenación")
    args = parser.parse_args()

    print_header("ANALIZADOR DE BIBLIOTECA")

    sel = args.lib
    if not sel:
        if sys.stdin.isatty():
            print(f"{Color.BOLD}Selecciona la librería:{Color.ENDC}")
            for k, v in PATHS.items():
                print(f"  [{k}] {v['nombre']}")
            sel = input(f"\n>> Opción: ").strip()
        else:
            print(f"{Color.FAIL}❌ Error: Argumento --lib requerido.{Color.ENDC}")
            return

    if sel not in PATHS:
        print(f"{Color.FAIL}❌ Opción inválida.{Color.ENDC}")
        return

    config = PATHS[sel]
    base_path = config["ruta"]
    
    if not os.path.exists(base_path):
        print(f"{Color.FAIL}❌ Ruta no encontrada: {base_path}{Color.ENDC}")
        return

    print(f"{Color.CYAN}📂 Analizando: {base_path}{Color.ENDC}", flush=True)

    total_files = 0
    for root, dirs, files in os.walk(base_path):
        if CARPETA_EXCLUIDA in dirs: dirs.remove(CARPETA_EXCLUIDA)
        total_files += len([f for f in files if os.path.splitext(f)[1].lower() in VIDEO_EXT])

    datos = []
    stats = defaultdict(int)
    processed = 0
    
    for root, dirs, files in os.walk(base_path):
        if CARPETA_EXCLUIDA in dirs: dirs.remove(CARPETA_EXCLUIDA)
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext not in VIDEO_EXT: continue

            res = extraer_resolucion(f)
            cod = extraer_codec(f)
            f_path = os.path.join(root, f)
            try: size = os.path.getsize(f_path)
            except: size = 0

            datos.append({
                "ruta": f_path, "nombre": f, "res": res, 
                "cod": cod, "size": size, "size_fmt": formatear_tamano(size)
            })
            stats[(res, cod)] += 1
            processed += 1
            if processed % 500 == 0: print(f"   ... {processed} archivos", flush=True)

    f_res = args.res.lower().strip()
    f_cod = args.codec.lower().strip()
    
    filtrados = [
        d for d in datos 
        if (not f_res or f_res in d["res"].lower()) and 
           (not f_cod or f_cod in d["cod"].lower())
    ]

    if not filtrados:
        print(f"{Color.FAIL}❌ Sin coincidencias.{Color.ENDC}")
        return

    ord_opt = args.sort
    if ord_opt == "2": filtrados.sort(key=lambda x: x["size"])
    elif ord_opt == "3": filtrados.sort(key=lambda x: x["nombre"])
    elif ord_opt == "4": filtrados.sort(key=lambda x: ORDEN_RESOL.get(x["res"], 99))
    else: filtrados.sort(key=lambda x: x["size"], reverse=True)

    print_header(f"INFORME: {config['nombre'].upper()}")
    print(f"   • Archivos: {len(filtrados)}")
    
    filters_str = f"Res='{f_res or 'ALL'}', Codec='{f_cod or 'ALL'}'"
    html_path = generar_html_pro(filtrados, config, stats, filters_str)
    
    print(f"\n{Color.GREEN}✅ Informe generado:{Color.ENDC}")
    print(f"📄 {html_path}", flush=True)

if __name__ == "__main__":
    main()
