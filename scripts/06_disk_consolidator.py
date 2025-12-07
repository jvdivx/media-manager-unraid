#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import re
import time
from pathlib import Path

# ==========================================
# CONFIGURACIÓN
# ==========================================
# Ruta relativa dentro de cada disco que queremos consolidar
RELATIVE_PATH = "Uploads/BajaCalidad"

# Ruta base de los discos en Unraid
MNT_ROOT = Path("/mnt")

# Permisos Unraid
UID = 99   # nobody
GID = 100  # users

# ==========================================
# LOGS
# ==========================================
def log(msg, tipo="INFO"):
    colors = {
        'INFO': '\033[94m', # Azul
        'OK': '\033[92m',   # Verde
        'WARN': '\033[93m', # Amarillo
        'ERR': '\033[91m',  # Rojo
        'DEST': '\033[95m', # Magenta
        'END': '\033[0m'
    }
    c = colors.get(tipo, colors['INFO'])
    print(f"[{time.strftime('%H:%M:%S')}] {c}{msg}{colors['END']}", flush=True)

# ==========================================
# DETECTAR DISCOS
# ==========================================
def obtener_discos():
    """Devuelve lista de discos ordenados y el disco destino (el último)"""
    discos = []
    
    if not MNT_ROOT.exists(): return [], None

    for d in MNT_ROOT.iterdir():
        # Buscamos carpetas que se llamen disk1, disk2, disk10...
        if d.is_dir() and re.match(r"^disk\d+$", d.name):
            num = int(d.name.replace("disk", ""))
            discos.append((num, d))
    
    # Ordenar por número
    discos.sort(key=lambda x: x[0])
    
    if not discos:
        return [], None
        
    # El último disco es el destino
    target_disk = discos[-1][1]
    
    # La lista de discos origen son todos MENOS el último
    source_disks = [d[1] for d in discos[:-1]]
    
    return source_disks, target_disk

# ==========================================
# MOVIMIENTO Y FUSIÓN
# ==========================================
def mover_contenido(origen_root, destino_root):
    """
    Mueve recursivamente todo el contenido de origen_root a destino_root
    """
    if not origen_root.exists(): return

    # Recorremos de abajo a arriba para poder borrar carpetas al vaciarlas
    for root, dirs, files in os.walk(origen_root, topdown=False):
        root_path = Path(root)
        
        # Calcular ruta relativa respecto a la raíz del path buscado
        # Ej: /mnt/disk1/Uploads/BajaCalidad/SerieX/S01 -> SerieX/S01
        try:
            rel_path = root_path.relative_to(origen_root)
        except ValueError:
            continue

        dest_dir = destino_root / rel_path
        
        # 1. MOVER ARCHIVOS
        for file in files:
            src_file = root_path / file
            dest_file = dest_dir / file
            
            # Crear carpeta destino si no existe
            if not dest_dir.exists():
                dest_dir.mkdir(parents=True, exist_ok=True)
                # Permisos carpeta
                os.chown(dest_dir, UID, GID)
                os.chmod(dest_dir, 0o2775)

            if dest_file.exists():
                log(f"⚠️ Conflicto: {file} ya existe en destino. Saltando.", "WARN")
            else:
                try:
                    # Mover archivo
                    shutil.move(str(src_file), str(dest_file))
                    
                    # Permisos archivo
                    os.chown(dest_file, UID, GID)
                    os.chmod(dest_file, 0o664)
                    
                    log(f"📦 Movido: {src_file} -> {dest_disk_name}", "INFO")
                except Exception as e:
                    log(f"Error moviendo {file}: {e}", "ERR")

        # 2. BORRAR CARPETA SI QUEDÓ VACÍA
        try:
            root_path.rmdir()
            # log(f"🗑️  Limpiado: {root_path}", "OK") # Verbose off
        except OSError:
            pass # No estaba vacía

# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    print("🚀 INICIANDO CONSOLIDADOR DE ARRAY UNRAID")
    print("Objetivo: Mover todo al último disco físico disponible.\n")
    
    origenes, destino_disk = obtener_discos()
    
    if not destino_disk:
        log("❌ No se detectaron discos en /mnt/disk*", "ERR")
        exit()

    dest_disk_name = destino_disk.name
    destino_final = destino_disk / RELATIVE_PATH
    
    log(f"🎯 DISCO DESTINO DETECTADO: {dest_disk_name}", "DEST")
    log(f"📂 Ruta final: {destino_final}\n", "DEST")

    # Crear la estructura base en el destino si no existe
    if not destino_final.exists():
        destino_final.mkdir(parents=True, exist_ok=True)
        os.chown(destino_final, UID, GID)
        os.chmod(destino_final, 0o2775)

    # Procesar cada disco origen
    for disk in origenes:
        origen_path = disk / RELATIVE_PATH
        
        if origen_path.exists():
            log(f"🔎 Analizando: {disk.name}...", "INFO")
            mover_contenido(origen_path, destino_final)
            
            # Intentar borrar la raíz /Uploads/BajaCalidad del disco origen si quedó vacía
            try:
                origen_path.rmdir()
                log(f"✨ {disk.name} limpiado completamente.", "OK")
            except OSError:
                log(f"⚠️ {disk.name} no se pudo limpiar del todo (archivos duplicados o bloqueados).", "WARN")
        else:
            # log(f"Omitiendo {disk.name} (vacío)", "INFO")
            pass

    print("\n🏁 Proceso de consolidación finalizado.")
