from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import nsdecls
from docx.oxml import parse_xml

def create_manual():
    doc = Document()

    # --- Estilos Globales ---
    style = doc.styles['Normal']
    style.font.name = 'Calibri'
    style.font.size = Pt(11)

    # --- Helper: Título Principal ---
    def add_main_title(text):
        p = doc.add_heading(text, 0)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.runs[0]
        run.font.color.rgb = RGBColor(0, 51, 102) # Azul oscuro profesional

    # --- Helper: Metadatos ---
    def add_metadata(label, value):
        p = doc.add_paragraph()
        runner = p.add_run(f"{label}: ")
        runner.bold = True
        p.add_run(value)

    # --- Helper: Bloque de Código ---
    def add_code_block(code_text):
        p = doc.add_paragraph()
        p.style = 'No Spacing'
        runner = p.add_run(code_text)
        runner.font.name = 'Consolas'
        runner.font.size = Pt(9)
        runner.font.color.rgb = RGBColor(100, 100, 100) # Gris oscuro
        # Añadir un borde izquierdo para simular bloque (avanzado, opcional, aquí simple)
        p.paragraph_format.left_indent = Pt(20)
        p.paragraph_format.space_before = Pt(5)
        p.paragraph_format.space_after = Pt(10)

    # --- Helper: Tablas con estilo ---
    def add_styled_table(data):
        table = doc.add_table(rows=1, cols=len(data[0]))
        table.style = 'Light Shading Accent 1' # Estilo azulado de Word
        
        # Header
        hdr_cells = table.rows[0].cells
        for i, header_text in enumerate(data[0]):
            hdr_cells[i].text = header_text
            hdr_cells[i].paragraphs[0].runs[0].bold = True
        
        # Rows
        for row_data in data[1:]:
            row_cells = table.add_row().cells
            for i, cell_text in enumerate(row_data):
                row_cells[i].text = cell_text
        
        doc.add_paragraph() # Espacio después de tabla

    # ================= CONTENIDO =================

    # 1. Portada / Cabecera
    add_main_title("Media Manager Pro\nManual Técnico y Guía de Operaciones")
    
    doc.add_paragraph() # Espaciador
    add_metadata("Versión del Proyecto", "1.0")
    add_metadata("Plataforma", "Unraid / Docker / Git")
    add_metadata("Actualizado", "7 de Diciembre 2025")
    doc.add_paragraph("_" * 70) # Línea divisoria

    # 2. Índice (Simulado)
    doc.add_heading('ÍNDICE DE CONTENIDOS', level=1)
    index_items = [
        "1. Conceptos Fundamentales",
        "2. Estructura del Entorno (Unraid)",
        "3. Flujo de Desarrollo Diario (Ciclo DEV)",
        "4. Despliegue a Producción (Ciclo PROD)",
        "5. Gestión Avanzada de Docker (Dual Container)",
        "6. Persistencia y Seguridad",
        "7. Resolución de Problemas (Troubleshooting)",
        "8. Chuleta de Comandos (Cheat Sheet)"
    ]
    for item in index_items:
        doc.add_paragraph(item, style='List Bullet')
    
    doc.add_page_break()

    # 3. Secciones
    # SECCION 1
    doc.add_heading('1. CONCEPTOS FUNDAMENTALES', level=1)
    doc.add_paragraph("Para operar este sistema como un profesional, entiende los tres pilares:")
    
    p = doc.add_paragraph()
    p.add_run("Git (Control de Versiones):").bold = True
    p.add_run(" Es tu \"máquina del tiempo\".")
    doc.add_paragraph("Rama DEV: Tu laboratorio sucio. Aquí rompes cosas.", style='List Bullet 2')
    doc.add_paragraph("Rama MAIN: Tu escaparate limpio. Solo código perfecto.", style='List Bullet 2')

    p = doc.add_paragraph()
    p.add_run("Docker (Contenedores):").bold = True
    p.add_run(" Son tus \"aplicaciones envasadas\".")
    doc.add_paragraph("Imagen: La receta inmutable (el código empaquetado).", style='List Bullet 2')
    doc.add_paragraph("Contenedor: La aplicación corriendo en vivo.", style='List Bullet 2')
    
    p = doc.add_paragraph()
    p.add_run("GHCR (GitHub Container Registry):").bold = True
    p.add_run(" Tu almacén en la nube para las imágenes Docker (sustituye a Docker Hub).")

    # SECCION 2
    doc.add_heading('2. ESTRUCTURA DEL ENTORNO (UNRAID)', level=1)
    doc.add_paragraph("Tu servidor Unraid debe tener esta estructura física y lógica:")
    
    doc.add_heading('Directorios en Unraid', level=2)
    doc.add_paragraph("Zona de Trabajo (Git): /mnt/user/appdata/scripts/media-manager-working/", style='List Bullet')
    doc.add_paragraph("(Aquí editas los archivos .py, .sh y Dockerfile)", style='No Spacing')
    
    doc.add_paragraph("Configuración PROD: /mnt/user/appdata/media-manager-pro/", style='List Bullet')
    doc.add_paragraph("(Base de datos real)", style='No Spacing')

    doc.add_paragraph("Configuración DEV: /mnt/user/appdata/media-manager-dev/", style='List Bullet')
    doc.add_paragraph("(Base de datos de prueba - ¡IMPORTANTE para no borrar la real!)", style='No Spacing')

    doc.add_heading('Contenedores en Unraid', level=2)
    doc.add_paragraph("Debes tener dos contenedores creados desde la pestaña Docker:")
    
    table_data = [
        ['Contenedor', 'Imagen (Repository)', 'Puerto', 'Uso'],
        ['Media-Manager-PRO', 'ghcr.io/jvdivx/media-manager-pro:latest', '5000', 'Servicio estable 24/7'],
        ['Media-Manager-DEV', 'ghcr.io/jvdivx/media-manager-pro:dev', '5001', 'Pruebas puntuales']
    ]
    add_styled_table(table_data)

    # SECCION 3
    doc.add_heading('3. FLUJO DE DESARROLLO DIARIO (Ciclo DEV)', level=1)
    doc.add_paragraph("Objetivo: Crear una nueva funcionalidad o arreglar un bug sin riesgo.")

    doc.add_heading('Paso A: Preparar el Terreno', level=2)
    add_code_block("cd /mnt/user/appdata/scripts/media-manager-working/\ngit checkout dev\ngit pull origin dev")

    doc.add_heading('Paso B: Codificar y Guardar', level=2)
    doc.add_paragraph("Edita tus scripts y confirma los cambios:")
    add_code_block("git status\ngit add .\ngit commit -m \"Explicación breve\"\ngit push origin dev")

    doc.add_heading('Paso C: Construir y Probar (Docker)', level=2)
    doc.add_paragraph("Genera la imagen de desarrollo:")
    add_code_block("docker build -t ghcr.io/jvdivx/media-manager-pro:dev .\ndocker push ghcr.io/jvdivx/media-manager-pro:dev")
    doc.add_paragraph("Ve a la UI de Unraid, reinicia Media-Manager-DEV y prueba en el puerto 5001.")

    # SECCION 4
    doc.add_heading('4. DESPLIEGUE A PRODUCCIÓN (Ciclo PROD)', level=1)
    
    doc.add_heading('Paso A: Fusión (Merge)', level=2)
    add_code_block("git checkout main\ngit merge dev\ngit push origin main\ngit checkout dev")

    doc.add_heading('Paso B: Generar Imagen Oficial', level=2)
    add_code_block("git checkout main\ndocker build -t ghcr.io/jvdivx/media-manager-pro:latest .\ndocker push ghcr.io/jvdivx/media-manager-pro:latest\ngit checkout dev")

    doc.add_heading('Paso C: Actualizar Unraid', level=2)
    doc.add_paragraph("En Unraid, pulsa 'Check for Updates' en Media-Manager-PRO.")

    # SECCION 5
    doc.add_heading('5. GESTIÓN AVANZADA DE DOCKER', level=1)
    doc.add_heading('Cómo clonar tu contenedor para DEV', level=2)
    doc.add_paragraph("Crea un nuevo contenedor usando la plantilla del PRO pero cambiando:")
    items = [
        "Name: Media-Manager-DEV",
        "Repository: ghcr.io/jvdivx/media-manager-pro:dev",
        "Appdata: /mnt/user/appdata/media-manager-dev/",
        "Port: 5001"
    ]
    for i in items:
        doc.add_paragraph(i, style='List Bullet')

    doc.add_heading('Limpieza de Disco', level=2)
    add_code_block("docker image prune -f\ndocker system prune -a")

    # SECCION 6
    doc.add_heading('6. PERSISTENCIA Y SEGURIDAD', level=1)
    doc.add_paragraph("Unraid pierde el login de Docker al reiniciar. Solución recomendada: Hacer el paquete Público en GitHub.")
    doc.add_paragraph("Solución para repos privados (User Scripts Plugin):")
    add_code_block("echo \"TU_TOKEN_GHP\" | docker login ghcr.io -u jvdivx --password-stdin")
    
    doc.add_paragraph("Manejo de API Keys: Usa os.getenv('API_KEY') y variables de entorno en Unraid.")

    # SECCION 7
    doc.add_heading('7. RESOLUCIÓN DE PROBLEMAS', level=1)
    
    p = doc.add_paragraph()
    p.add_run("Git: Conflictos en el Merge.").bold = True
    doc.add_paragraph("Busca <<<<<<< HEAD, limpia el código y haz commit.")
    
    p = doc.add_paragraph()
    p.add_run("Docker: Manifest unknown.").bold = True
    doc.add_paragraph("No existe la imagen en la nube. Haz build y push primero.")

    # SECCION 8
    doc.add_page_break()
    doc.add_heading('8. CHULETA DE COMANDOS', level=1)
    
    doc.add_heading('Git Básico', level=2)
    git_data = [
        ['Acción', 'Comando'],
        ['Ver estado', 'git status'],
        ['Historial', 'git log --oneline'],
        ['Cambiar rama', 'git checkout [rama]'],
        ['Crear rama', 'git checkout -b [rama]'],
        ['Deshacer (archivo)', 'git restore [archivo]']
    ]
    add_styled_table(git_data)

    doc.add_heading('Docker', level=2)
    docker_data = [
        ['Acción', 'Comando'],
        ['Ver contenedores', 'docker ps'],
        ['Ver logs', 'docker logs -f [id]'],
        ['Entrar consola', 'docker exec -it [id] /bin/bash']
    ]
    add_styled_table(docker_data)

    # Guardar
    doc.save('Media_Manager_Pro_Manual.docx')
    print("Documento 'Media_Manager_Pro_Manual.docx' generado con éxito.")

if __name__ == "__main__":
    create_manual()
