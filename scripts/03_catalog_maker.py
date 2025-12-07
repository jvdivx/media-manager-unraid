#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import html
import sys
from datetime import datetime
from pathlib import Path

# ==========================================
# CONFIGURACIÓN
# ==========================================
BASE_PATH = Path("/mnt/user")
OUTPUT_DIR = Path("/mnt/user/appdata/media-manager/datos")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FILE_MOVIES = OUTPUT_DIR / "catalog_movies.html"
FILE_SERIES = OUTPUT_DIR / "catalog_series.html"

RUTAS_PELICULAS = {
    "Peliculas HD": BASE_PATH / "peliculas/Peliculas HD",
    "Documentales": BASE_PATH / "peliculas/Documentales",
    "Conciertos": BASE_PATH / "peliculas/Conciertos"
}

RUTAS_SERIES = {
    "Series": BASE_PATH / "series/Series HD",
    "Dibujos": BASE_PATH / "series/Dibujos",
    "Documentales": BASE_PATH / "series/Documentales"
}

# LISTA COMPLETA DE EXTENSIONES DE VIDEO
VID_EXT = {
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m2ts', '.mpg', '.mpeg', 
    '.m4v', '.vob', '.ts', '.ogm', '.flv', '.iso', '.webm', '.divx', 
    '.3gp', '.asf', '.rmvb', '.mts'
}

# ==========================================
# LÓGICA DE ESCANEO (OPTIMIZADA 1 PASS)
# ==========================================
def escanear_contenido(rutas_dict, es_serie=False):
    items = []
    
    for categoria, path_obj in rutas_dict.items():
        if not path_obj.exists():
            continue
            
        print(f"📂 Categoría: {categoria}...", flush=True)
        
        try:
            entradas = sorted([x for x in path_obj.iterdir() if x.is_dir()])
        except OSError:
            continue

        total_entradas = len(entradas)
        print(f"   Detectados {total_entradas} elementos. Procesando...", flush=True)

        for i, entrada in enumerate(entradas, 1):
            if i % 50 == 0:
                print(f"   ... procesando {i}/{total_entradas}: {entrada.name}", flush=True)

            nombre = entrada.name
            
            # Variables acumuladoras
            total_size = 0
            video_count = 0
            has_nfo = False
            has_jpg = False
            
            # Recorrido único recursivo
            for root, dirs, files in os.walk(entrada):
                for file in files:
                    fp = os.path.join(root, file)
                    ext = Path(file).suffix.lower()
                    
                    # 1. Tamaño
                    try:
                        total_size += os.path.getsize(fp)
                    except OSError: pass

                    # 2. Detección
                    if ext in VID_EXT: video_count += 1
                    elif ext == '.nfo': has_nfo = True
                    elif ext in ['.jpg', '.png', '.jpeg', '.tbn']: has_jpg = True

            # Formatear tamaño
            gb = total_size / (1024**3)
            tamano_str = f"{gb:.2f} GB"

            item = {
                "Categoria": categoria,
                "Titulo": nombre,
                "Ruta": str(entrada),
                "Tamano": tamano_str,
                "Year": "-",
                "Estado": "OK",
                "Archivos": video_count,
                "NFO": has_nfo,
                "Cover": has_jpg,
                "Extras": "-"
            }

            # Extraer Año
            match = re.search(r'\((\d{4})\)', nombre)
            if match:
                item["Year"] = match.group(1)
            
            # Contar temporadas (solo si es serie)
            if es_serie:
                try:
                    temps = [x for x in entrada.iterdir() if x.is_dir() and ("season" in x.name.lower() or "temporada" in x.name.lower())]
                    if temps:
                        item["Extras"] = f"{len(temps)} Temps"
                except: pass

            items.append(item)

    return items

# ==========================================
# GENERADOR HTML
# ==========================================
def generar_html_individual(datos, titulo_informe, filepath):
    if not datos:
        print(f"⚠️ No hay datos para {titulo_informe}")
        return

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    css = """
    <style>
        :root { --bg-color: #121212; --card-bg: #1e1e1e; --text-main: #e0e0e0; --text-muted: #a0a0a0;
            --accent: #6366f1; --border: #333; --ok: #10b981; --err: #ef4444; }
        body { font-family: 'Segoe UI', Roboto, sans-serif; background: var(--bg-color); color: var(--text-main); margin: 0; padding: 40px; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 20px; }
        h1 { margin: 0; font-weight: 300; }
        
        .controls { background: #252525; padding: 15px; display: flex; gap: 15px; border: 1px solid var(--border); border-radius: 8px 8px 0 0; }
        input, select { background: #121212; border: 1px solid #444; color: #fff; padding: 8px; border-radius: 4px; outline: none; }
        
        table { width: 100%; border-collapse: collapse; background: var(--card-bg); border: 1px solid var(--border); }
        th { text-align: left; padding: 15px; background: #2a2a2a; color: var(--text-muted); cursor: pointer; }
        td { padding: 12px 15px; border-bottom: 1px solid var(--border); }
        .badge { padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }
        .b-yes { background: rgba(16, 185, 129, 0.15); color: var(--ok); }
        .b-no { background: rgba(239, 68, 68, 0.15); color: var(--err); }
        
        .pagination { padding: 15px; background: #252525; border: 1px solid var(--border); border-top: none; display: flex; justify-content: space-between; border-radius: 0 0 8px 8px; }
        button { background: var(--accent); color: white; border: none; padding: 6px 15px; border-radius: 4px; cursor: pointer; }
        button:disabled { background: #444; cursor: not-allowed; }
        .hidden { display: none !important; }
    </style>
    """

    js = """
    <script>
    document.addEventListener('DOMContentLoaded', () => {
        const rows = Array.from(document.querySelectorAll('tbody tr'));
        const search = document.getElementById('search');
        const rowsSel = document.getElementById('rowsPerPage');
        const pInfo = document.getElementById('pageInfo');
        const btnPrev = document.getElementById('prev');
        const btnNext = document.getElementById('next');
        
        let state = { page: 1, limit: 50, filter: '', data: rows };
        
        function update() {
            const term = state.filter.toLowerCase();
            const filtered = rows.filter(r => r.innerText.toLowerCase().includes(term));
            
            rows.forEach(r => r.classList.add('hidden'));
            
            const total = Math.ceil(filtered.length / state.limit) || 1;
            if(state.page > total) state.page = 1;
            
            const start = (state.page - 1) * state.limit;
            const end = start + parseInt(state.limit);
            
            filtered.slice(start, end).forEach(r => r.classList.remove('hidden'));
            
            pInfo.innerText = `Página ${state.page} de ${total} (${filtered.length} items)`;
            btnPrev.disabled = state.page === 1;
            btnNext.disabled = state.page === total;
        }

        search.addEventListener('input', e => { state.filter = e.target.value; state.page = 1; update(); });
        rowsSel.addEventListener('change', e => { state.limit = e.target.value; state.page = 1; update(); });
        btnPrev.addEventListener('click', () => { if(state.page > 1) state.page--; update(); });
        btnNext.addEventListener('click', () => { state.page++; update(); });
        
        update();
    });
    </script>
    """

    html_content = f"""
    <!DOCTYPE html><html><head><meta charset='utf-8'><title>{titulo_informe}</title>{css}{js}</head>
    <body><div class="container">
        <div class="header"><h1>{titulo_informe}</h1><div style="color:#888">{ts}</div></div>
        
        <div class="controls">
            <input type="text" id="search" placeholder="🔍 Buscar..." style="width:300px;">
            <select id="rowsPerPage">
                <option value="25">25</option><option value="50" selected>50</option><option value="100">100</option><option value="9999">Todo</option>
            </select>
        </div>

        <table>
            <thead><tr><th>Cat</th><th>Título</th><th>Año</th><th>Tamaño</th><th>Info</th><th>Meta</th></tr></thead>
            <tbody>
    """
    
    for item in datos:
        t_safe = html.escape(item['Titulo'])
        c_safe = html.escape(item['Categoria'])
        badges = f"<span class='badge {'b-yes' if item['NFO'] else 'b-no'}'>NFO</span> <span class='badge {'b-yes' if item['Cover'] else 'b-no'}'>IMG</span>"
        
        html_content += f"""
        <tr>
            <td><span class="badge" style="background:#333">{c_safe}</span></td>
            <td style="font-weight:bold; color:#fff">{t_safe}</td>
            <td>{item['Year']}</td>
            <td>{item['Tamano']}</td>
            <td style="color:#aaa; font-size:0.9rem">{item['Archivos']} files | {item['Extras']}</td>
            <td>{badges}</td>
        </tr>"""

    html_content += """
            </tbody>
        </table>
        <div class="pagination">
            <button id="prev">Anterior</button>
            <span id="pageInfo" style="color:#aaa; align-self:center"></span>
            <button id="next">Siguiente</button>
        </div>
    </div></body></html>
    """
    
    with open(filepath, "w", encoding="utf-8") as f: f.write(html_content)
    print(f"✅ Informe generado: {filepath}")

if __name__ == "__main__":
    print("🚀 Iniciando Escaneo (Full Ext)...", flush=True)
    
    print("\n=== SERIES ===", flush=True)
    d_series = escanear_contenido(RUTAS_SERIES, True)
    generar_html_individual(d_series, "Catálogo de Series", FILE_SERIES)
    
    print("\n=== PELÍCULAS ===", flush=True)
    d_movies = escanear_contenido(RUTAS_PELICULAS, False)
    generar_html_individual(d_movies, "Catálogo de Películas", FILE_MOVIES)
    
    print("\n🏁 Finalizado.", flush=True)
