"""
Flask API para el analizador de anuncios de empleo.
ESTE ARCHIVO DEBE SER app.py (NO main.py)
"""

from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os
import tempfile

# Importar desde main.py (NO desde este archivo)
from main import JobAnalyzerFirebase

app = Flask(__name__)

# Configuración
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

# Inicializar el analizador una sola vez
try:
    analyzer = JobAnalyzerFirebase()
    print("✅ Analyzer inicializado correctamente")
except Exception as e:
    print(f"❌ Error al inicializar analyzer: {e}")
    analyzer = None

def allowed_file(filename):
    """Verifica si la extensión del archivo es permitida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET'])
def home():
    """Endpoint de bienvenida."""
    return jsonify({
        "status": "ok",
        "message": "Job Analyzer API está funcionando",
        "endpoints": {
            "/": "GET - Este mensaje",
            "/health": "GET - Health check",
            "/analyze/image": "POST - Analizar imagen (multipart/form-data)",
            "/analyze/text": "POST - Analizar texto (application/json)",
            "/analyze": "POST - Analizar imagen y/o texto"
        },
        "version": "1.0.0"
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    if analyzer is None:
        return jsonify({"status": "unhealthy", "error": "Analyzer no inicializado"}), 503
    return jsonify({"status": "healthy"}), 200

@app.route('/analyze/image', methods=['POST'])
def analyze_image():
    """
    Analiza una imagen de anuncio de empleo.
    
    Espera:
    - file: archivo de imagen (multipart/form-data)
    - additional_text: texto adicional opcional (form field)
    """
    if analyzer is None:
        return jsonify({"error": "Servicio no disponible"}), 503
    
    try:
        # Verificar que hay un archivo
        if 'file' not in request.files:
            return jsonify({"error": "No se proporcionó ningún archivo"}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"error": "Nombre de archivo vacío"}), 400
        
        if not allowed_file(file.filename):
            return jsonify({"error": f"Tipo de archivo no permitido. Permitidos: {', '.join(ALLOWED_EXTENSIONS)}"}), 400
        
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
        return jsonify({"error": f"Error al procesar imagen: {str(e)}"}), 500

@app.route('/analyze/text', methods=['POST'])
def analyze_text():
    """
    Analiza un anuncio de empleo desde texto.
    
    Espera JSON:
    {
        "text": "texto del anuncio"
    }
    """
    if analyzer is None:
        return jsonify({"error": "Servicio no disponible"}), 503
    
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({"error": "Se requiere el campo 'text' en formato JSON"}), 400
        
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
        return jsonify({"error": f"Error al procesar texto: {str(e)}"}), 500

@app.route('/analyze', methods=['POST'])
def analyze():
    """
    Analiza un anuncio de empleo (imagen, texto o ambos).
    
    Puede recibir:
    - Solo imagen (multipart/form-data con 'file')
    - Solo texto (application/json con 'text')
    - Imagen + texto (multipart/form-data con 'file' y 'text')
    """
    if analyzer is None:
        return jsonify({"error": "Servicio no disponible"}), 503
    
    try:
        # Determinar el tipo de contenido
        content_type = request.content_type or ''
        
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
                        return jsonify({"error": f"Tipo de archivo no permitido. Permitidos: {', '.join(ALLOWED_EXTENSIONS)}"}), 400
                    
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
                return jsonify({"error": "Se requiere el campo 'text' en formato JSON"}), 400
            
            result = analyzer.process_job_text(
                text=data['text'],
                upload_to_firestore=True
            )
            
            return jsonify(result), 200
        
        else:
            return jsonify({
                "error": "Content-Type no soportado",
                "received": content_type,
                "supported": ["multipart/form-data", "application/json"]
            }), 400
    
    except Exception as e:
        return jsonify({"error": f"Error al procesar: {str(e)}"}), 500

@app.errorhandler(413)
def request_entity_too_large(error):
    """Maneja archivos demasiado grandes."""
    return jsonify({"error": "Archivo demasiado grande (máximo 16MB)"}), 413

@app.errorhandler(404)
def not_found(error):
    """Maneja rutas no encontradas."""
    return jsonify({
        "error": "Endpoint no encontrado",
        "path": request.path,
        "method": request.method
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    """Maneja métodos no permitidos."""
    return jsonify({
        "error": "Método no permitido",
        "path": request.path,
        "method": request.method
    }), 405

@app.errorhandler(500)
def internal_error(error):
    """Maneja errores internos."""
    return jsonify({"error": "Error interno del servidor"}), 500

# Este bloque solo se ejecuta cuando corres python app.py directamente
# NO se ejecuta cuando Gunicorn importa el módulo
if __name__ == '__main__':
    print("🚀 Iniciando Flask en modo desarrollo...")
    app.run(host='0.0.0.0', port=8080, debug=True)