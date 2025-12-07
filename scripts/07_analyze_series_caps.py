#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
from datetime import datetime
from collections import defaultdict
from pathlib import Path

# ==========================================
# CONFIGURACIÓN
# ==========================================
BASE_PATH = "/mnt/user"
RUTAS_SERIES = {
    "Series HD": os.path.join(BASE_PATH, "series", "Series HD"),
    "Dibujos": os.path.join(BASE_PATH, "series", "Dibujos"),
    "Documentales": os.path.join(BASE_PATH, "series", "Documentales")
}

EXT_VIDEO = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m2ts', '.mpg', '.m4v'}

# Rutas Normalizadas
SCRIPT_DIR = Path("/mnt/user/appdata/media-manager/datos")
SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
INFORME_HTML = SCRIPT_DIR / "report_07_series_caps.html"

# ==========================================
# CLASES DE UTILIDAD
# ==========================================
class Color:
    HEADER = '\033[95m'; BLUE = '\033[94m'; GREEN = '\033[92m'; WARNING = '\033[93m'; FAIL = '\033[91m'; ENDC = '\033[0m'; BOLD = '\033[1m'

def detectar_calidad(nombre_archivo):
    nombre = nombre_archivo.lower()
    if '2160p' in nombre or '4k' in nombre: return '2160p'
    if '1080p' in nombre: return '1080p'
    if '720p' in nombre: return '720p'
    if '576p' in nombre: return '576p'
    if '480p' in nombre: return '480p'
    return 'SD/Otros'

def procesar_series():
    print(f"\n{Color.HEADER}=== ANALIZANDO RESOLUCIONES (SERIES) ==={Color.ENDC}", flush=True)
    
    resultados_por_categoria = []
    
    # KPI Globales
    total_series = 0
    total_episodios = 0
    series_mezcladas = 0

    for nombre_cat, ruta_base in RUTAS_SERIES.items():
        if not os.path.exists(ruta_base): continue
        
        print(f"📂 Analizando categoría: {nombre_cat}...", flush=True)
        
        datos_series = defaultdict(lambda: defaultdict(int))
        
        try:
            series_lista = [d for d in os.listdir(ruta_base) if os.path.isdir(os.path.join(ruta_base, d))]
        except OSError: continue

        total_cat = len(series_lista)
        procesados = 0
        
        for serie in series_lista:
            procesados += 1
            if procesados % 100 == 0:
                print(f"   ... {procesados}/{total_cat} series analizadas", flush=True)
                
            ruta_serie = os.path.join(ruta_base, serie)
            
            for root, _, files in os.walk(ruta_serie):
                for f in files:
                    if os.path.splitext(f)[1].lower() in EXT_VIDEO:
                        calidad = detectar_calidad(f)
                        datos_series[serie][calidad] += 1
                        datos_series[serie]["total"] += 1

        items_html = []
        for serie, counts in datos_series.items():
            total = counts["total"]
            total_episodios += total
            
            # Detectar si hay mezcla (más de una calidad HD distinta)
            calidades_presentes = sum(1 for k in ['2160p','1080p','720p'] if counts[k] > 0)
            es_mezcla = calidades_presentes > 1
            if es_mezcla: series_mezcladas += 1
            
            items_html.append({
                "Titulo": serie,
                "2160p": counts['2160p'],
                "1080p": counts['1080p'],
                "720p": counts['720p'],
                "SD": counts['576p'] + counts['480p'] + counts['SD/Otros'],
                "Total": total,
                "Mezcla": es_mezcla
            })
        
        total_series += len(items_html)
        resultados_por_categoria.append({
            "categoria": nombre_cat,
            "items": items_html
        })

    print(f"\n{Color.GREEN}✅ Análisis completado.{Color.ENDC}", flush=True)
    generar_html_pro(resultados_por_categoria, total_series, total_episodios, series_mezcladas)

def generar_html_pro(datos, t_series, t_eps, t_mezcla):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    css = """
    <style>
        :root { --bg-color: #121212; --card-bg: #1e1e1e; --text-main: #e0e0e0; --text-muted: #a0a0a0; --accent: #00bcd4; --accent-hover: #26c6da; --border: #333; --warn-color: #ff9800; --ok-color: #69f0ae; }
        body { font-family: 'Segoe UI', Roboto, sans-serif; background-color: var(--bg-color); color: var(--text-main); margin: 0; padding: 40px; }
        .container { max-width: 1600px; margin: 0 auto; }
        .header { margin-bottom: 40px; border-bottom: 1px solid var(--border); padding-bottom: 20px; display: flex; justify-content: space-between; align-items: end; }
        .header h1 { margin: 0; font-size: 2.5rem; font-weight: 300; color: #fff; }
        .meta { color: var(--text-muted); font-size: 0.9rem; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 40px; }
        .stat-card { background: var(--card-bg); padding: 20px; border-radius: 12px; border: 1px solid var(--border); display: flex; flex-direction: column; }
        .stat-label { color: var(--text-muted); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px; }
        .stat-value { font-size: 2rem; font-weight: 600; color: #fff; margin-top: 10px; }
        .stat-card.info { border-left: 4px solid var(--accent); }
        .stat-card.warn { border-left: 4px solid var(--warn-color); }
        .category-section { margin-bottom: 20px; background: var(--card-bg); border-radius: 16px; overflow: hidden; border: 1px solid var(--border); box-shadow: 0 4px 10px rgba(0,0,0,0.2); transition: all 0.3s ease; }
        .cat-header { background: #252525; padding: 15px 30px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; cursor: pointer; user-select: none; }
        .cat-header:hover { background: #2f2f2f; }
        .cat-title-group { display: flex; align-items: center; }
        .cat-header h2 { margin: 0; font-size: 1.4rem; color: #fff; }
        .badge-count { background: var(--accent); color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; margin-left: 15px; font-weight: bold; }
        .toggle-icon { margin-right: 15px; transition: transform 0.3s ease; font-size: 0.8rem; color: var(--text-muted); }
        .controls-group { display: flex; gap: 10px; align-items: center; }
        .category-section.collapsed .cat-content { display: none; }
        .category-section.collapsed .toggle-icon { transform: rotate(-90deg); }
        .category-section.collapsed .cat-header { border-bottom: none; }
        .cat-content { animation: fadeIn 0.3s ease-in-out; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        .search-input { background: #121212; border: 1px solid #444; color: #fff; padding: 8px 15px; border-radius: 20px; outline: none; font-size: 0.9rem; width: 200px; transition: border 0.2s; }
        .search-input:focus { border-color: var(--accent); }
        .filter-btn { background: transparent; border: 1px solid #444; color: #aaa; padding: 8px 12px; border-radius: 20px; cursor: pointer; font-size: 0.85rem; transition: all 0.2s; display: flex; align-items: center; gap: 5px; }
        .filter-btn:hover { background: #333; color: #fff; }
        .filter-btn.active { background: var(--warn-color); border-color: var(--warn-color); color: #121212; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; padding: 15px 20px; background: #2a2a2a; color: var(--text-muted); font-weight: 600; font-size: 0.9rem; cursor: pointer; user-select: none; border-bottom: 2px solid var(--border); }
        th:hover { color: #fff; background: #333; }
        td { padding: 12px 20px; border-bottom: 1px solid var(--border); font-size: 0.95rem; vertical-align: middle; text-align: center; }
        td:first-child { text-align: left; font-weight: 600; color: #fff; }
        tr:hover { background-color: rgba(255,255,255,0.02); }
        .res-badge { display: inline-block; padding: 4px 12px; border-radius: 6px; background: #333; color: #ccc; min-width: 30px; }
        .res-badge.active { color: #fff; font-weight: bold; }
        .badge-4k { background: #311b92; color: #b388ff; }
        .badge-1080 { background: #004d40; color: #69f0ae; }
        .badge-720 { background: #01579b; color: #4fc3f7; }
        .badge-sd { background: #3e2723; color: #ffccbc; }
        .pagination { padding: 15px 30px; background: #252525; border-top: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
        .page-btn { background: var(--accent); color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 0.9rem; }
        .page-btn:hover { background: var(--accent-hover); }
        .page-btn:disabled { background: #444; cursor: not-allowed; color: #888; }
        .page-info { color: var(--text-muted); }
        .hidden { display: none; }
    </style>

    <script>
    document.addEventListener('DOMContentLoaded', () => {
        const ROWS_PER_PAGE = 50;
        document.querySelectorAll('.cat-header').forEach(header => {
            header.addEventListener('click', (e) => {
                if (e.target.closest('.controls-group')) return;
                header.closest('.category-section').classList.toggle('collapsed');
            });
        });
        document.querySelectorAll('.category-section').forEach(section => {
            const tableBody = section.querySelector('tbody');
            const rows = Array.from(tableBody.querySelectorAll('tr'));
            const prevBtn = section.querySelector('.btn-prev');
            const nextBtn = section.querySelector('.btn-next');
            const pageInfo = section.querySelector('.page-info');
            const searchInput = section.querySelector('.search-input');
            const filterBtn = section.querySelector('.filter-btn');
            let currentPage = 1; let filteredRows = rows; let showMixedOnly = false;

            function updateTable() {
                rows.forEach(r => r.classList.add('hidden'));
                const totalPages = Math.ceil(filteredRows.length / ROWS_PER_PAGE) || 1;
                if (currentPage > totalPages) currentPage = 1;
                const start = (currentPage - 1) * ROWS_PER_PAGE;
                filteredRows.slice(start, start + ROWS_PER_PAGE).forEach(r => r.classList.remove('hidden'));
                pageInfo.textContent = `Página ${currentPage} de ${totalPages} (Total: ${filteredRows.length})`;
                prevBtn.disabled = currentPage === 1;
                nextBtn.disabled = currentPage === totalPages;
            }
            function applyFilters() {
                const term = searchInput.value.toLowerCase();
                filteredRows = rows.filter(row => {
                    const matchesSearch = row.cells[0].textContent.toLowerCase().includes(term);
                    const isMixed = row.classList.contains('row-mixed');
                    return matchesSearch && (showMixedOnly ? isMixed : true);
                });
                currentPage = 1; updateTable();
            }
            searchInput.addEventListener('input', applyFilters);
            filterBtn.addEventListener('click', () => { showMixedOnly = !showMixedOnly; filterBtn.classList.toggle('active'); applyFilters(); });
            prevBtn.addEventListener('click', () => { if (currentPage > 1) { currentPage--; updateTable(); } });
            nextBtn.addEventListener('click', () => { if (currentPage < Math.ceil(filteredRows.length / ROWS_PER_PAGE)) { currentPage++; updateTable(); } });
            const getCellValue = (tr, idx) => tr.children[idx].innerText || tr.children[idx].textContent;
            const comparer = (idx, asc) => (a, b) => {
                const v1 = getCellValue(asc ? a : b, idx); const v2 = getCellValue(asc ? b : a, idx);
                const n1 = parseFloat(v1); const n2 = parseFloat(v2);
                if (!isNaN(n1) && !isNaN(n2)) return n1 - n2;
                return v1.toString().localeCompare(v2);
            };
            section.querySelectorAll('th').forEach(th => th.addEventListener('click', (() => {
                const idx = Array.from(th.parentNode.children).indexOf(th);
                const asc = !th.classList.contains('asc');
                section.querySelectorAll('th').forEach(h => { if (h !== th) h.classList.remove('asc', 'desc'); });
                th.classList.toggle('asc', asc); th.classList.toggle('desc', !asc);
                rows.sort(comparer(idx, asc)); rows.forEach(tr => tableBody.appendChild(tr)); applyFilters();
            })));
            updateTable();
        });
    });
    </script>
    """

    html = f"""
    <!DOCTYPE html><html><head><meta charset='utf-8'><title>Informe Resoluciones</title>{css}</head>
    <body>
        <div class="container">
            <div class="header"><h1>🎬 Informe de Resoluciones</h1><div class="meta">Generado: {ts}</div></div>
            <div class="stats-grid">
                <div class="stat-card info"><div class="stat-label">Total Series</div><div class="stat-value">{t_series}</div></div>
                <div class="stat-card info"><div class="stat-label">Total Episodios</div><div class="stat-value">{t_eps}</div></div>
                <div class="stat-card warn"><div class="stat-label">Series con Mezcla</div><div class="stat-value">{t_mezcla}</div></div>
            </div>
    """

    for grupo in datos:
        html += f"""
        <div class="category-section collapsed">
            <div class="cat-header">
                <div class="cat-title-group"><span class="toggle-icon">▼</span><h2>{grupo['categoria']}</h2><span class="badge-count">{len(grupo['items'])}</span></div>
                <div class="controls-group"><button class="filter-btn">⚠️ Solo Mezclas</button><input type="text" class="search-input" placeholder="🔍 Buscar..."></div>
            </div>
            <div class="cat-content">
                <table>
                    <thead><tr><th>Serie</th><th>2160p</th><th>1080p</th><th>720p</th><th>SD/Otros</th><th>TOTAL</th></tr></thead>
                    <tbody>
        """
        items_ord = sorted(grupo["items"], key=lambda x: x['Titulo'])
        for i in items_ord:
            b_4k = f'class="res-badge badge-4k active"' if i['2160p'] > 0 else 'class="res-badge"'
            b_1080 = f'class="res-badge badge-1080 active"' if i['1080p'] > 0 else 'class="res-badge"'
            b_720 = f'class="res-badge badge-720 active"' if i['720p'] > 0 else 'class="res-badge"'
            b_sd = f'class="res-badge badge-sd active"' if i['SD'] > 0 else 'class="res-badge"'
            row_class = "row-mixed" if i['Mezcla'] else ""
            
            html += f"""<tr class="{row_class}"><td>{i['Titulo']}</td><td><span {b_4k}>{i['2160p']}</span></td><td><span {b_1080}>{i['1080p']}</span></td><td><span {b_720}>{i['720p']}</span></td><td><span {b_sd}>{i['SD']}</span></td><td><strong>{i['Total']}</strong></td></tr>"""
            
        html += """</tbody></table><div class="pagination"><button class="page-btn btn-prev">Anterior</button><span class="page-info">1/X</span><button class="page-btn btn-next">Siguiente</button></div></div></div>"""
    
    html += "</div></body></html>"
    
    with open(INFORME_HTML, "w", encoding="utf-8") as f: f.write(html)
    print(f"\n📄 Informe HTML generado: {INFORME_HTML}", flush=True)

if __name__ == "__main__":
    procesar_series()
