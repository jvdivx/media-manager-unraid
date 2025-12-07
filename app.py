#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import subprocess
import threading
import os
import sys
import re
import time
import uuid
import signal

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_secreto_seguro_media_server'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# ==========================================
# CONFIGURACIÓN DE RUTAS
# ==========================================
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "scripts")
LOGS_DIR = "/app/datos"

# Diccionario global para guardar procesos vivos
procesos_activos = {}

# ==========================================
# CONFIGURACIÓN DE SCRIPTS
# ==========================================
SCRIPTS_CONFIG = {
    "01_organizer": {
        "nombre": "01. Organizador & Defrag",
        "archivo": "01_organizer_movies.py",
        "desc": "Analiza, organiza y limpia basura. Opcional: Defrag.",
        "args_form": [
            {"name": "dry_run", "label": "Modo Simulación (Dry Run)", "type": "select", "options": [{"value": "yes", "label": "Sí"}, {"value": "no", "label": "No"}]},
            {"name": "force_clean", "label": "Limpieza Profunda", "type": "select", "options": [{"value": "no", "label": "No"}, {"value": "yes", "label": "Sí"}]}
        ]
    },
    "02_permissions": {
        "nombre": "02. Reparar Permisos",
        "archivo": "02_fix_permissions.py",
        "desc": "Aplica chown nobody:users y chmod 2775/664 recursivamente.",
        "args_form": []
    },
    "03_catalog": {
        "nombre": "03. Catálogo Global",
        "archivo": "03_catalog_maker.py",
        "desc": "Genera catálogo CSV y HTML de Series y Películas.",
        "args_form": []
    },
    "analyze": {
        "nombre": "04. Análisis Biblioteca",
        "archivo": "04_analyze_library.py",
        "desc": "Informe detallado por códec, resolución y tamaño.",
        "args_form": [
            {"name": "lib", "label": "Librería", "type": "select", "options": [
                {"value": "1", "label": "Series"},
                {"value": "2", "label": "Películas"}
            ]},
            {"name": "res", "label": "Filtro Resolución", "type": "select", "options": [
                {"value": "", "label": "Todas (Sin filtro)"},
                {"value": "2160p", "label": "4K / 2160p"},
                {"value": "1080p", "label": "Full HD / 1080p"},
                {"value": "720p", "label": "HD / 720p"},
                {"value": "576p", "label": "SD / 576p"},
                {"value": "480p", "label": "SD / 480p"}
            ]},
            {"name": "codec", "label": "Filtro Codec", "type": "select", "options": [
                {"value": "", "label": "Todos (Sin filtro)"},
                {"value": "hevc", "label": "HEVC / x265 / H.265"},
                {"value": "h264", "label": "AVC / x264 / H.264"},
                {"value": "vp9", "label": "VP9"},
                {"value": "av1", "label": "AV1"},
                {"value": "mpeg2", "label": "MPEG-2"},
                {"value": "mpeg4", "label": "MPEG-4 / DivX / XviD"},
                {"value": "vc1", "label": "VC-1"}
            ]},
            {"name": "sort", "label": "Ordenar por", "type": "select", "options": [
                {"value": "1", "label": "Tamaño (Desc)"},
                {"value": "2", "label": "Tamaño (Asc)"},
                {"value": "3", "label": "Nombre"},
                {"value": "4", "label": "Resolución"}
            ]}
        ]
    },
    "scanner": {
        "nombre": "05. Scanner Calidad",
        "archivo": "05_scanner_quality.py",
        "desc": "Detecta series con baja calidad para mover a Uploads.",
        "args_form": [
            {"name": "porcentaje", "label": "Umbral de capítulos malos (%)", "type": "number", "default": "80"}
        ]
    },
    "consolidator": {
        "nombre": "06. Consolidador Discos",
        "archivo": "06_disk_consolidator.py",
        "desc": "Mueve contenido disperso de 'Uploads/BajaCalidad' al último disco.",
        "args_form": []
    },
    "caps_analysis": {
        "nombre": "07. Análisis Capítulos",
        "archivo": "07_analyze_series_caps.py",
        "desc": "Inventario de resoluciones por capítulo y detección de mezclas.",
        "args_form": []
    },
    "baja_calidad": {
        "nombre": "08. Reporte Baja Calidad",
        "archivo": "08_analisis_carpeta_bajacalidad.py",
        "desc": "Genera reporte HTML interactivo de Series HD y Dibujos en BajaCalidad.",
        "args_form": []
    },
    "plex_users": {
        "nombre": "09. Reporte Usuarios Plex",
        "archivo": "09_reporte_usuarios_plex.py",
        "desc": "Auditoría de usuarios: Activos vs Bajas y última conexión.",
        "args_form": []
    },
    "movimientos_sd": {
        "nombre": "10. Generar Movimientos SD (Pelis)",
        "archivo": "10_generar_movimientos_peliculas_sd.py",
        "desc": "Detecta Películas < 720p, genera reporte HTML y script de movimiento.",
        "args_form": []
    }
}

# ==========================================
# RUTAS WEB Y API
# ==========================================
@app.route('/')
def index():
    return render_template('index.html', scripts=SCRIPTS_CONFIG)

@app.route('/api/files', methods=['GET'])
def list_files():
    files = []
    if os.path.exists(LOGS_DIR):
        try:
            for f in os.listdir(LOGS_DIR):
                if f.startswith("report_") or f.endswith(('.log', '.sh', '.csv', '.html')):
                    path = os.path.join(LOGS_DIR, f)
                    stats = os.stat(path)
                    files.append({
                        'name': f,
                        'size': stats.st_size,
                        'mtime': stats.st_mtime,
                        'date': time.strftime('%Y-%m-%d %H:%M', time.localtime(stats.st_mtime))
                    })
        except Exception as e:
            print(f"Error leyendo logs: {e}")
    files.sort(key=lambda x: x['mtime'], reverse=True)
    return jsonify(files)

@app.route('/download/<path:filename>')
def download_file(filename):
    return send_from_directory(LOGS_DIR, filename, as_attachment=True)

@app.route('/view/<path:filename>')
def view_file(filename):
    response = send_from_directory(LOGS_DIR, filename, as_attachment=False)
    if filename.lower().endswith('.html'):
        response.headers["Content-Type"] = "text/html; charset=utf-8"
    else:
        response.headers["Content-Type"] = "text/plain; charset=utf-8"
    return response

# ==========================================
# UTILIDADES
# ==========================================
def ansi_to_html(text):
    ansi_map = {
        '\033[95m': '<span style="color: #d670d6; font-weight: bold;">', 
        '\033[94m': '<span style="color: #5e9bff;">', 
        '\033[96m': '<span style="color: #00ffff;">', 
        '\033[92m': '<span style="color: #10b981;">', 
        '\033[93m': '<span style="color: #f59e0b;">', 
        '\033[91m': '<span style="color: #ef4444;">', 
        '\033[0m': '</span>',                          
        '\033[1m': '<span style="font-weight: bold;">' 
    }
    result = text
    for ansi_code, html in ansi_map.items():
        result = result.replace(ansi_code, html)
    
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    result = ansi_escape.sub('', result)
    return result

# ==========================================
# EJECUCIÓN
# ==========================================
def ejecutar_script_thread(script_key, params, process_id):
    config = SCRIPTS_CONFIG.get(script_key)
    if not config: return
    
    script_path = os.path.join(SCRIPTS_DIR, config['archivo'])
    
    if not os.path.exists(script_path):
        socketio.emit('script_output', {'process_id': process_id, 'data': f"<span style='color:red'>Error: No encuentro {config['archivo']}</span>"})
        socketio.emit('script_complete', {'process_id': process_id, 'status': 'error', 'code': 404})
        return

    cmd = [sys.executable, "-u", script_path]
    
    # Argumentos unificados y corrección de formato (key.replace('_', '-'))
    if params:
        for key, val in params.items():
            # Convertimos 'force_clean' -> 'force-clean' para CLI
            clean_key = key.replace('_', '-')
            
            # Caso especial script 1 (boolean flags)
            if script_key == '01_organizer':
                if val == 'yes': 
                    cmd.append(f"--{clean_key}")
            # Caso genérico (clave valor)
            else:
                if val and str(val).strip() != "":
                    cmd.append(f"--{clean_key}")
                    cmd.append(str(val))

    socketio.emit('script_start', {
        'process_id': process_id,
        'script_name': config['nombre'],
        'comando': ' '.join(cmd)
    })
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            preexec_fn=os.setsid 
        )
        
        procesos_activos[process_id] = process
        
        for line in iter(process.stdout.readline, ''):
            if line:
                html_line = ansi_to_html(line.rstrip())
                socketio.emit('script_output', {'process_id': process_id, 'data': html_line})
        
        process.wait()
        
        if process_id in procesos_activos:
            del procesos_activos[process_id]

        status = 'success' if process.returncode == 0 else 'error'
        if process.returncode == -15 or process.returncode == -9:
            status = 'stopped'

        socketio.emit('script_complete', {
            'process_id': process_id,
            'status': status, 
            'code': process.returncode
        })
            
    except Exception as e:
        if process_id in procesos_activos: del procesos_activos[process_id]
        socketio.emit('script_output', {'process_id': process_id, 'data': f"<span style='color:red'>Error: {str(e)}</span>"})

@socketio.on('run_script')
def handle_run_script(data):
    script_key = data.get('script')
    params = data.get('params', {})
    
    process_id = str(uuid.uuid4())[:8]
    
    thread = threading.Thread(target=ejecutar_script_thread, args=(script_key, params, process_id))
    thread.daemon = True
    thread.start()

@socketio.on('stop_script')
def handle_stop_script(data):
    pid_key = data.get('process_id')
    
    if pid_key in procesos_activos:
        proc = procesos_activos[pid_key]
        try:
            print(f"🛑 Matando proceso UUID: {pid_key} PID: {proc.pid}")
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            
            if pid_key in procesos_activos:
                del procesos_activos[pid_key]
            
            socketio.emit('script_stopped', {'process_id': pid_key})
            
        except Exception as e:
            print(f"Error matando proceso: {e}")
    else:
        print(f"No se encontró proceso activo con ID {pid_key}")

if __name__ == '__main__':
    print("🚀 Servidor V4.7 (Full Suite + Movimientos SD) iniciado en puerto 5000", flush=True)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
