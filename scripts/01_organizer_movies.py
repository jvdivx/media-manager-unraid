#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import signal
import argparse
import logging
from logging.handlers import RotatingFileHandler
import sys
import re
import html
import fcntl
from datetime import datetime
from pathlib import Path
from typing import List, Set, Dict
from collections import defaultdict

# ==========================================
# CONFIGURACIÓN VISUAL
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

# ==========================================
# CONFIGURACIONES INICIALES
# ==========================================
UPLOAD_SUFFIX = ".upload"
BASE_PATH = Path("/mnt/user/appdata/media-manager/datos")
BASE_PATH.mkdir(parents=True, exist_ok=True)

LOG_FILE = BASE_PATH / "01_organizer_defrag.log"
INFORME_FILE = BASE_PATH / "report_01_organizer.html"
LOG_PATH_FALTANTES = BASE_PATH / "report_01_missing_meta.html"

CATEGORIAS = {
    "Peliculas HD": ("peliculas/Peliculas HD", "Peliculas"),
    "Documentales Cine": ("peliculas/Documentales", "Peliculas"),
    "Conciertos": ("peliculas/Conciertos", "Peliculas"),
    "Series HD": ("series/Series HD", "Series"),
    "Dibujos": ("series/Dibujos", "Series"),
    "Documentales Series": ("series/Documentales", "Series")
}

EXT_VIDEO = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m2ts', '.mpg', '.m4v', '.vob', '.ts', '.ogm', '.flv'}
JUNK_FILES = {'.ds_store', 'thumbs.db', '._.ds_store', 'desktop.ini', '.smbdelete'}
BUFFER_SIZE = 10 * 1024**3  # 10 GB

# ==========================================
# LOGGING
# ==========================================
class NoColorFormatter(logging.Formatter):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    def format(self, record):
        msg = super().format(record)
        return self.ansi_escape.sub('', msg)

logger = logging.getLogger("UnraidDefrag")
logger.setLevel(logging.INFO)

file_formatter = NoColorFormatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
fh = RotatingFileHandler(LOG_FILE, maxBytes=50*1024*1024, backupCount=3, encoding='utf-8')
fh.setFormatter(file_formatter)
logger.addHandler(fh)

class ConsoleHandler(logging.StreamHandler):
    def emit(self, record):
        if record.levelno >= logging.INFO:
            msg = record.getMessage()
            print(msg, flush=True)

ch = ConsoleHandler(sys.stdout)
logger.addHandler(ch)
logger.propagate = False

STOP_REQUESTED = False
def signal_handler(signum, frame):
    global STOP_REQUESTED
    logger.warning(f"{Color.FAIL}🛑 Señal de terminación recibida. Finalizando ordenadamente...{Color.ENDC}")
    STOP_REQUESTED = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ==========================================
# FUNCIONES DE UTILIDAD
# ==========================================
def log_bonito(mensaje, tipo="info"):
    if tipo == "titulo":
        logger.info(f"\n{Color.HEADER}{'='*60}\n {mensaje} \n{'='*60}{Color.ENDC}")
    elif tipo == "subtitulo":
        logger.info(f"{Color.CYAN}📂 {mensaje}{Color.ENDC}")
    elif tipo == "exito":
        logger.info(f"{Color.GREEN}✅ {mensaje}{Color.ENDC}")
    elif tipo == "aviso":
        logger.info(f"{Color.WARNING}⚠️ {mensaje}{Color.ENDC}")
    elif tipo == "error":
        logger.error(f"{Color.FAIL}❌ {mensaje}{Color.ENDC}")
    elif tipo == "movimiento":
        logger.info(f"   {Color.BLUE}📦 {mensaje}{Color.ENDC}")
    else:
        logger.info(mensaje)

def get_disks() -> List[Path]:
    disks = [d for d in Path("/mnt").glob("disk*") if d.is_dir() and d.name[4:].isdigit()]
    return sorted(disks, key=lambda p: int(p.name[4:]))

DISCOS_DISPONIBLES = get_disks()
DISCO_MAP = {d.name: d for d in DISCOS_DISPONIBLES}

def obtener_espacio_libre(path: Path) -> int:
    try:
        st = os.statvfs(path)
        return st.f_frsize * st.f_bavail
    except OSError: return 0

def set_unraid_permissions(path: Path):
    try:
        shutil.chown(path, user=99, group=100)
        if path.is_dir(): path.chmod(0o777)
        else: path.chmod(0o666)
    except: pass

def ensure_path_permissions(path: Path):
    if not path.exists():
        try: path.mkdir(parents=True, exist_ok=True)
        except: return
    current = path
    try:
        while "disk" in current.parts:
            stat = current.stat()
            if stat.st_uid == 99 and stat.st_gid == 100: break
            shutil.chown(current, user=99, group=100)
            if current.is_dir(): current.chmod(0o777)
            else: current.chmod(0o666)
            parent = current.parent
            if parent == current or not parent.exists(): break
            current = parent
    except: pass

# ==========================================
# LIMPIEZA
# ==========================================
def limpiar_vacios_recursivo(base_paths: List[Path]):
    max_pasadas = 3
    for i in range(max_pasadas):
        cambios = False
        for base in base_paths:
            if not base.exists(): continue
            for root, dirs, files in os.walk(base, topdown=False):
                current = Path(root)
                for f in files:
                    if f.lower() in JUNK_FILES:
                        try: (current / f).unlink()
                        except: pass
                try:
                    if not any(current.iterdir()):
                        if current != base:
                            current.rmdir()
                            logger.debug(f"🧹 Eliminada carpeta vacía: {current}")
                            cambios = True
                except OSError: pass
        if not cambios: break

def limpiar_partial_huerfanos(discos: List[Path]):
    count = 0
    for disco in discos:
        for root, _, files in os.walk(disco):
            for f in files:
                if f.endswith(".partial"):
                    try: 
                        (Path(root) / f).unlink()
                        count += 1
                    except: pass
    if count > 0:
        log_bonito(f"Eliminados {count} archivos .partial huérfanos", "exito")

# ==========================================
# MOVIMIENTO (CORE)
# ==========================================
def safe_copy_and_delete(src: Path, dst: Path, dry_run: bool = False) -> bool:
    if STOP_REQUESTED: return False
    archivo_nombre = src.name
    origen_str = f"{src.parts[2]}"
    destino_str = f"{dst.parts[2]}"
    
    if dst.exists():
        if src.stat().st_size == dst.stat().st_size:
            log_bonito(f"Destino idéntico existe ({destino_str}), borrando origen ({origen_str}): {archivo_nombre}", "aviso")
            if not dry_run: src.unlink()
            return True
        else:
            log_bonito(f"CONFLICTO DE TAMAÑO: {dst}", "error")
            return False

    msg_mov = f"[{origen_str} -> {destino_str}] {archivo_nombre}"
    if dry_run:
        log_bonito(f"[DRY-RUN] {msg_mov}", "movimiento")
        return True

    log_bonito(f"{msg_mov}", "movimiento")
    dst_temp = dst.with_suffix(dst.suffix + ".partial")
    try:
        ensure_path_permissions(dst.parent)
        shutil.copy2(src, dst_temp)
        if src.stat().st_size == dst_temp.stat().st_size:
            dst_temp.rename(dst)
            set_unraid_permissions(dst)
            src.unlink()
            return True
        else:
            if dst_temp.exists(): dst_temp.unlink()
            return False
    except Exception as e:
        log_bonito(f"Error moviendo {archivo_nombre}: {e}", "error")
        if dst_temp.exists():
            try: dst_temp.unlink()
            except: pass
        return False

def fusionar_item(item_name: str, fragments: List[Path], dest_disk: Path, rel_path: str, dry_run: bool):
    dest_base = dest_disk / rel_path / item_name
    disk_name_dest = dest_disk.name
    for frag_path in fragments:
        if len(frag_path.parts) > 2 and frag_path.parts[2] == disk_name_dest:
            continue
        for r, _, files in os.walk(frag_path):
            if ".RecycleBin" in r: continue
            if STOP_REQUESTED: break
            for f in files:
                if f.endswith(UPLOAD_SUFFIX): continue
                src = Path(r) / f
                if f.lower() in JUNK_FILES:
                    if not dry_run:
                        try: src.unlink()
                        except: pass
                    continue
                try:
                    rel_file = src.relative_to(frag_path)
                    dst = dest_base / rel_file
                    safe_copy_and_delete(src, dst, dry_run)
                except ValueError: continue
        
        if not dry_run and not STOP_REQUESTED:
            limpiar_vacios_recursivo([frag_path])
            try:
                if frag_path.exists() and not any(frag_path.iterdir()):
                    frag_path.rmdir()
                    log_bonito(f"Fragmento limpio y eliminado: {frag_path}", "exito")
            except OSError: pass

# ==========================================
# ANÁLISIS
# ==========================================
def init_conteo():
    return {"videos": 0, "jpg": 0, "nfo": 0, "srt": 0, "otros": 0}

class ItemStats:
    def __init__(self):
        self.size_bytes = 0
        self.file_count = 0
        self.dir_count = 0
        self.has_jpg = False
        self.has_nfo = False
        self.disks: Set[str] = set()
        self.path_ref: str = ""

def procesar_y_analizar(dry_run: bool):
    report_data = []
    missing_metadata = []
    resumen_categorias = {}

    for cat_name, (subpath, tipo_contenido) in CATEGORIAS.items():
        if STOP_REQUESTED: break
        log_bonito(f"Analizando: {cat_name} ({tipo_contenido})", "subtitulo")

        if cat_name not in resumen_categorias:
            resumen_categorias[cat_name] = {
                "tipo_contenido": tipo_contenido,
                "total_items": 0, "fragmentadas": 0, "desfragmentadas": 0, "conteo": init_conteo()
            }

        items_map: Dict[str, List[Path]] = {}
        for disco in DISCOS_DISPONIBLES:
            search_path = disco / subpath
            if not search_path.exists(): continue
            for entry in search_path.iterdir():
                if entry.is_dir():
                    items_map.setdefault(entry.name, []).append(entry)

        for name, frags in items_map.items():
            if STOP_REQUESTED: break
            stats = ItemStats()
            frag_sizes: Dict[Path, int] = {}
            conteo_cat = resumen_categorias[cat_name]["conteo"]

            for frag in frags:
                current_frag_size = 0
                if len(frag.parts) > 2: stats.disks.add(frag.parts[2])
                stats.path_ref = str(frag)
                for root, dirs, files in os.walk(frag):
                    stats.dir_count += len(dirs)
                    for f in files:
                        if f.endswith(UPLOAD_SUFFIX) or f.lower() in JUNK_FILES: continue
                        file_path = Path(root) / f
                        ext = file_path.suffix.lower()
                        
                        if ext == ".jpg": stats.has_jpg = True
                        if ext == ".nfo": stats.has_nfo = True
                        if ext in EXT_VIDEO: conteo_cat["videos"] += 1
                        elif ext == ".jpg": conteo_cat["jpg"] += 1
                        elif ext == ".nfo": conteo_cat["nfo"] += 1
                        elif ext == ".srt": conteo_cat["srt"] += 1
                        else: conteo_cat["otros"] += 1
                        
                        try:
                            s = file_path.stat().st_size
                            stats.size_bytes += s
                            current_frag_size += s
                            stats.file_count += 1
                        except: pass
                frag_sizes[frag] = current_frag_size

            estado = "Desfragmentada"
            destino_final = "-"

            if len(stats.disks) > 1:
                sorted_frags_by_size = sorted(frags, key=lambda f: frag_sizes.get(f, 0), reverse=True)
                target_disk = None
                for candidate_frag in sorted_frags_by_size:
                    disk_name = candidate_frag.parts[2]
                    c_disk = DISCO_MAP.get(disk_name)
                    if not c_disk: continue
                    needed = stats.size_bytes - frag_sizes[candidate_frag]
                    if obtener_espacio_libre(c_disk) > (needed + BUFFER_SIZE):
                        target_disk = c_disk
                        break
                if not target_disk:
                    all_disks_sorted = sorted(DISCOS_DISPONIBLES, key=obtener_espacio_libre, reverse=True)
                    for d in all_disks_sorted:
                        if obtener_espacio_libre(d) > (stats.size_bytes + BUFFER_SIZE):
                            target_disk = d
                            break
                if target_disk:
                    destino_final = target_disk.name
                    log_bonito(f"🔧 Consolidando '{name}' en {destino_final}", "aviso")
                    fusionar_item(name, frags, target_disk, subpath, dry_run)
                    estado = "Consolidado"
                else:
                    log_bonito(f"Sin espacio para consolidar: {name}", "error")
                    estado = "Fallo (Espacio)"
            elif len(stats.disks) == 1:
                destino_final = list(stats.disks)[0]

            resumen_categorias[cat_name]["total_items"] += 1
            if estado in ("Fragmentada", "Fallo (Espacio)"):
                resumen_categorias[cat_name]["fragmentadas"] += 1
            else:
                resumen_categorias[cat_name]["desfragmentadas"] += 1

            if not stats.has_jpg or not stats.has_nfo:
                missing_metadata.append({
                    "titulo": name, "tipo": tipo_contenido, "path": stats.path_ref,
                    "no_jpg": not stats.has_jpg, "no_nfo": not stats.has_nfo
                })

            report_data.append({
                "tipo": tipo_contenido, "categoria": cat_name, "titulo": name,
                "discos": sorted(list(stats.disks)) if estado != "Consolidado" else [destino_final],
                "temps": stats.dir_count if tipo_contenido == "Series" else "-",
                "ficheros": stats.file_count, "jpg": stats.has_jpg, "nfo": stats.has_nfo,
                "tamano": stats.size_bytes / (1024**3), "estado": estado
            })

    return report_data, missing_metadata, resumen_categorias

# ==========================================
# GENERACIÓN DE INFORMES (HTML PRO + INTERACTIVO)
# ==========================================
def imprimir_tabla_resumen(resumen_categorias):
    C_B = Color.HEADER 
    C_R = Color.ENDC   
    print(f"\n{C_B}=== RESUMEN DE EJECUCIÓN ==={C_R}", flush=True)

def generar_informe(datos, missing_meta):
    if not datos: return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    datos_por_cat = defaultdict(list)
    for d in datos:
        datos_por_cat[d['categoria']].append(d)

    css = """
    <style>
        :root { --bg-color: #121212; --card-bg: #1e1e1e; --text-main: #e0e0e0; --text-muted: #a0a0a0;
            --accent: #7c4dff; --accent-hover: #651fff; --border: #333;
            --warn-color: #ff9800; --ok-color: #69f0ae; --frag-color: #ff5252; }
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
        .category-section { margin-bottom: 20px; background: var(--card-bg); border-radius: 16px; overflow: hidden; border: 1px solid var(--border); box-shadow: 0 4px 10px rgba(0,0,0,0.2); }
        .cat-header { background: #252525; padding: 15px 30px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; cursor: pointer; user-select: none; }
        .cat-header h2 { margin: 0; font-size: 1.4rem; color: #fff; }
        .badge-count { background: var(--accent); color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; margin-left: 15px; font-weight: bold; }
        .category-section.collapsed .cat-content { display: none; }
        
        .controls-bar { padding: 10px 20px; background: #202020; border-bottom: 1px solid var(--border); display: flex; gap: 15px; align-items: center; }
        .search-input { background: #121212; border: 1px solid #444; color: #fff; padding: 6px 12px; border-radius: 4px; outline: none; font-size: 0.9rem; width: 200px; }
        .search-input:focus { border-color: var(--accent); }
        .rows-select { background: #121212; border: 1px solid #444; color: #fff; padding: 6px; border-radius: 4px; outline: none; }

        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; padding: 15px 20px; background: #2a2a2a; color: var(--text-muted); border-bottom: 2px solid var(--border); cursor: pointer; user-select: none; }
        th:hover { color: #fff; background: #333; }
        th.sort-asc::after { content: ' ▲'; font-size: 0.8em; color: var(--accent); }
        th.sort-desc::after { content: ' ▼'; font-size: 0.8em; color: var(--accent); }
        
        td { padding: 12px 20px; border-bottom: 1px solid var(--border); }
        
        .badge { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; text-transform: uppercase; }
        .badge.yes { background: rgba(105, 240, 174, 0.1); color: var(--ok-color); border: 1px solid rgba(105, 240, 174, 0.3); }
        .badge.no { background: rgba(255, 82, 82, 0.1); color: var(--frag-color); border: 1px solid rgba(255, 82, 82, 0.3); }
        
        .status-frag { color: var(--frag-color); font-weight: bold; }
        .status-ok { color: var(--ok-color); }
        .status-warn { color: var(--warn-color); }

        .pagination { display: flex; justify-content: space-between; align-items: center; padding: 15px 20px; background: #252525; border-top: 1px solid var(--border); }
        .page-btn { background: var(--accent); color: white; border: none; padding: 6px 15px; border-radius: 4px; cursor: pointer; font-size: 0.9rem; transition: background 0.2s; }
        .page-btn:hover { background: var(--accent-hover); }
        .page-btn:disabled { background: #444; cursor: not-allowed; color: #888; }
        .page-info { color: var(--text-muted); font-size: 0.9rem; }
        .hidden { display: none !important; }
    </style>
    <script>
    document.addEventListener('DOMContentLoaded', () => {
        
        document.querySelectorAll('.category-section').forEach(section => {
            // COLAPSAR
            const header = section.querySelector('.cat-header');
            header.addEventListener('click', (e) => {
                if(e.target.closest('.controls-bar')) return; // Evitar colapso al clicar inputs
                section.classList.toggle('collapsed');
            });

            // REFERENCIAS
            const tableBody = section.querySelector('tbody');
            const allRows = Array.from(tableBody.querySelectorAll('tr')); // Copia de todas las filas
            const searchInput = section.querySelector('.search-input');
            const rowsSelect = section.querySelector('.rows-select');
            const headers = section.querySelectorAll('th');
            
            // ESTADO LOCAL
            let state = {
                page: 1,
                rowsPerPage: 10, // Default ahora es 10
                search: "",
                sortCol: 0,
                sortAsc: true,
                filteredRows: allRows
            };

            // UI PAGINACIÓN
            const paginationDiv = document.createElement('div');
            paginationDiv.className = 'pagination';
            paginationDiv.innerHTML = `
                <button class="page-btn prev-btn">Anterior</button>
                <span class="page-info">Página 1</span>
                <button class="page-btn next-btn">Siguiente</button>
            `;
            section.querySelector('.cat-content').appendChild(paginationDiv);
            
            const prevBtn = paginationDiv.querySelector('.prev-btn');
            const nextBtn = paginationDiv.querySelector('.next-btn');
            const pageInfo = paginationDiv.querySelector('.page-info');

            // FUNCIONES LOGICA
            function filterRows() {
                const term = state.search.toLowerCase();
                state.filteredRows = allRows.filter(row => {
                    return row.innerText.toLowerCase().includes(term);
                });
                state.page = 1; // Reset a página 1 al buscar
                sortRows();
            }

            function sortRows() {
                const colIdx = state.sortCol;
                const asc = state.sortAsc;
                
                state.filteredRows.sort((a, b) => {
                    const valA = a.children[colIdx].innerText.trim();
                    const valB = b.children[colIdx].innerText.trim();
                    
                    // Detectar números (GB, Files)
                    const numA = parseFloat(valA.replace(/[^\d.-]/g, ''));
                    const numB = parseFloat(valB.replace(/[^\d.-]/g, ''));
                    
                    if (!isNaN(numA) && !isNaN(numB) && valA.includes(valA.match(/[0-9]/))) {
                        return asc ? numA - numB : numB - numA;
                    }
                    return asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
                });
                renderTable();
            }

            function renderTable() {
                // 1. Limpiar tabla visual
                allRows.forEach(r => r.remove());
                
                // 2. Calcular paginación
                const totalPages = Math.ceil(state.filteredRows.length / state.rowsPerPage) || 1;
                if (state.page > totalPages) state.page = 1;
                
                const start = (state.page - 1) * state.rowsPerPage;
                const end = start + parseInt(state.rowsPerPage);
                const rowsToShow = state.filteredRows.slice(start, end);
                
                // 3. Inyectar filas
                rowsToShow.forEach(r => tableBody.appendChild(r));
                
                // 4. Actualizar controles
                pageInfo.textContent = `Página ${state.page} de ${totalPages} (${state.filteredRows.length} items)`;
                prevBtn.disabled = state.page === 1;
                nextBtn.disabled = state.page === totalPages;
                
                // 5. Headers visuales
                headers.forEach((th, idx) => {
                    th.classList.remove('sort-asc', 'sort-desc');
                    if (idx === state.sortCol) th.classList.add(state.sortAsc ? 'sort-asc' : 'sort-desc');
                });
            }

            // LISTENERS
            searchInput.addEventListener('input', (e) => { state.search = e.target.value; filterRows(); });
            rowsSelect.addEventListener('change', (e) => { state.rowsPerPage = parseInt(e.target.value); renderTable(); });
            
            prevBtn.addEventListener('click', () => { if(state.page > 1) { state.page--; renderTable(); }});
            nextBtn.addEventListener('click', () => { 
                const max = Math.ceil(state.filteredRows.length / state.rowsPerPage);
                if(state.page < max) { state.page++; renderTable(); }
            });

            headers.forEach((th, idx) => {
                th.addEventListener('click', () => {
                    if (state.sortCol === idx) state.sortAsc = !state.sortAsc;
                    else { state.sortCol = idx; state.sortAsc = true; }
                    sortRows();
                });
            });

            // INIT
            filterRows(); // Trigger inicial
        });
    });
    </script>
    """
    
    html_content = f"""
    <!DOCTYPE html><html><head><meta charset='utf-8'><title>Reporte Organizador</title>{css}</head>
    <body>
        <div class="container">
            <div class="header"><h1>📊 Reporte de Organización</h1><div class="meta">{ts}</div></div>
            <div class="stats-grid">
                <div class="stat-card info"><div class="stat-label">Items Totales</div><div class="stat-value">{len(datos)}</div></div>
                <div class="stat-card info"><div class="stat-label">Categorías</div><div class="stat-value">{len(datos_por_cat)}</div></div>
            </div>
    """
    
    for cat_name, items in datos_por_cat.items():
        items.sort(key=lambda x: x['titulo'])
        html_content += f"""
        <div class="category-section collapsed">
            <div class="cat-header">
                <div style="display:flex;align-items:center;"><h2>{cat_name}</h2><span class="badge-count">{len(items)}</span></div>
                <span>▼</span>
            </div>
            <div class="cat-content">
                <div class="controls-bar">
                    <input type="text" class="search-input" placeholder="🔍 Buscar...">
                    <select class="rows-select">
                        <option value="10" selected>10 filas</option>
                        <option value="25">25 filas</option>
                        <option value="50">50 filas</option>
                        <option value="100">100 filas</option>
                        <option value="9999">Todas</option>
                    </select>
                </div>
                <table>
                    <thead><tr><th>Título</th><th>Discos</th><th>Archivos</th><th>JPG</th><th>NFO</th><th>Tamaño</th><th>Estado</th></tr></thead>
                    <tbody>
        """
        for d in items:
            discos_str = ", ".join(d['discos'])
            html_content += f"""
            <tr>
                <td><strong>{html.escape(d['titulo'])}</strong></td>
                <td>{discos_str}</td>
                <td>{d['ficheros']}</td>
                <td><span class="badge {'yes' if d['jpg'] else 'no'}">{'SI' if d['jpg'] else 'NO'}</span></td>
                <td><span class="badge {'yes' if d['nfo'] else 'no'}">{'SI' if d['nfo'] else 'NO'}</span></td>
                <td>{d['tamano']:.2f} GB</td>
                <td class="{'status-frag' if 'Fallo' in d['estado'] else ('status-warn' if 'Consolidado' in d['estado'] else 'status-ok')}">{d['estado']}</td>
            </tr>
            """
        html_content += "</tbody></table></div></div>"
    
    html_content += "</div></body></html>"
    
    with open(INFORME_FILE, "w", encoding="utf-8") as f: f.write(html_content)
    
    if missing_meta:
        html_missing = f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Missing Meta</title>{css}</head><body><div class='container'><h1 style='color:#ff5252;'>⚠️ Metadatos Faltantes</h1><table><thead><tr><th>Tipo</th><th>Título</th><th>Ruta</th><th>Falta JPG</th><th>Falta NFO</th></tr></thead><tbody>"
        for item in missing_meta:
            html_missing += f"<tr><td>{item['tipo']}</td><td><strong>{html.escape(item['titulo'])}</strong></td><td>{html.escape(item['path'])}</td><td><span class='badge {'no' if item['no_jpg'] else 'yes'}'>{'FALTA' if item['no_jpg'] else 'OK'}</span></td><td><span class='badge {'no' if item['no_nfo'] else 'yes'}'>{'FALTA' if item['no_nfo'] else 'OK'}</span></td></tr>"
        html_missing += "</tbody></table></div></body></html>"
        with open(LOG_PATH_FALTANTES, "w", encoding="utf-8") as f: f.write(html_missing)
        print(f"{Color.WARNING}⚠️  Se detectaron metadatos faltantes. Ver: {LOG_PATH_FALTANTES}{Color.ENDC}")
    else:
        print(f"{Color.GREEN}🎉 Todo perfecto. Metadatos completos.{Color.ENDC}")

def limpiar_uploads_antiguos():
    if not DISCOS_DISPONIBLES: return
    log_bonito("Limpiando carpetas 'Uploads' antiguas...", "info")
    for disco in DISCOS_DISPONIBLES[:-1]:
        for rel in ["peliculas/Uploads", "series/Uploads"]:
            p = disco / rel
            limpiar_vacios_recursivo([p])
            try:
                if p.exists() and not any(p.iterdir()): p.rmdir()
            except: pass

def crear_uploads_ultimo():
    if not DISCOS_DISPONIBLES: return
    ultimo = DISCOS_DISPONIBLES[-1]
    log_bonito(f"Verificando 'Uploads' en {ultimo.name}...", "info")
    rutas = [ultimo/"peliculas"/"Uploads"/sub for sub in ["Conciertos","Documentales","Peliculas HD"]] + \
            [ultimo/"series"/"Uploads"/sub for sub in ["Series HD","Dibujos","Documentales"]]
    for r in rutas:
        try:
            if not r.exists(): r.mkdir(parents=True, exist_ok=True)
            set_unraid_permissions(r)
        except: pass

if __name__ == "__main__":
    print("🚀 Iniciando...", flush=True)
    lock_path = '/tmp/unraid_defrag.lock'
    try:
        with open(lock_path, 'w') as lock_file:
            try:
                fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                print(f"{Color.FAIL}❌ Ya está en ejecución.{Color.ENDC}"); sys.exit(1)

            log_bonito("DESFRAGMENTADOR Y ORGANIZADOR (01)", "titulo")
            limpiar_partial_huerfanos(DISCOS_DISPONIBLES)

            parser = argparse.ArgumentParser()
            parser.add_argument("--dry-run", action="store_true", help="Simular")
            parser.add_argument("--force-clean", action="store_true", help="Limpieza profunda")
            args = parser.parse_args()

            if args.dry_run: log_bonito("MODO DRY-RUN", "aviso")
            
            datos, meta, resumen = procesar_y_analizar(args.dry_run)
            imprimir_tabla_resumen(resumen)
            generar_informe(datos, meta)

            if args.force_clean and not args.dry_run:
                base_paths = []
                for d in DISCOS_DISPONIBLES: base_paths += [d/"peliculas", d/"series"]
                limpiar_vacios_recursivo(base_paths)
            
            if not args.dry_run:
                limpiar_uploads_antiguos()
                crear_uploads_ultimo()

            print(f"\n{Color.GREEN}Finalizado.{Color.ENDC}")
            print(f"📄 {INFORME_FILE}")
    finally: pass
