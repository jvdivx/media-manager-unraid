#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Script 12: Análisis Completo de Calidades por Categoría
Analiza series y películas por categorías, cuenta ficheros por calidad,
calcula tamaños totales y genera informe HTML profesional compatible con app.py.
"""

import os
import re
from collections import defaultdict
from pathlib import Path
from datetime import datetime

# --- CONFIGURACIÓN DE RUTAS ---
SERIES_PATH = "/mnt/user/series"
PELICULAS_PATH = "/mnt/user/peliculas"

# Configuración de salida para integración con app.py (Docker)
# Si existe /app/datos (Docker), se usa. Si no, se usa ./reports local.
BASE_LOGS_DIR = "/app/datos"
if not os.path.exists(BASE_LOGS_DIR):
    BASE_LOGS_DIR = os.path.join(os.getcwd(), "reports")

OUTPUT_HTML = os.path.join(BASE_LOGS_DIR, "12_informe_calidades_categorias.html")

# --- PATRONES Y EXTENSIONES ---
QUALITY_PATTERNS = {
    "2160p": re.compile(r"2160p|4K|UHD", re.IGNORECASE),
    "1080p": re.compile(r"1080p|FHD", re.IGNORECASE),
    "720p": re.compile(r"720p|HD", re.IGNORECASE),
    "576p": re.compile(r"576p|DVD", re.IGNORECASE),
    "480p": re.compile(r"480p", re.IGNORECASE),
    "SD": re.compile(r"SD|360p|240p", re.IGNORECASE),
}

VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.m4v', '.ts', '.mpg', '.mpeg', '.wmv', '.flv', '.webm'}

# --- FUNCIONES AUXILIARES ---

def format_size(size_bytes):
    """Convierte bytes a formato legible."""
    if size_bytes is None: size_bytes = 0
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

def detect_quality(filename):
    """Detecta la calidad del archivo según su nombre."""
    for quality, pattern in QUALITY_PATTERNS.items():
        if pattern.search(filename):
            return quality
    return "Desconocida"

def is_video_file(filepath):
    """Verifica si el archivo es un vídeo válido."""
    return filepath.suffix.lower() in VIDEO_EXTENSIONS

# --- FUNCIONES DE ANÁLISIS ---

def analyze_series():
    """Analiza la estructura de series por categoría."""
    print("\n🎬 Analizando SERIES...")
    stats = defaultdict(lambda: defaultdict(lambda: {"count": 0, "size": 0}))
    
    series_base = Path(SERIES_PATH)
    if not series_base.exists():
        print(f"⚠️  La ruta {SERIES_PATH} no existe")
        return stats
    
    # Excluir carpetas especiales
    exclude_folders = {"Uploads", "BajaCalidad", "@eaDir"}
    
    # Iterar por categorías (primer nivel)
    for categoria in series_base.iterdir():
        if not categoria.is_dir() or categoria.name in exclude_folders:
            continue
        
        print(f"  📁 Categoría: {categoria.name}")
        
        # Iterar por series dentro de la categoría
        for serie in categoria.iterdir():
            if not serie.is_dir():
                continue
            
            # Buscar archivos de vídeo recursivamente
            for video_file in serie.rglob("*"):
                if video_file.is_file() and is_video_file(video_file):
                    quality = detect_quality(video_file.name)
                    size = video_file.stat().st_size
                    
                    stats[categoria.name][quality]["count"] += 1
                    stats[categoria.name][quality]["size"] += size
    
    return stats

def analyze_peliculas():
    """Analiza películas por categorías (Peliculas HD, Conciertos, Documentales, etc.)."""
    print("\n🎥 Analizando PELÍCULAS...")
    stats = defaultdict(lambda: defaultdict(lambda: {"count": 0, "size": 0}))
    
    peliculas_base = Path(PELICULAS_PATH)
    if not peliculas_base.exists():
        print(f"⚠️  La ruta {PELICULAS_PATH} no existe")
        return stats
    
    # Excluir carpetas especiales
    exclude_folders = {"BajaCalidad", "@eaDir"}
    
    # Iterar por categorías (primer nivel: Peliculas HD, Conciertos, Documentales)
    for categoria in peliculas_base.iterdir():
        if not categoria.is_dir() or categoria.name in exclude_folders:
            continue
        
        print(f"  📁 Categoría: {categoria.name}")
        
        # Buscar archivos de vídeo recursivamente dentro de cada categoría
        for video_file in categoria.rglob("*"):
            if video_file.is_file() and is_video_file(video_file):
                quality = detect_quality(video_file.name)
                size = video_file.stat().st_size
                
                stats[categoria.name][quality]["count"] += 1
                stats[categoria.name][quality]["size"] += size
    
    return stats

# --- GENERACIÓN DE REPORTES ---

def generate_html_report(series_stats, peliculas_stats):
    """Genera el informe HTML profesional."""
    print(f"\n📝 Generando informe HTML en: {OUTPUT_HTML}")
    
    # Crear directorio si no existe
    os.makedirs(os.path.dirname(OUTPUT_HTML), exist_ok=True)
    
    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Informe de Calidades por Categoría</title>
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.4/css/jquery.dataTables.min.css">
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: rgba(30, 30, 46, 0.95);
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }}
        h1 {{
            text-align: center;
            color: #00d9ff;
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 0 0 10px rgba(0, 217, 255, 0.5);
        }}
        .timestamp {{
            text-align: center;
            color: #888;
            margin-bottom: 30px;
        }}
        h2 {{
            color: #ff6b6b;
            border-bottom: 2px solid #ff6b6b;
            padding-bottom: 10px;
            margin-top: 40px;
        }}
        table {{
            width: 100%;
            margin: 20px 0;
            border-collapse: collapse;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            overflow: hidden;
        }}
        th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        tr:hover {{
            background: rgba(255, 255, 255, 0.08);
        }}
        .quality-2160p {{ color: #ff6b6b; font-weight: bold; }}
        .quality-1080p {{ color: #4ecdc4; font-weight: bold; }}
        .quality-720p {{ color: #95e1d3; }}
        .quality-576p {{ color: #f38181; }}
        .quality-480p {{ color: #feca57; }}
        .quality-sd {{ color: #a29bfe; }}
        .quality-desconocida {{ color: #636e72; }}
        .total-row {{
            background: rgba(0, 217, 255, 0.1);
            font-weight: bold;
            font-size: 1.1em;
        }}
        .dataTables_wrapper {{
            color: #e0e0e0;
        }}
        .dataTables_filter input {{
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid #667eea;
            color: white;
            padding: 5px 10px;
            border-radius: 5px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Informe de Calidades por Categoría</h1>
        <div class="timestamp">Generado: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}</div>
        
        <h2>🎬 Series por Categoría</h2>
        <table id="tableSeries" class="display">
            <thead>
                <tr>
                    <th>Categoría</th>
                    <th>2160p</th>
                    <th>1080p</th>
                    <th>720p</th>
                    <th>576p</th>
                    <th>480p</th>
                    <th>SD</th>
                    <th>Desconocida</th>
                    <th>Total Archivos</th>
                    <th>Tamaño Total</th>
                </tr>
            </thead>
            <tbody>
"""
    
    # --- TABLA SERIES ---
    total_series = defaultdict(lambda: {"count": 0, "size": 0})
    qualities = ["2160p", "1080p", "720p", "576p", "480p", "SD", "Desconocida"]
    
    for categoria in sorted(series_stats.keys()):
        html_content += f"                <tr>\n                    <td><strong>{categoria}</strong></td>\n"
        
        total_cat_count = 0
        total_cat_size = 0
        
        for quality in qualities:
            count = series_stats[categoria][quality]["count"]
            size = series_stats[categoria][quality]["size"]
            
            total_cat_count += count
            total_cat_size += size
            total_series[quality]["count"] += count
            total_series[quality]["size"] += size
            
            html_content += f"                    <td class='quality-{quality.lower()}'>{count} ({format_size(size)})</td>\n"
        
        html_content += f"                    <td><strong>{total_cat_count}</strong></td>\n"
        html_content += f"                    <td><strong>{format_size(total_cat_size)}</strong></td>\n"
        html_content += "                </tr>\n"
    
    # Totales Series
    html_content += "                <tr class='total-row'>\n                    <td>TOTAL SERIES</td>\n"
    grand_total_series_count = 0
    grand_total_series_size = 0
    
    for quality in qualities:
        count = total_series[quality]["count"]
        size = total_series[quality]["size"]
        grand_total_series_count += count
        grand_total_series_size += size
        html_content += f"                    <td>{count} ({format_size(size)})</td>\n"
    
    html_content += f"                    <td>{grand_total_series_count}</td>\n"
    html_content += f"                    <td>{format_size(grand_total_series_size)}</td>\n"
    html_content += "                </tr>\n"
    
    html_content += """            </tbody>
        </table>
        
        <h2>🎥 Películas por Categoría</h2>
        <table id="tablePeliculas" class="display">
            <thead>
                <tr>
                    <th>Categoría</th>
                    <th>2160p</th>
                    <th>1080p</th>
                    <th>720p</th>
                    <th>576p</th>
                    <th>480p</th>
                    <th>SD</th>
                    <th>Desconocida</th>
                    <th>Total Archivos</th>
                    <th>Tamaño Total</th>
                </tr>
            </thead>
            <tbody>
"""
    
    # --- TABLA PELÍCULAS ---
    total_peliculas = defaultdict(lambda: {"count": 0, "size": 0})
    
    for categoria in sorted(peliculas_stats.keys()):
        html_content += f"                <tr>\n                    <td><strong>{categoria}</strong></td>\n"
        
        total_cat_count = 0
        total_cat_size = 0
        
        for quality in qualities:
            count = peliculas_stats[categoria][quality]["count"]
            size = peliculas_stats[categoria][quality]["size"]
            
            total_cat_count += count
            total_cat_size += size
            total_peliculas[quality]["count"] += count
            total_peliculas[quality]["size"] += size
            
            html_content += f"                    <td class='quality-{quality.lower()}'>{count} ({format_size(size)})</td>\n"
        
        html_content += f"                    <td><strong>{total_cat_count}</strong></td>\n"
        html_content += f"                    <td><strong>{format_size(total_cat_size)}</strong></td>\n"
        html_content += "                </tr>\n"
    
    # Totales Películas
    html_content += "                <tr class='total-row'>\n                    <td>TOTAL PELÍCULAS</td>\n"
    grand_total_peliculas_count = 0
    grand_total_peliculas_size = 0
    
    for quality in qualities:
        count = total_peliculas[quality]["count"]
        size = total_peliculas[quality]["size"]
        grand_total_peliculas_count += count
        grand_total_peliculas_size += size
        html_content += f"                    <td>{count} ({format_size(size)})</td>\n"
    
    html_content += f"                    <td>{grand_total_peliculas_count}</td>\n"
    html_content += f"                    <td>{format_size(grand_total_peliculas_size)}</td>\n"
    html_content += "                </tr>\n"
    
    html_content += """            </tbody>
        </table>
        
        <script>
            $(document).ready(function() {{
                const tableConfig = {{
                    "pageLength": 25,
                    "order": [[0, "asc"]],
                    "language": {{
                        "url": "//cdn.datatables.net/plug-ins/1.13.4/i18n/es-ES.json"
                    }}
                }};
                
                $('#tableSeries').DataTable(tableConfig);
                $('#tablePeliculas').DataTable(tableConfig);
            }});
        </script>
    </div>
</body>
</html>"""
    
    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ Informe generado: {OUTPUT_HTML}")

def print_console_summary(series_stats, peliculas_stats):
    """Muestra resumen en consola."""
    print("\n" + "="*80)
    print("📊 RESUMEN DE CALIDADES".center(80))
    print("="*80)
    
    print("\n🎬 SERIES:")
    total_series = 0
    for categoria, qualities in sorted(series_stats.items()):
        cat_total = sum(q["count"] for q in qualities.values())
        total_series += cat_total
        print(f"  {categoria}: {cat_total} archivos")
    print(f"  TOTAL: {total_series} archivos")
    
    print("\n🎥 PELÍCULAS:")
    total_peliculas = 0
    for categoria, qualities in sorted(peliculas_stats.items()):
        cat_total = sum(q["count"] for q in qualities.values())
        total_peliculas += cat_total
        print(f"  {categoria}: {cat_total} archivos")
    print(f"  TOTAL: {total_peliculas} archivos")
    
    print("\n" + "="*80)

def main():
    """Función principal."""
    print("="*80)
    print("  ANÁLISIS DE CALIDADES POR CATEGORÍA".center(80))
    print("="*80)
    
    # Analizar series y películas
    series_stats = analyze_series()
    peliculas_stats = analyze_peliculas()
    
    # Mostrar resumen en consola
    print_console_summary(series_stats, peliculas_stats)
    
    # Generar informe HTML
    generate_html_report(series_stats, peliculas_stats)
    
    print("\n✅ Proceso completado exitosamente\n")

if __name__ == "__main__":
    main()
