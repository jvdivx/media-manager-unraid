#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import shutil
from pathlib import Path
from datetime import datetime

# ==========================================
# CONFIGURACIÓN
# ==========================================
TARGET_DIRS = [
    Path("/mnt/user/peliculas"),
    Path("/mnt/user/series")
]

REPORT_FILE = Path("/mnt/user/appdata/media-manager/datos/report_02_permissions.html")
REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)

# Unraid Standard
UID = 99   # nobody
GID = 100  # users
DIR_MODE = 0o2775  # drwxrwsr-x
FILE_MODE = 0o664  # -rw-rw-r--

# Colores consola
class Color:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

# ==========================================
# LÓGICA
# ==========================================
stats = {
    "scanned_files": 0,
    "scanned_dirs": 0,
    "fixed_ownership": 0,
    "fixed_perms": 0,
    "errors": [],
    "start_time": 0,
    "end_time": 0
}

def check_and_fix(path, is_dir):
    changed = False
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return

    # 1. Check Owner/Group
    if st.st_uid != UID or st.st_gid != GID:
        try:
            os.chown(path, UID, GID)
            stats["fixed_ownership"] += 1
            changed = True
        except Exception as e:
            stats["errors"].append(f"CHOWN Error {path}: {e}")

    # 2. Check Mode
    # Máscara para ignorar bits irrelevantes, nos interesa 777 + setgid
    current_mode = st.st_mode & 0o7777
    target = DIR_MODE if is_dir else FILE_MODE
    
    if current_mode != target:
        try:
            os.chmod(path, target)
            stats["fixed_perms"] += 1
            changed = True
        except Exception as e:
            stats["errors"].append(f"CHMOD Error {path}: {e}")
    
    return changed

def process_recursive(base_path):
    print(f"{Color.BLUE}📂 Escaneando: {base_path}{Color.ENDC}")
    
    # Fix raiz
    check_and_fix(base_path, is_dir=True)
    stats["scanned_dirs"] += 1

    for root, dirs, files in os.walk(base_path):
        # Directorios
        for d in dirs:
            d_path = os.path.join(root, d)
            check_and_fix(d_path, is_dir=True)
            stats["scanned_dirs"] += 1

        # Archivos
        for f in files:
            f_path = os.path.join(root, f)
            check_and_fix(f_path, is_dir=False)
            stats["scanned_files"] += 1
            
            if stats["scanned_files"] % 2000 == 0:
                print(f"   ... {stats['scanned_files']} archivos analizados ...")

# ==========================================
# REPORTE HTML
# ==========================================
def generar_html():
    duration = stats["end_time"] - stats["start_time"]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    total_items = stats["scanned_files"] + stats["scanned_dirs"]
    total_fixed = stats["fixed_ownership"] + stats["fixed_perms"] # Aproximado, un archivo puede tener ambos fixes
    
    css = """
    <style>
        :root { --bg: #0f172a; --card: #1e293b; --text: #f1f5f9; --accent: #6366f1; --ok: #10b981; --err: #ef4444; }
        body { font-family: sans-serif; background: var(--bg); color: var(--text); padding: 40px; margin: 0; }
        .container { max-width: 1000px; margin: 0 auto; }
        h1 { font-weight: 300; margin-bottom: 10px; }
        .meta { color: #94a3b8; margin-bottom: 40px; font-size: 0.9rem; }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 40px; }
        .card { background: var(--card); padding: 20px; border-radius: 12px; border: 1px solid #334155; text-align: center; }
        .card .val { font-size: 2rem; font-weight: bold; display: block; margin-bottom: 5px; }
        .card .lbl { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; }
        .c-accent { color: var(--accent); }
        .c-ok { color: var(--ok); }
        .c-err { color: var(--err); }

        .error-box { background: #2d1a1a; border: 1px solid var(--err); border-radius: 8px; padding: 20px; margin-top: 20px; }
        .error-box h3 { color: var(--err); margin-top: 0; }
        .error-list { font-family: monospace; color: #fca5a5; font-size: 0.9rem; }
        
        .success-box { background: rgba(16, 185, 129, 0.1); border: 1px solid var(--ok); padding: 15px; border-radius: 8px; text-align: center; color: var(--ok); }
    </style>
    """

    html = f"""
    <!DOCTYPE html><html><head><meta charset='utf-8'><title>Reporte Permisos</title>{css}</head>
    <body>
        <div class="container">
            <h1>🛡️ Reporte de Permisos</h1>
            <div class="meta">Generado: {ts} | Duración: {duration:.2f}s</div>

            <div class="grid">
                <div class="card"><span class="val">{total_items}</span><span class="lbl">Items Escaneados</span></div>
                <div class="card"><span class="val c-accent">{stats['fixed_ownership']}</span><span class="lbl">Cambios de Dueño</span></div>
                <div class="card"><span class="val c-accent">{stats['fixed_perms']}</span><span class="lbl">Cambios de Permisos</span></div>
                <div class="card"><span class="val { 'c-ok' if not stats['errors'] else 'c-err' }">{len(stats['errors'])}</span><span class="lbl">Errores</span></div>
            </div>
    """

    if stats["errors"]:
        html += "<div class='error-box'><h3>⚠️ Errores Encontrados</h3><div class='error-list'>"
        for e in stats["errors"][:100]: # Limitamos a 100 para no explotar el HTML
            html += f"<div>{e}</div>"
        if len(stats["errors"]) > 100:
            html += f"<div>... y {len(stats['errors']) - 100} más.</div>"
        html += "</div></div>"
    else:
        html += f"""
        <div class="success-box">
            <h2>✅ Todo Correcto</h2>
            <p>Todos los archivos en las carpetas objetivo tienen ahora permisos <strong>nobody:users</strong>, <strong>2775</strong> (dirs) y <strong>664</strong> (files).</p>
        </div>
        """

    html += "</div></body></html>"

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"\n{Color.GREEN}📄 Reporte generado en: {REPORT_FILE}{Color.ENDC}")

# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    print(f"{Color.HEADER}=== REPARADOR DE PERMISOS UNRAID ==={Color.ENDC}")
    print(f"Objetivos: {[str(p) for p in TARGET_DIRS]}")
    print(f"Meta: nobody:users | Dirs 2775 | Files 664\n")
    
    stats["start_time"] = time.time()
    
    for target in TARGET_DIRS:
        if target.exists():
            process_recursive(target)
        else:
            print(f"{Color.FAIL}❌ Ruta no encontrada: {target}{Color.ENDC}")
            stats["errors"].append(f"Ruta no encontrada: {target}")

    stats["end_time"] = time.time()
    
    generar_html()
    print(f"\n{Color.GREEN}✅ Proceso finalizado.{Color.ENDC}")
