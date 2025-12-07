#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import html
import argparse
from pathlib import Path
from datetime import datetime

# ==========================================
# CONFIGURACIÓN
# ==========================================
PATH_SERIES_ROOT = "/mnt/user/series"
CARPETA_UPLOADS = "Uploads" 
SUB_CARPETA_BAJA_CALIDAD = "BajaCalidad" 
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".m2ts", ".mpg", ".m4v", ".ts", ".iso"}

# Criterios de Baja Calidad
BAJA_CALIDAD = ["576p", "540p", "480p", "360p", "SD", "Desconocido"]

# Rutas Normalizadas
SCRIPT_DIR = Path("/mnt/user/appdata/media-manager/datos")
SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_FILENAME = SCRIPT_DIR / "report_05_quality.html"
SH_FILENAME = SCRIPT_DIR / "script_05_move_quality.sh"

# ==========================================
# CLASES Y UTILIDADES
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

def print_header(text):
    print(f"\n{Color.HEADER}╔{'═'*60}╗", flush=True)
    print(f"║ {text:^58} ║", flush=True)
    print(f"╚{'═'*60}╝{Color.ENDC}", flush=True)

def detectar_resolucion(nombre):
    n = nombre.lower()
    if "2160p" in n or "4k" in n: return "2160p"
    if "1080p" in n: return "1080p"
    if "720p" in n: return "720p"
    match = re.search(r'(\d{3,4}p)', n)
    if match: return match.group(1)
    return "Desconocido"

def es_baja_calidad(res):
    return res in BAJA_CALIDAD

# ==========================================
# GENERADOR HTML PRO
# ==========================================
def generar_html(series_afectadas):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    # Obtenemos el umbral del primer elemento (todos tienen el mismo umbral)
    umbral = list(series_afectadas.values())[0]['umbral'] if series_afectadas else 80
    
    rows = ""
    for ruta_serie, datos in series_afectadas.items():
        nombre_serie = os.path.basename(ruta_serie)
        categoria = datos['categoria']
        total_caps = datos['total_caps']
        malos = datos['malos']
        
        safe_name = html.escape(nombre_serie)
        safe_cat = html.escape(categoria)
        porcentaje = (malos / total_caps) * 100 if total_caps > 0 else 0
        
        rows += f"""
        <tr>
            <td><span class="badge badge-danger">{int(porcentaje)}% BC</span></td>
            <td>{safe_cat}</td>
            <td class="text-right">{malos}/{total_caps} caps</td>
            <td>
                <div class="file-name">{safe_name}</div>
                <div class="file-path">{ruta_serie}</div>
            </td>
        </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Series Baja Calidad</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.4/css/jquery.dataTables.min.css">
    <style>
        :root {{ --bg: #0f1115; --card: #181b21; --accent: #ef4444; --text: #e2e8f0; --border: #334155; }}
        body {{ background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; padding: 40px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #fff; }}
        .meta {{ color: #94a3b8; margin-bottom: 20px; }}
        table.dataTable {{ width: 100% !important; margin-top: 20px !important; border-collapse: collapse !important; }}
        table.dataTable thead th {{ background: #1e293b; color: #fff; padding: 12px; border-bottom: 2px solid var(--accent); text-align: left; }}
        table.dataTable tbody td {{ background: var(--card); color: #ccc; padding: 10px; border-bottom: 1px solid var(--border); }}
        .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); }}
        .file-name {{ font-weight: 600; color: #fff; }}
        .file-path {{ font-family: monospace; color: #64748b; font-size: 0.8rem; }}
        .dataTables_wrapper select, .dataTables_wrapper input {{ background: #0f1115; border: 1px solid var(--border); color: #fff; padding: 5px; border-radius: 4px; }}
        .paginate_button.current {{ background: var(--accent) !important; border: none !important; color: white !important; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📺 Series Candidatas a Mover</h1>
        <div class="meta">Generado: {ts} | Umbral: > {umbral}% mala calidad</div>
        <table id="seriesTable" class="display">
            <thead><tr><th width="15%">Calidad</th><th width="15%">Categoría</th><th width="15%">Caps Afectados</th><th>Serie / Ruta</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>
    <script>$(document).ready(function() {{ $('#seriesTable').DataTable({{ "order": [[ 0, "desc" ]] }}); }});</script>
</body>
</html>"""

    with open(REPORT_FILENAME, "w", encoding="utf-8") as f: f.write(html_content)
    return REPORT_FILENAME

# ==========================================
# GENERADOR SCRIPT .SH
# ==========================================
def generar_script_sh(series_afectadas):
    dest_root = os.path.join(PATH_SERIES_ROOT, CARPETA_UPLOADS, SUB_CARPETA_BAJA_CALIDAD)
    
    with open(SH_FILENAME, "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\n")
        f.write(f"# Script generado el {datetime.now()}\n")
        f.write(f"# Destino Base: {dest_root}\n\n")
        
        for ruta_serie, datos in series_afectadas.items():
            categoria = datos['categoria']
            dest_category_folder = os.path.join(dest_root, categoria)
            
            # Escapado básico para bash
            src_safe = ruta_serie.replace('"', '\\"')
            dest_cat_safe = dest_category_folder.replace('"', '\\"')
            
            f.write(f'mkdir -p "{dest_cat_safe}"\n')
            f.write(f'mv "{src_safe}" "{dest_cat_safe}/"\n')
            
    os.chmod(SH_FILENAME, 0o755)
    return SH_FILENAME

# ==========================================
# MAIN
# ==========================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--porcentaje", type=int, default=80, help="Porcentaje mínimo de caps malos")
    args = parser.parse_args()

    print_header(f"SCANNER SERIES (Umbral: {args.porcentaje}%)")
    
    if not os.path.exists(PATH_SERIES_ROOT):
        print(f"{Color.FAIL}❌ Ruta no encontrada: {PATH_SERIES_ROOT}{Color.ENDC}")
        return

    try:
        categorias = [d for d in os.listdir(PATH_SERIES_ROOT) 
                      if os.path.isdir(os.path.join(PATH_SERIES_ROOT, d)) and d != CARPETA_UPLOADS]
    except OSError: return

    series_stats = {}
    total_scan = 0
    
    for cat in categorias:
        path_cat = os.path.join(PATH_SERIES_ROOT, cat)
        print(f"🔎 Analizando: {cat}", flush=True)
        try: series_dirs = [d for d in os.listdir(path_cat) if os.path.isdir(os.path.join(path_cat, d))]
        except: continue
        
        for serie in series_dirs:
            path_serie = os.path.join(path_cat, serie)
            caps_total = 0; caps_malos = 0
            
            for root, dirs, files in os.walk(path_serie):
                for f in files:
                    if os.path.splitext(f)[1].lower() in VIDEO_EXT:
                        caps_total += 1
                        if es_baja_calidad(detectar_resolucion(f)): caps_malos += 1
            
            if caps_total > 0:
                pct_malo = (caps_malos / caps_total) * 100
                if pct_malo >= args.porcentaje:
                    series_stats[path_serie] = {
                        "categoria": cat, "total_caps": caps_total, "malos": caps_malos, "umbral": args.porcentaje 
                    }
                    print(f"   ❌ Detectada: {serie} ({int(pct_malo)}%)")
            
            total_scan += 1

    count = len(series_stats)
    print_header(f"RESULTADOS: {count} SERIES CANDIDATAS")

    if count == 0:
        print(f"{Color.GREEN}¡Limpio! Ninguna serie supera el umbral.{Color.ENDC}")
        return

    html_path = generar_html(series_stats)
    sh_path = generar_script_sh(series_stats)

    print(f"\n{Color.GREEN}✅ Archivos generados:{Color.ENDC}")
    print(f"📄 HTML: {html_path}")
    print(f"📜 SH:   {sh_path}")
    print(f"\n{Color.WARNING}⚠️  Revisa el .sh antes de ejecutarlo.{Color.ENDC}")

if __name__ == "__main__":
    main()
