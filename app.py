"""
Flask API para el analizador de anuncios de empleo.
ARCHIVO: app.py (SEPARADO de main.py)
"""

from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os
import tempfile
import json

# Importar la clase desde main.py
from main import JobAnalyzerFirebase

app = Flask(__name__)

# Configuración
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

# Función para preparar las credenciales de Firebase
def setup_firebase_credentials():
    """Configura las credenciales de Firebase desde variable de entorno o archivo."""
    firebase_creds = os.environ.get('FIREBASE_CREDENTIALS')
    
    if firebase_creds:
        # Si hay credenciales en variable de entorno, crear archivo temporal
        temp_creds_path = '/tmp/serviceAccountKey.json'
        try:
            # Intentar parsear como JSON primero para validar
            creds_dict = json.loads(firebase_creds)
            # Escribir el JSON formateado
            with open(temp_creds_path, 'w') as f:
                json.dump(creds_dict, f)
            print(f"✅ Credenciales Firebase cargadas desde variable de entorno")
            return temp_creds_path
        except json.JSONDecodeError as e:
            print(f"❌ Error parseando FIREBASE_CREDENTIALS: {e}")
            raise
    else:
        # Usar archivo local (para desarrollo)
        if os.path.exists('serviceAccountKey.json'):
            print("✅ Usando archivo serviceAccountKey.json local")
            return 'serviceAccountKey.json'
        else:
            raise FileNotFoundError(
                "No se encontró serviceAccountKey.json ni la variable FIREBASE_CREDENTIALS. "
                "Por favor configura FIREBASE_CREDENTIALS en Railway."
            )

# Inicializar el analizador con las credenciales correctas
try:
    service_account_path = setup_firebase_credentials()
    analyzer = JobAnalyzerFirebase(service_account_path)
    print("✅ Analyzer inicializado correctamente")
except Exception as e:
    print(f"❌ Error inicializando analyzer: {e}")
    analyzer = None

def allowed_file(filename):
    """Verifica si la extensión del archivo es permitida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET'])
def home():
    """Interfaz web para analizar anuncios."""
    return '''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Job Analyzer - Analizador de Anuncios</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 800px;
            width: 100%;
            padding: 40px;
        }
        
        h1 {
            color: #667eea;
            margin-bottom: 10px;
            font-size: 2em;
        }
        
        .subtitle {
            color: #666;
            margin-bottom: 30px;
        }
        
        .form-group {
            margin-bottom: 25px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 600;
        }
        
        textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 14px;
            font-family: inherit;
            resize: vertical;
            min-height: 120px;
            transition: border-color 0.3s;
        }
        
        textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .file-input-wrapper {
            position: relative;
            overflow: hidden;
            display: inline-block;
            width: 100%;
        }
        
        .file-input-wrapper input[type=file] {
            position: absolute;
            left: -9999px;
        }
        
        .file-input-label {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            background: #f8f9fa;
            border: 2px dashed #667eea;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .file-input-label:hover {
            background: #e9ecff;
            border-color: #5568d3;
        }
        
        .file-name {
            margin-top: 10px;
            color: #667eea;
            font-size: 14px;
        }
        
        button {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        button:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
        }
        
        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .loading {
            display: none;
            text-align: center;
            margin: 20px 0;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .result {
            display: none;
            margin-top: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
            border-left: 4px solid #667eea;
        }
        
        .result h3 {
            color: #667eea;
            margin-bottom: 15px;
        }
        
        .result-item {
            margin-bottom: 10px;
            padding: 10px;
            background: white;
            border-radius: 5px;
        }
        
        .result-label {
            font-weight: 600;
            color: #333;
        }
        
        .result-value {
            color: #666;
            margin-left: 10px;
        }
        
        .error {
            display: none;
            margin-top: 20px;
            padding: 15px;
            background: #fee;
            border-left: 4px solid #f44336;
            border-radius: 5px;
            color: #c00;
        }
        
        .api-info {
            margin-top: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
            font-size: 14px;
        }
        
        .api-info h4 {
            color: #667eea;
            margin-bottom: 10px;
        }
        
        .endpoint {
            background: white;
            padding: 8px 12px;
            border-radius: 5px;
            margin: 5px 0;
            font-family: monospace;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Job Analyzer</h1>
        <p class="subtitle">Analiza anuncios de empleo usando IA</p>
        
        <form id="analyzeForm">
            <div class="form-group">
                <label>📝 Texto del anuncio (opcional)</label>
                <textarea id="jobText" placeholder="Pega aquí el texto del anuncio de empleo..."></textarea>
            </div>
            
            <div class="form-group">
                <label>📸 Imagen del anuncio (opcional)</label>
                <div class="file-input-wrapper">
                    <input type="file" id="jobImage" accept="image/*">
                    <label for="jobImage" class="file-input-label">
                        📁 Click para seleccionar imagen
                    </label>
                </div>
                <div class="file-name" id="fileName"></div>
            </div>
            
            <button type="submit" id="submitBtn">
                Analizar Anuncio
            </button>
        </form>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p style="margin-top: 10px; color: #667eea;">Analizando con IA...</p>
        </div>
        
        <div class="error" id="error"></div>
        
        <div class="result" id="result">
            <h3>✅ Resultado del Análisis</h3>
            <div id="resultContent"></div>
        </div>
        
        <div class="api-info">
            <h4>📡 API Endpoints</h4>
            <div class="endpoint">GET /health - Health check</div>
            <div class="endpoint">POST /analyze/text - Analizar solo texto</div>
            <div class="endpoint">POST /analyze/image - Analizar solo imagen</div>
            <div class="endpoint">POST /analyze - Analizar texto y/o imagen</div>
        </div>
    </div>
    
    <script>
        const form = document.getElementById('analyzeForm');
        const jobText = document.getElementById('jobText');
        const jobImage = document.getElementById('jobImage');
        const fileName = document.getElementById('fileName');
        const loading = document.getElementById('loading');
        const error = document.getElementById('error');
        const result = document.getElementById('result');
        const resultContent = document.getElementById('resultContent');
        const submitBtn = document.getElementById('submitBtn');
        
        // Mostrar nombre del archivo seleccionado
        jobImage.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                fileName.textContent = '✓ ' + e.target.files[0].name;
            } else {
                fileName.textContent = '';
            }
        });
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const text = jobText.value.trim();
            const file = jobImage.files[0];
            
            // Validar que hay al menos texto o imagen
            if (!text && !file) {
                showError('Por favor proporciona al menos texto o una imagen del anuncio');
                return;
            }
            
            // Mostrar loading
            loading.style.display = 'block';
            error.style.display = 'none';
            result.style.display = 'none';
            submitBtn.disabled = true;
            
            try {
                let response;
                
                if (file && text) {
                    // Ambos: imagen y texto
                    const formData = new FormData();
                    formData.append('file', file);
                    formData.append('text', text);
                    response = await fetch('/analyze', {
                        method: 'POST',
                        body: formData
                    });
                } else if (file) {
                    // Solo imagen
                    const formData = new FormData();
                    formData.append('file', file);
                    response = await fetch('/analyze/image', {
                        method: 'POST',
                        body: formData
                    });
                } else {
                    // Solo texto
                    response = await fetch('/analyze/text', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ text })
                    });
                }
                
                const data = await response.json();
                
                if (response.ok) {
                    showResult(data);
                } else {
                    showError(data.error || 'Error al analizar el anuncio');
                }
            } catch (err) {
                showError('Error de conexión: ' + err.message);
            } finally {
                loading.style.display = 'none';
                submitBtn.disabled = false;
            }
        });
        
        function showResult(data) {
            result.style.display = 'block';
            
            if (!data.es_anuncio_empleo) {
                resultContent.innerHTML = `
                    <div class="result-item" style="background: #fee; border-left: 3px solid #f44336;">
                        <div class="result-label">⚠️ No es un anuncio de empleo</div>
                        <div class="result-value">${data.razon || 'No se detectó información de empleo'}</div>
                    </div>
                `;
                return;
            }
            
            resultContent.innerHTML = `
                ${data.position ? `<div class="result-item"><span class="result-label">💼 Puesto:</span><span class="result-value">${data.position}</span></div>` : ''}
                ${data.company ? `<div class="result-item"><span class="result-label">🏢 Empresa:</span><span class="result-value">${data.company}</span></div>` : ''}
                ${data.city ? `<div class="result-item"><span class="result-label">📍 Ciudad:</span><span class="result-value">${data.city}</span></div>` : ''}
                ${data.salary_range ? `<div class="result-item"><span class="result-label">💰 Salario:</span><span class="result-value">${data.salary_range}</span></div>` : ''}
                ${data.requirements ? `<div class="result-item"><span class="result-label">📋 Requisitos:</span><span class="result-value">${data.requirements}</span></div>` : ''}
                ${data.contact_info ? `<div class="result-item"><span class="result-label">📞 Contacto:</span><span class="result-value">${data.contact_info}</span></div>` : ''}
                ${data.url ? `<div class="result-item"><span class="result-label">🔗 URL Imagen:</span><span class="result-value"><a href="${data.url}" target="_blank">Ver imagen</a></span></div>` : ''}
                ${data.firestoreDocId ? `<div class="result-item"><span class="result-label">🆔 Doc ID:</span><span class="result-value">${data.firestoreDocId}</span></div>` : ''}
            `;
        }
        
        function showError(message) {
            error.style.display = 'block';
            error.textContent = '❌ ' + message;
        }
    </script>
</body>
</html>
    '''

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy"}), 200

@app.route('/analyze/image', methods=['POST'])
def analyze_image():
    """
    Analiza una imagen de anuncio de empleo.
    
    Espera:
    - file: archivo de imagen (multipart/form-data)
    - additional_text: texto adicional opcional (form field)
    """
    try:
        # Verificar que hay un archivo
        if 'file' not in request.files:
            return jsonify({"error": "No se proporcionó ningún archivo"}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"error": "Nombre de archivo vacío"}), 400
        
        if not allowed_file(file.filename):
            return jsonify({"error": "Tipo de archivo no permitido"}), 400
        
        # Obtener texto adicional si existe
        additional_text = request.form.get('additional_text', None)
        
        # Guardar temporalmente el archivo
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            file.save(temp_file.name)
            temp_path = temp_file.name
        
        try:
            # Procesar la imagen
            result = analyzer.process_job_image(
                image_path=temp_path,
                additional_text=additional_text,
                upload_to_storage=True,
                upload_to_firestore=True
            )
            
            return jsonify(result), 200
        
        finally:
            # Limpiar archivo temporal
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/analyze/text', methods=['POST'])
def analyze_text():
    """
    Analiza un anuncio de empleo desde texto.
    
    Espera JSON:
    {
        "text": "texto del anuncio"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({"error": "Se requiere el campo 'text'"}), 400
        
        text = data['text']
        
        if not text or not text.strip():
            return jsonify({"error": "El texto no puede estar vacío"}), 400
        
        # Procesar el texto
        result = analyzer.process_job_text(
            text=text,
            upload_to_firestore=True
        )
        
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/analyze', methods=['POST'])
def analyze():
    """
    Analiza un anuncio de empleo (imagen, texto o ambos).
    
    Puede recibir:
    - Solo imagen (multipart/form-data con 'file')
    - Solo texto (application/json con 'text')
    - Imagen + texto (multipart/form-data con 'file' y 'text')
    """
    try:
        # Determinar el tipo de contenido
        content_type = request.content_type
        
        if 'multipart/form-data' in content_type:
            # Puede tener imagen y/o texto
            has_file = 'file' in request.files and request.files['file'].filename != ''
            has_text = 'text' in request.form and request.form['text'].strip()
            
            if not has_file and not has_text:
                return jsonify({"error": "Debe proporcionar al menos una imagen o texto"}), 400
            
            temp_path = None
            
            try:
                if has_file:
                    file = request.files['file']
                    
                    if not allowed_file(file.filename):
                        return jsonify({"error": "Tipo de archivo no permitido"}), 400
                    
                    # Guardar temporalmente el archivo
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
                        file.save(temp_file.name)
                        temp_path = temp_file.name
                
                text = request.form.get('text', None) if has_text else None
                
                # Procesar
                result = analyzer.process_job(
                    image_path=temp_path if has_file else None,
                    text=text,
                    upload_to_storage=has_file,
                    upload_to_firestore=True
                )
                
                return jsonify(result), 200
            
            finally:
                # Limpiar archivo temporal
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
        
        elif 'application/json' in content_type:
            # Solo texto
            data = request.get_json()
            
            if not data or 'text' not in data:
                return jsonify({"error": "Se requiere el campo 'text'"}), 400
            
            result = analyzer.process_job_text(
                text=data['text'],
                upload_to_firestore=True
            )
            
            return jsonify(result), 200
        
        else:
            return jsonify({"error": "Content-Type no soportado"}), 400
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.errorhandler(413)
def request_entity_too_large(error):
    """Maneja archivos demasiado grandes."""
    return jsonify({"error": "Archivo demasiado grande (máximo 16MB)"}), 413

@app.errorhandler(404)
def not_found(error):
    """Maneja rutas no encontradas."""
    return jsonify({"error": "Endpoint no encontrado"}), 404

@app.errorhandler(500)
def internal_error(error):
    """Maneja errores internos."""
    return jsonify({"error": "Error interno del servidor"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)