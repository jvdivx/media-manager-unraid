import os
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime
import sys
import urllib.request

# === CONFIGURACIÓN ===
# Ajusta estas rutas si es necesario para tu servidor Unraid
PLEX_PREFS = "/mnt/user/appdata/plex/Library/Application Support/Plex Media Server/Preferences.xml"
DB_PATH = "/mnt/user/appdata/plex/Library/Application Support/Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db"

# Ruta de salida para la Web App
LOGS_DIR = "/mnt/user/appdata/media-manager/datos"
OUTPUT_FILE = os.path.join(LOGS_DIR, "report_09_usuarios_plex.html")

# Colores Consola (para debug local)
RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
GRAY = "\033[90m"

# --- ESTILOS CSS (Media Control Dark Theme) ---
CSS_STYLE = """
<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
<style>
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #1e1e1e; color: #e0e0e0; margin: 20px; }
    h1 { text-align: center; color: #4da6ff; margin-bottom: 10px; }
    h2 { border-bottom: 2px solid #4da6ff; padding-bottom: 5px; color: #ffffff; margin-top: 40px; }
    .container { max-width: 95%; margin: 0 auto; background: #252526; padding: 20px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
    
    /* Estilos de Tabla */
    table.dataTable { width: 100% !important; border-collapse: collapse; font-size: 0.95em; color: #e0e0e0; }
    table.dataTable thead th { background-color: #333337; color: #4da6ff; border-bottom: 1px solid #4da6ff; padding: 12px; text-align: left; }
    table.dataTable tbody td { background-color: #252526; border-bottom: 1px solid #3e3e42; padding: 10px; vertical-align: middle; }
    table.dataTable tbody tr:hover td { background-color: #2d2d30 !important; }
    
    /* Badges de Estado */
    .badge { padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; color: white; text-transform: uppercase; letter-spacing: 0.5px; }
    .status-active { background-color: #10b981; box-shadow: 0 0 5px rgba(16, 185, 129, 0.3); }
    .status-baja { background-color: #ef4444; opacity: 0.8; }
    .status-admin { background-color: #f59e0b; color: #000; }
    .status-unknown { background-color: #6b7280; }

    .email-cell { color: #9ca3af; font-family: 'Consolas', monospace; font-size: 0.9em; }
    .count-cell { font-weight: bold; color: #e0e0e0; text-align: center; }
    .date-cell { color: #60a5fa; }
    
    .summary-box { background: #333337; padding: 15px; border-radius: 5px; margin-bottom: 20px; border-left: 5px solid #4da6ff; display: flex; justify-content: space-between; align-items: center; }
    .stats-mini { display: flex; gap: 20px; }
    .stat-item span { font-weight: bold; color: #fff; }

    /* Overrides para DataTables en Dark Mode */
    .dataTables_wrapper .dataTables_length, 
    .dataTables_wrapper .dataTables_filter, 
    .dataTables_wrapper .dataTables_info, 
    .dataTables_wrapper .dataTables_paginate { color: #e0e0e0 !important; margin-bottom: 10px; }
    
    .dataTables_wrapper .dataTables_filter input,
    .dataTables_wrapper .dataTables_length select {
        background-color: #333337; color: #e0e0e0; border: 1px solid #4da6ff; padding: 5px; border-radius: 4px;
    }
    
    .dataTables_wrapper .dataTables_paginate .paginate_button { color: #e0e0e0 !important; }
    .dataTables_wrapper .dataTables_paginate .paginate_button.current {
        background: #4da6ff !important; color: #fff !important; border: none;
    }
    .dataTables_wrapper .dataTables_paginate .paginate_button:hover {
        background: #3e3e42 !important; color: #fff !important; border: 1px solid #4da6ff;
    }
</style>
"""

# --- JAVASCRIPT (DataTables Init) ---
JS_SCRIPT = """
<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
<script>
$(document).ready(function() {
    $('#userTable').DataTable({
        "pageLength": 25,
        "lengthMenu": [ [10, 25, 50, 100, -1], [10, 25, 50, 100, "Todos"] ],
        "order": [[ 4, "desc" ]], // Ordenar por 'Última Vez' descendente
        "language": {
            "lengthMenu": "Mostrar _MENU_ usuarios",
            "zeroRecords": "No se encontraron usuarios",
            "info": "Mostrando _START_ a _END_ de _TOTAL_ usuarios",
            "infoEmpty": "Sin datos",
            "infoFiltered": "(filtrado de _MAX_ totales)",
            "search": "🔍 Buscar:",
            "paginate": { "first": "<<", "last": ">>", "next": ">", "previous": "<" }
        }
    });
});
</script>
"""

def get_token():
    try:
        if not os.path.exists(PLEX_PREFS):
            return None
        with open(PLEX_PREFS, 'r') as f:
            c = f.read()
            if 'PlexOnlineToken="' in c: 
                return c.split('PlexOnlineToken="')[1].split('"')[0]
    except: pass
    return None

def get_api(token):
    users = {}
    url = "https://plex.tv/api/users"
    
    try:
        # Usamos urllib en lugar de curl/subprocess para evitar dependencias
        req = urllib.request.Request(url)
        req.add_header("X-Plex-Token", token)
        
        with urllib.request.urlopen(req, timeout=15) as response:
            xml_content = response.read()
            
        root = ET.fromstring(xml_content)
        for u in root.findall('User'):
            try: 
                users[int(u.get('id'))] = {'name': u.get('username'), 'email': u.get('email')}
            except: pass
            
    except Exception as e: 
        print(f"Nota: No se pudo contactar API Plex o Token inválido ({e})")
        
    # Admin siempre existe
    if 1 not in users: 
        users[1] = {'name': 'ADMIN (Server Owner)', 'email': 'Dueño'}
    return users

def get_local():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: No se encuentra la base de datos en {DB_PATH}")
        return {}, {}

    tmp = "/tmp/stats_plex.db"
    # Copiamos la DB a tmp para no bloquearla si Plex la está usando
    os.system(f'cp "{DB_PATH}" "{tmp}" && chmod 777 "{tmp}"')
    
    stats, offline = {}, {}
    try:
        conn = sqlite3.connect(tmp)
        cur = conn.cursor()
        
        # 1. Obtener estadísticas de uso
        cur.execute("SELECT account_id, count(*), max(last_viewed_at) FROM metadata_item_settings WHERE view_count > 0 GROUP BY account_id;")
        for r in cur.fetchall():
            ts = r[2] if r[2] else 0
            d_str = datetime.fromtimestamp(ts).strftime('%d/%m/%Y %H:%M') if ts > 0 else "Nunca"
            stats[r[0]] = {'count': r[1], 'last_ts': ts, 'last_str': d_str}

        # 2. Obtener nombres de cuentas locales
        try:
            cur.execute("SELECT id, name FROM accounts;")
            for r in cur.fetchall(): 
                offline[r[0]] = r[1]
        except: pass
        
        conn.close()
    except Exception as e:
        print(f"Error leyendo DB SQLite: {e}")
    finally:
        if os.path.exists(tmp): os.remove(tmp)
    
    return stats, offline

def generate_html_report(data):
    if not os.path.exists(LOGS_DIR):
        try: os.makedirs(LOGS_DIR)
        except: pass

    # Calcular totales
    total_users = len(data)
    active_users = sum(1 for r in data if r['raw_status'] == 'Activo')
    removed_users = sum(1 for r in data if r['raw_status'] == 'Baja')

    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Reporte Usuarios Plex</title>
        {CSS_STYLE}
    </head>
    <body>
        <div class="container">
            <h1>👥 Reporte de Usuarios Plex</h1>
            
            <div class="summary-box">
                <div>
                    Generado el: <i>{datetime.now().strftime('%d/%m/%Y %H:%M')}</i>
                </div>
                <div class="stats-mini">
                    <div class="stat-item">Total: <span>{total_users}</span></div>
                    <div class="stat-item" style="color:#10b981">Activos: <span>{active_users}</span></div>
                    <div class="stat-item" style="color:#ef4444">Bajas: <span>{removed_users}</span></div>
                </div>
            </div>

            <table id="userTable" class="display">
                <thead>
                    <tr>
                        <th>Estado</th>
                        <th>Usuario</th>
                        <th>Email / Contacto</th>
                        <th style="text-align:center;">Items Vistos</th>
                        <th>Última Actividad</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for row in data:
        status_class = "status-unknown"
        if row['raw_status'] == "Admin": status_class = "status-admin"
        elif row['raw_status'] == "Activo": status_class = "status-active"
        elif row['raw_status'] == "Baja": status_class = "status-baja"
        
        html_content += f"""
                    <tr>
                        <td><span class="badge {status_class}">{row['raw_status']}</span></td>
                        <td><strong>{row['raw_name']}</strong></td>
                        <td class="email-cell">{row['email']}</td>
                        <td class="count-cell" data-order="{row['count']}">{row['count']}</td>
                        <td class="date-cell" data-order="{row['ts']}">{row['last_str']}</td>
                    </tr>
        """
    
    html_content += f"""
                </tbody>
            </table>
        </div>
        {JS_SCRIPT}
    </body>
    </html>
    """
    
    with open(OUTPUT_FILE, "w", encoding='utf-8') as f: 
        f.write(html_content)
    
    print(f"    [OK] Reporte generado exitosamente.")
    print(f"    Archivo: {OUTPUT_FILE}")

def main():
    print(f"{'='*60}")
    print(f" GENERADOR DE REPORTE DE USUARIOS PLEX")
    print(f"{'='*60}")

    print("  > Obteniendo Token de Plex...")
    token = get_token()
    
    api_users = {}
    if token:
        print("  > Consultando API de Plex.tv...")
        api_users = get_api(token)
    else:
        print("  [!] No se encontró Token en Preferences.xml. Solo se usarán datos locales.")

    print("  > Leyendo base de datos local (SQLite)...")
    stats, offline_names = get_local()
    
    report_data = []
    all_ids = set(api_users.keys()) | set(stats.keys())
    
    print(f"  > Procesando {len(all_ids)} cuentas encontradas...")

    for uid in all_ids:
        s = stats.get(uid, {'count': 0, 'last_ts': 0, 'last_str': 'Nunca'})
        
        if s['count'] == 0 and uid not in api_users and uid != 1:
            continue

        status = "Desconocido"
        raw_name = f"Unknown (ID {uid})"
        email = "---"

        if uid == 1:
            status = "Admin"
            raw_name = api_users.get(1, {}).get('name', 'ADMIN')
            email = "Server Owner"
        elif uid in api_users:
            status = "Activo"
            raw_name = api_users[uid]['name']
            email = api_users[uid]['email']
        elif uid in offline_names:
            status = "Baja"
            raw_name = offline_names[uid]
            email = "---"
        
        if not raw_name: raw_name = f"Usuario {uid}"

        report_data.append({
            'raw_status': status,
            'raw_name': raw_name,
            'email': email,
            'count': s['count'],
            'last_str': s['last_str'],
            'ts': s['last_ts']
        })

    report_data.sort(key=lambda x: x['ts'], reverse=True)
    generate_html_report(report_data)
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
