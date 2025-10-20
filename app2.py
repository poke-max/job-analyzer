"""
Flask App - Procesador de Anuncios de Empleo con Drag & Drop
Interfaz web para arrastrar imágenes y textos que se procesan en cola
"""

from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
import threading
import time
from pathlib import Path
from datetime import datetime
from queue import Queue
import json

from main import JobAnalyzerFirebase

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['UPLOAD_FOLDER'] = 'uploads'

# Extensiones permitidas
ALLOWED_EXTENSIONS = {
    'image': {'jpg', 'jpeg', 'png', 'webp', 'bmp', 'gif'},
    'text': {'txt', 'md', 'text'}
}

# Estado global de la aplicación
app_state = {
    'analyzer': None,
    'queue': Queue(),
    'processing': False,
    'current_file': None,
    'files': [],  # Lista de todos los archivos
    'stats': {
        'total': 0,
        'procesados': 0,
        'exitosos': 0,
        'fallidos': 0,
        'no_anuncios': 0
    }
}

# Lock para operaciones thread-safe
state_lock = threading.Lock()

# Crear carpetas necesarias
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('resultados', exist_ok=True)


def allowed_file(filename):
    """Verifica si el archivo tiene una extensión permitida."""
    if '.' not in filename:
        return False, None
    ext = filename.rsplit('.', 1)[1].lower()
    
    for file_type, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return True, file_type
    
    return False, None


def get_file_id():
    """Genera un ID único para el archivo."""
    return f"{int(time.time() * 1000)}_{os.urandom(4).hex()}"


def read_text_file(file_path):
    """Lee el contenido de un archivo de texto."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='latin-1') as f:
            return f.read()


def process_file(file_data):
    """Procesa un archivo individual (imagen o texto)."""
    file_id = file_data['id']
    file_path = file_data['path']
    file_type = file_data['type']
    
    # Actualizar estado a "processing"
    with state_lock:
        for f in app_state['files']:
            if f['id'] == file_id:
                f['status'] = 'processing'
                f['started_at'] = datetime.now().isoformat()
                break
        app_state['current_file'] = file_data
    
    try:
        analyzer = app_state['analyzer']
        
        # Procesar según el tipo
        if file_type == 'image':
            datos = analyzer.process_job_image(
                file_path,
                quality=95,
                upload_to_storage=True,
                upload_to_firestore=True,
                timeout_ia=30
            )
        else:  # text
            text_content = read_text_file(file_path)
            datos = analyzer.process_job_text(
                text_content,
                upload_to_firestore=True,
                timeout_ia=30
            )
        
        # Actualizar con resultado exitoso
        with state_lock:
            for f in app_state['files']:
                if f['id'] == file_id:
                    f['status'] = 'completed'
                    f['completed_at'] = datetime.now().isoformat()
                    f['result'] = datos
                    f['is_job'] = datos.get('es_anuncio_empleo', False)
                    break
            
            app_state['stats']['procesados'] += 1
            if datos.get('es_anuncio_empleo', False):
                app_state['stats']['exitosos'] += 1
            else:
                app_state['stats']['no_anuncios'] += 1
        
    except Exception as e:
        # Actualizar con error
        with state_lock:
            for f in app_state['files']:
                if f['id'] == file_id:
                    f['status'] = 'error'
                    f['completed_at'] = datetime.now().isoformat()
                    f['error'] = str(e)
                    break
            
            app_state['stats']['procesados'] += 1
            app_state['stats']['fallidos'] += 1


def queue_processor():
    """Worker thread que procesa la cola de archivos."""
    print("🔄 Worker thread iniciado y esperando archivos...")
    while True:
        try:
            # Esperar hasta que haya algo en la cola (bloquea hasta que llegue un item)
            file_data = app_state['queue'].get(timeout=1)
            
            print(f"📥 Obtenido de cola: {file_data['name']}")
            
            with state_lock:
                app_state['processing'] = True
            
            process_file(file_data)
            
            # Pequeña pausa entre archivos
            time.sleep(1)
            
            with state_lock:
                app_state['current_file'] = None
                if app_state['queue'].empty():
                    app_state['processing'] = False
                    print("✅ Cola vacía, esperando más archivos...")
            
        except Exception as e:
            # Timeout o error - continuar esperando
            time.sleep(0.1)


@app.route('/')
def index():
    """Página principal."""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """Endpoint para subir archivos."""
    if 'file' not in request.files:
        return jsonify({'error': 'No se encontró el archivo'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'Nombre de archivo vacío'}), 400
    
    is_allowed, file_type = allowed_file(file.filename)
    
    if not is_allowed:
        return jsonify({'error': 'Tipo de archivo no permitido'}), 400
    
    # Guardar archivo
    filename = secure_filename(file.filename)
    file_id = get_file_id()
    unique_filename = f"{file_id}_{filename}"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(file_path)
    
    # Crear entrada de archivo
    file_data = {
        'id': file_id,
        'name': filename,
        'path': file_path,
        'type': file_type,
        'status': 'queued',
        'uploaded_at': datetime.now().isoformat(),
        'started_at': None,
        'completed_at': None,
        'result': None,
        'error': None,
        'is_job': None
    }
    
    # Agregar a la cola y lista
    with state_lock:
        app_state['files'].append(file_data)
        app_state['stats']['total'] += 1
        queue_size = app_state['queue'].qsize()
    
    # Poner en cola DESPUÉS del lock
    app_state['queue'].put(file_data)
    
    print(f"✅ Archivo agregado a cola: {filename} (Cola: {queue_size + 1})")
    
    return jsonify({
        'success': True,
        'file': {
            'id': file_id,
            'name': filename,
            'type': file_type,
            'status': 'queued'
        }
    })


def clean_for_json(obj):
    """Limpia un objeto para que sea serializable a JSON."""
    if obj is None:
        return None
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [clean_for_json(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        # Cualquier otro objeto lo convertimos a string
        try:
            return str(obj)
        except:
            return None


@app.route('/status')
def get_status():
    """Obtiene el estado actual del procesamiento."""
    with state_lock:
        # Obtener archivos en cola
        queued = [f for f in app_state['files'] if f['status'] == 'queued']
        processing = [f for f in app_state['files'] if f['status'] == 'processing']
        completed = [f for f in app_state['files'] if f['status'] in ['completed', 'error']]
        
        # Limpiar current_file para JSON
        current_file_clean = None
        if app_state['current_file']:
            current_file_clean = {
                'id': app_state['current_file'].get('id'),
                'name': app_state['current_file'].get('name'),
                'type': app_state['current_file'].get('type'),
                'status': app_state['current_file'].get('status')
            }
        
        response_data = {
            'processing': app_state['processing'],
            'current_file': current_file_clean,
            'stats': dict(app_state['stats']),
            'files': {
                'queued': clean_for_json(queued),
                'processing': clean_for_json(processing),
                'completed': clean_for_json(completed)
            }
        }
        
        return jsonify(response_data)


@app.route('/clear', methods=['POST'])
def clear_queue():
    """Limpia la cola y archivos completados."""
    with state_lock:
        # Mantener solo los archivos en procesamiento
        app_state['files'] = [f for f in app_state['files'] if f['status'] == 'processing']
        
        # Limpiar cola
        while not app_state['queue'].empty():
            try:
                app_state['queue'].get_nowait()
            except:
                break
        
        # Resetear stats
        app_state['stats'] = {
            'total': len(app_state['files']),
            'procesados': 0,
            'exitosos': 0,
            'fallidos': 0,
            'no_anuncios': 0
        }
    
    return jsonify({'success': True})


@app.route('/results')
def get_results():
    """Obtiene todos los resultados."""
    with state_lock:
        return jsonify({
            'files': app_state['files'],
            'stats': app_state['stats']
        })


# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Procesador de Anuncios de Empleo</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        .header {
            background: white;
            padding: 30px;
            border-radius: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            text-align: center;
        }

        .header h1 {
            color: #667eea;
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .header p {
            color: #666;
            font-size: 1.1em;
        }

        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }

        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 15px;
            color: white;
            text-align: center;
        }

        .stat-card .number {
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 5px;
        }

        .stat-card .label {
            font-size: 0.9em;
            opacity: 0.9;
        }

        .main-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
        }

        @media (max-width: 1024px) {
            .main-content {
                grid-template-columns: 1fr;
            }
        }

        .upload-section {
            background: white;
            padding: 30px;
            border-radius: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }

        .drop-zone {
            border: 3px dashed #667eea;
            border-radius: 15px;
            padding: 60px 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            background: #f8f9ff;
        }

        .drop-zone:hover, .drop-zone.drag-over {
            background: #667eea;
            color: white;
            transform: scale(1.02);
        }

        .drop-zone.drag-over {
            border-color: #764ba2;
        }

        .drop-zone svg {
            width: 80px;
            height: 80px;
            margin-bottom: 20px;
            opacity: 0.5;
        }

        .drop-zone h3 {
            font-size: 1.5em;
            margin-bottom: 10px;
        }

        .drop-zone p {
            opacity: 0.7;
        }

        .queue-section {
            background: white;
            padding: 30px;
            border-radius: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }

        .section-title {
            font-size: 1.5em;
            margin-bottom: 20px;
            color: #333;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .clear-btn {
            background: #ff4757;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9em;
            transition: all 0.3s ease;
        }

        .clear-btn:hover {
            background: #ff3838;
            transform: scale(1.05);
        }

        .file-item {
            background: #f8f9ff;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 15px;
            transition: all 0.3s ease;
        }

        .file-item.processing {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.02); }
        }

        .file-item.completed {
            background: #d4edda;
            border-left: 4px solid #28a745;
        }

        .file-item.error {
            background: #f8d7da;
            border-left: 4px solid #dc3545;
        }

        .file-icon {
            width: 40px;
            height: 40px;
            flex-shrink: 0;
        }

        .file-info {
            flex: 1;
        }

        .file-name {
            font-weight: 600;
            margin-bottom: 5px;
        }

        .file-status {
            font-size: 0.85em;
            opacity: 0.8;
        }

        .file-result {
            margin-top: 10px;
            padding: 10px;
            background: rgba(255,255,255,0.5);
            border-radius: 8px;
            font-size: 0.9em;
        }

        .spinner {
            width: 30px;
            height: 30px;
            border: 3px solid rgba(255,255,255,0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .empty-state {
            text-align: center;
            padding: 40px;
            color: #999;
        }

        .empty-state svg {
            width: 60px;
            height: 60px;
            opacity: 0.3;
            margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Procesador de Anuncios de Empleo</h1>
            <p>Arrastra imágenes o archivos de texto para procesarlos</p>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="number" id="stat-total">0</div>
                    <div class="label">Total</div>
                </div>
                <div class="stat-card">
                    <div class="number" id="stat-procesados">0</div>
                    <div class="label">Procesados</div>
                </div>
                <div class="stat-card">
                    <div class="number" id="stat-exitosos">0</div>
                    <div class="label">Exitosos</div>
                </div>
                <div class="stat-card">
                    <div class="number" id="stat-fallidos">0</div>
                    <div class="label">Fallidos</div>
                </div>
            </div>
        </div>

        <div class="main-content">
            <div class="upload-section">
                <h2 class="section-title">📤 Subir Archivos</h2>
                <div class="drop-zone" id="dropZone">
                    <svg fill="currentColor" viewBox="0 0 20 20">
                        <path d="M16.88 9.1A4 4 0 0 1 16 17H5a5 5 0 0 1-1-9.9V7a3 3 0 0 1 4.52-2.59A4.98 4.98 0 0 1 17 8c0 .38-.04.74-.12 1.1zM11 11h3l-4-4-4 4h3v3h2v-3z"/>
                    </svg>
                    <h3>Arrastra archivos aquí</h3>
                    <p>o haz clic para seleccionar</p>
                    <p style="margin-top: 10px; font-size: 0.9em;">📸 Imágenes: JPG, PNG, WebP | 📄 Textos: TXT, MD</p>
                </div>
                <input type="file" id="fileInput" style="display: none;" multiple accept=".jpg,.jpeg,.png,.webp,.bmp,.gif,.txt,.md,.text">
            </div>

            <div class="queue-section">
                <h2 class="section-title">
                    📋 Cola de Procesamiento
                    <button class="clear-btn" onclick="clearQueue()">🗑️ Limpiar</button>
                </h2>
                <div id="processingArea"></div>
                <div id="queuedArea"></div>
                <div id="completedArea"></div>
            </div>
        </div>
    </div>

    <script>
        const dropZone = document.getElementById('dropZone');
        const fileInput = document.getElementById('fileInput');

        // Drag and drop
        dropZone.addEventListener('click', () => fileInput.click());

        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('drag-over');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            handleFiles(e.dataTransfer.files);
        });

        fileInput.addEventListener('change', (e) => {
            handleFiles(e.target.files);
        });

        async function handleFiles(files) {
            for (let file of files) {
                await uploadFile(file);
            }
        }

        async function uploadFile(file) {
            const formData = new FormData();
            formData.append('file', file);

            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();
                
                if (data.success) {
                    console.log('Archivo subido:', data.file);
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (error) {
                console.error('Error al subir archivo:', error);
                alert('Error al subir archivo');
            }
        }

        function updateUI(data) {
            // Actualizar estadísticas
            document.getElementById('stat-total').textContent = data.stats.total;
            document.getElementById('stat-procesados').textContent = data.stats.procesados;
            document.getElementById('stat-exitosos').textContent = data.stats.exitosos;
            document.getElementById('stat-fallidos').textContent = data.stats.fallidos;

            // Actualizar área de procesamiento
            const processingArea = document.getElementById('processingArea');
            if (data.files.processing.length > 0) {
                processingArea.innerHTML = '<h3 style="margin-bottom: 15px; color: #667eea;">⚡ Procesando Ahora</h3>' +
                    data.files.processing.map(f => createFileCard(f, true)).join('');
            } else {
                processingArea.innerHTML = '';
            }

            // Actualizar cola
            const queuedArea = document.getElementById('queuedArea');
            if (data.files.queued.length > 0) {
                queuedArea.innerHTML = '<h3 style="margin-top: 20px; margin-bottom: 15px; color: #ffa502;">⏳ En Cola (' + data.files.queued.length + ')</h3>' +
                    data.files.queued.map(f => createFileCard(f, false)).join('');
            } else {
                queuedArea.innerHTML = '';
            }

            // Actualizar completados
            const completedArea = document.getElementById('completedArea');
            if (data.files.completed.length > 0) {
                completedArea.innerHTML = '<h3 style="margin-top: 20px; margin-bottom: 15px; color: #2ed573;">✅ Completados</h3>' +
                    data.files.completed.map(f => createFileCard(f, false)).join('');
            } else if (data.files.queued.length === 0 && data.files.processing.length === 0) {
                completedArea.innerHTML = '<div class="empty-state"><svg fill="currentColor" viewBox="0 0 20 20"><path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z"/><path fill-rule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z" clip-rule="evenodd"/></svg><p>No hay archivos en la cola</p><p style="font-size: 0.9em; margin-top: 5px;">Arrastra archivos para comenzar</p></div>';
            }
        }

        function createFileCard(file, isProcessing) {
            const typeEmoji = file.type === 'image' ? '📸' : '📄';
            const statusClass = file.status;
            
            let statusHTML = '';
            if (file.status === 'processing') {
                statusHTML = '<div class="spinner"></div>';
            } else if (file.status === 'completed') {
                const jobStatus = file.is_job ? '✅ Anuncio detectado' : '⚠️ No es anuncio';
                const position = file.result?.position || 'N/A';
                statusHTML = `<div class="file-result"><strong>${jobStatus}</strong><br>Posición: ${position}</div>`;
            } else if (file.status === 'error') {
                statusHTML = `<div class="file-result">❌ Error: ${file.error}</div>`;
            } else if (file.status === 'queued') {
                statusHTML = '<div class="file-status">⏳ En espera...</div>';
            }

            return `
                <div class="file-item ${statusClass}">
                    <div class="file-icon">${typeEmoji}</div>
                    <div class="file-info">
                        <div class="file-name">${file.name}</div>
                        ${statusHTML}
                    </div>
                    ${isProcessing ? '<div class="spinner"></div>' : ''}
                </div>
            `;
        }

        async function clearQueue() {
            if (confirm('¿Limpiar todos los archivos completados?')) {
                await fetch('/clear', { method: 'POST' });
            }
        }

        // Poll status cada segundo
        setInterval(async () => {
            try {
                const response = await fetch('/status');
                const data = await response.json();
                updateUI(data);
            } catch (error) {
                console.error('Error al obtener estado:', error);
            }
        }, 1000);

        // Cargar estado inicial
        updateUI({
            stats: { total: 0, procesados: 0, exitosos: 0, fallidos: 0 },
            files: { processing: [], queued: [], completed: [] }
        });
    </script>
</body>
</html>
'''

# Crear template
os.makedirs('templates', exist_ok=True)
with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(HTML_TEMPLATE)


def init_app():
    """Inicializa la aplicación y el analizador."""
    print("\n" + "="*80)
    print("🚀 INICIALIZANDO PROCESADOR DE ANUNCIOS DE EMPLEO")
    print("="*80)
    
    try:
        app_state['analyzer'] = JobAnalyzerFirebase('serviceAccountKey.json')
        print("✅ Analizador Firebase inicializado")
        
        # Iniciar thread de procesamiento con mayor prioridad
        processor_thread = threading.Thread(target=queue_processor, daemon=True, name="QueueProcessor")
        processor_thread.start()
        print("✅ Worker thread iniciado")
        
        # Verificar que el thread está corriendo
        time.sleep(0.5)
        if processor_thread.is_alive():
            print("✅ Worker thread confirmado activo")
        else:
            print("❌ ERROR: Worker thread no está corriendo!")
        
        print("\n" + "="*80)
        print("🌐 Servidor Flask listo")
        print("   Accede a: http://localhost:5000")
        print("   Cola de procesamiento: ACTIVA")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"❌ Error al inicializar: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == '__main__':
    init_app()
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)