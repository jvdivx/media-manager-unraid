import os
import re
import sys
from collections import Counter, defaultdict
import datetime

# --- CONFIGURACIÓN ---
BASE_PATH = "/mnt/user/series/Uploads/BajaCalidad"
LOGS_DIR = "/mnt/user/appdata/media-manager/datos"
OUTPUT_FILE = os.path.join(LOGS_DIR, "report_08_baja_calidad.html")

TARGET_CATEGORIES = ["Dibujos", "Series HD"]
VIDEO_EXTENSIONS = ('.mkv', '.mp4', '.avi', '.m4v', '.divx', '.wmv', '.mpg')

# Regex
RES_REGEX = re.compile(r'(\d{3,4}[pP])')
YEAR_REGEX = re.compile(r'\((\d{4})\)') # Busca (1999) o (2024)

# --- ESTILOS CSS (Oscuro + DataTables) ---
CSS_STYLE = """
<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
<style>
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #1e1e1e; color: #e0e0e0; margin: 20px; }
    h1 { text-align: center; color: #4da6ff; margin-bottom: 10px; }
    h2 { border-bottom: 2px solid #4da6ff; padding-bottom: 5px; color: #ffffff; margin-top: 40px; }
    .container { max-width: 98%; margin: 0 auto; background: #252526; padding: 20px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
    
    table.dataTable { width: 100% !important; border-collapse: collapse; font-size: 0.9em; color: #e0e0e0; }
    table.dataTable thead th { background-color: #333337; color: #4da6ff; border-bottom: 1px solid #4da6ff; padding: 12px; }
    table.dataTable tbody td { background-color: #252526; border-bottom: 1px solid #3e3e42; padding: 8px 12px; vertical-align: middle; }
    table.dataTable tbody tr:hover td { background-color: #2d2d30 !important; }
    
    .res-badge { background-color: #0e639c; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; font-weight: bold; }
    .res-sub-badge { background-color: #3a3d41; color: #9cdcfe; padding: 1px 4px; border-radius: 3px; font-size: 0.85em; margin-right: 4px; border: 1px solid #555; }
    .size-cell { font-family: 'Consolas', monospace; color: #b5cea8; }
    .year-cell { color: #dcdcaa; font-weight: bold; text-align: center; }
    .details-cell { font-size: 0.85em; color: #cccccc; }
    .summary-box { background: #333337; padding: 15px; border-radius: 5px; margin-bottom: 20px; border-left: 5px solid #4da6ff; }

    /* DataTables Overrides Dark Mode */
    .dataTables_wrapper .dataTables_length, .dataTables_wrapper .dataTables_filter, 
    .dataTables_wrapper .dataTables_info, .dataTables_wrapper .dataTables_paginate { color: #e0e0e0 !important; margin-bottom: 10px; }
    .dataTables_wrapper .dataTables_filter input, .dataTables_wrapper .dataTables_length select {
        background-color: #333337; color: #e0e0e0; border: 1px solid #4da6ff; padding: 5px; border-radius: 4px;
    }
    .dataTables_wrapper .dataTables_paginate .paginate_button { color: #e0e0e0 !important; }
    .dataTables_wrapper .dataTables_paginate .paginate_button.current { background: #4da6ff !important; color: #fff !important; border: none; }
    .dataTables_wrapper .dataTables_paginate .paginate_button:hover { background: #3e3e42 !important; color: #fff !important; border: 1px solid #4da6ff; }
</style>
"""

JS_SCRIPT = """
<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
<script>
$(document).ready(function() {
    $('table.display').DataTable({
        "pageLength": 10,
        "lengthMenu": [ [10, 25, 50, 100, -1], [10, 25, 50, 100, "Todos"] ],
        "order": [[ 0, "asc" ]],
        "language": {
            "lengthMenu": "Mostrar _MENU_ series",
            "zeroRecords": "Sin resultados",
            "info": "Página _PAGE_ de _PAGES_",
            "infoEmpty": "Vacío",
            "infoFiltered": "(filtrado de _MAX_)",
            "search": "🔍 Buscar:",
            "paginate": { "first": "<<", "last": ">>", "next": ">", "previous": "<" }
        }
    });
});
</script>
"""

def get_readable_size(size_in_bytes):
    original = size_in_bytes
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}", original
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} PB", original

def get_majority_resolution(resolutions_list):
    if not resolutions_list: return "N/A"
    valid_res = [r for r in resolutions_list if r != "N/A"]
    if not valid_res: return "N/A"
    return Counter(valid_res).most_common(1)[0][0]

def extract_season_number(season_name):
    """Extrae el número de la temporada para ordenar correctamente (9, 10, 11)."""
    if season_name == "Raíz": return 0
    nums = re.findall(r'\d+', season_name)
    return int(nums[0]) if nums else 9999

def analyze_category(category_name, category_path):
    data = []
    if not os.path.exists(category_path):
        print(f"  [!] La ruta {category_path} no existe.")
        return data
        
    try:
        series_dirs = sorted([d for d in os.listdir(category_path) if os.path.isdir(os.path.join(category_path, d))])
    except PermissionError:
        return data

    total_series = len(series_dirs)
    if total_series == 0:
        print(f"  [i] Carpeta '{category_name}' vacía.")
        return data

    print(f"  > Escaneando {total_series} series en {category_name}...")

    for i, series in enumerate(series_dirs, 1):
        print(f"    [{i}/{total_series}] Analizando: {series}")
        series_path = os.path.join(category_path, series)
        
        # Extraer Año
        year_match = YEAR_REGEX.search(series)
        series_year = year_match.group(1) if year_match else "-"

        total_size = 0
        # Estructura: season_info[nombre_temp] = {'count': 0, 'res_list': []}
        season_info = defaultdict(lambda: {'count': 0, 'res_list': []})
        all_resolutions = []
        
        for root, dirs, files in os.walk(series_path):
            video_files = [f for f in files if f.lower().endswith(VIDEO_EXTENSIONS)]
            if not video_files: continue

            rel_path = os.path.relpath(root, series_path)
            season_name = "Raíz" if rel_path == "." else rel_path.split(os.sep)[0]

            for vfile in video_files:
                fpath = os.path.join(root, vfile)
                try:
                    total_size += os.path.getsize(fpath)
                except: pass
                
                # Detectar resolución
                match = RES_REGEX.search(vfile)
                res = match.group(1).lower() if match else "N/A"
                
                # Guardar datos globales y por temporada
                all_resolutions.append(res)
                season_info[season_name]['count'] += 1
                season_info[season_name]['res_list'].append(res)

        if season_info:
            maj_res_global = get_majority_resolution(all_resolutions)
            size_str, size_bytes = get_readable_size(total_size)
            
            # Procesar detalles por temporada (Orden Numérico y Resolución individual)
            # Convertimos a lista y ordenamos usando la función extract_season_number
            sorted_seasons = sorted(season_info.items(), key=lambda x: extract_season_number(x[0]))
            
            details_parts = []
            for s_name, s_data in sorted_seasons:
                s_maj_res = get_majority_resolution(s_data['res_list'])
                s_count = s_data['count']
                # Formato: Season 01 [720p]: 12
                details_parts.append(f"{s_name} <span class='res-sub-badge'>{s_maj_res}</span>: <b>{s_count}</b>")
            
            details_str = " <span style='color:#666'>|</span> ".join(details_parts)
            
            data.append({
                "name": series,
                "year": series_year,
                "res": maj_res_global,
                "size_str": size_str,
                "size_bytes": size_bytes,
                "seasons": len(season_info),
                "episodes": sum(s['count'] for s in season_info.values()),
                "details": details_str
            })
    
    print(f"    [OK] Fin {category_name}. {len(data)} series procesadas.")
    return data

def generate_html():
    if not os.path.exists(LOGS_DIR):
        try: os.makedirs(LOGS_DIR)
        except: pass

    print(f"{'='*60}\n REPORTE AVANZADO: BAJA CALIDAD\n{'='*60}")
    
    html_content = f"<!DOCTYPE html><html><head><title>Reporte Baja Calidad</title><meta charset=\"utf-8\">{CSS_STYLE}</head><body>"
    html_content += f"<div class=\"container\"><h1>📊 Reporte de Contenido: Baja Calidad</h1><div class=\"summary-box\">Generado: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</div>"

    for idx, category in enumerate(TARGET_CATEGORIES):
        print(f"\n>>> Categoría: {category.upper()}")
        cat_path = os.path.join(BASE_PATH, category)
        rows = analyze_category(category, cat_path)
        
        table_id = f"table_{idx}"
        html_content += f"<h2>📂 {category}</h2>"
        
        if not rows:
            html_content += "<p>Sin contenido.</p>"
            continue

        html_content += f'<table id="{table_id}" class="display"><thead><tr>'
        # Nueva columna Año añadida
        headers = ["Serie", "Año", "Res. Global", "Tamaño", "Temp.", "Caps", "Detalle (Res : Caps)"]
        for h in headers: html_content += f"<th>{h}</th>"
        html_content += "</tr></thead><tbody>"
        
        for row in rows:
            html_content += f"""
            <tr>
                <td data-order="{row['name']}"><b>{row['name']}</b></td>
                <td class="year-cell">{row['year']}</td>
                <td><span class="res-badge">{row['res']}</span></td>
                <td class="size-cell" data-order="{row['size_bytes']}">{row['size_str']}</td>
                <td data-order="{row['seasons']}">{row['seasons']}</td>
                <td data-order="{row['episodes']}">{row['episodes']}</td>
                <td class="details-cell">{row['details']}</td>
            </tr>"""
        html_content += "</tbody></table>"

    html_content += f"</div>{JS_SCRIPT}</body></html>"

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"\n{'='*60}\n OK: Reporte guardado en:\n {OUTPUT_FILE}\n{'='*60}")

if __name__ == "__main__":
    generate_html()
