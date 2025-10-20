import json
import firebase_admin
from firebase_admin import credentials, firestore, storage
from datetime import datetime
import requests
import base64
import re
from PIL import Image
from typing import Optional, Dict, Any, Union
from io import BytesIO
import time


class JobAnalyzerFirebase:
    """Sistema completo para analizar anuncios de empleo y subirlos a Firebase (sin archivos locales)."""
    
    def __init__(self, service_account_path: str = 'serviceAccountKey.json'):
        """
        Inicializa la conexión con Firebase.
        
        Args:
            service_account_path: Ruta al archivo de credenciales de Firebase
        """
        if not firebase_admin._apps:
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred, {
                'storageBucket': 'jomach-f6258.firebasestorage.app'
            })
        
        self.db = firestore.client()
        self.bucket = storage.bucket()
        print("✅ Firebase inicializado correctamente")
    
    def convert_to_webp_memory(
        self,
        image_data: Union[str, bytes, BytesIO],
        quality: int = 95
    ) -> BytesIO:
        """
        Convierte una imagen a formato WebP en memoria (sin guardar archivo).
        
        Args:
            image_data: Ruta del archivo, bytes o BytesIO de la imagen
            quality: Calidad de conversión (0-100)
        
        Returns:
            BytesIO con la imagen WebP
        """
        # Cargar imagen según el tipo de entrada
        if isinstance(image_data, str):
            with open(image_data, 'rb') as f:
                img = Image.open(f)
                img.load()  # Cargar completamente antes de cerrar el archivo
        elif isinstance(image_data, bytes):
            img = Image.open(BytesIO(image_data))
        else:
            img = Image.open(image_data)
        
        # Convertir modo de color si es necesario
        if img.mode in ('RGBA', 'LA', 'P'):
            if img.mode == 'P':
                img = img.convert('RGBA')
        elif img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGB')
        
        # Guardar en memoria
        output = BytesIO()
        img.save(output, format='WEBP', quality=quality, method=6, lossless=False)
        output.seek(0)
        
        # Calcular tamaños (si viene de archivo)
        if isinstance(image_data, str):
            import os
            original_size = os.path.getsize(image_data)
            compressed_size = len(output.getvalue())
            compression_ratio = (1 - compressed_size / original_size) * 100
            
            print(f"✓ Imagen convertida a WebP en memoria:")
            print(f"  Original: {original_size / 1024:.2f} KB → WebP: {compressed_size / 1024:.2f} KB")
            print(f"  Reducción: {compression_ratio:.2f}%")
        else:
            print(f"✓ Imagen convertida a WebP en memoria")
        
        return output
    
    def upload_image_to_storage_memory(
        self,
        image_buffer: BytesIO,
        filename_prefix: str = "job",
        folder: str = "jobs"
    ) -> str:
        """
        Sube una imagen a Firebase Storage desde memoria.
        
        Args:
            image_buffer: BytesIO con la imagen
            filename_prefix: Prefijo para el nombre del archivo
            folder: Carpeta en Storage
        
        Returns:
            URL pública de la imagen
        """
        timestamp = int(datetime.now().timestamp() * 1000)
        filename = f"{filename_prefix}_{timestamp}.webp"
        blob_path = f"{folder}/{filename}"
        
        # Subir desde memoria
        blob = self.bucket.blob(blob_path)
        image_buffer.seek(0)
        blob.upload_from_file(image_buffer, content_type='image/webp')
        
        # Hacer público
        blob.make_public()
        public_url = blob.public_url
        
        print(f"✓ Imagen subida a Firebase Storage:")
        print(f"  URL: {public_url}")
        
        return public_url
    
    def countdown_timer(self, seconds: int, mensaje: str = "Reintentando en"):
        """
        Muestra un contador regresivo en consola.
        
        Args:
            seconds: Segundos a esperar
            mensaje: Mensaje a mostrar antes del contador
        """
        print(f"\n⏳ {mensaje}:", end=" ", flush=True)
        for remaining in range(seconds, 0, -1):
            print(f"\r⏳ {mensaje}: {remaining} segundos...", end="", flush=True)
            time.sleep(1)
        print(f"\r✓ Esperando completado ({seconds}s)          ")
    
    def analyze_image_with_ollama(
        self,
        image_data: Union[str, bytes, BytesIO],
        modelo: str = "qwen3-vl:235b-cloud",
        url_ollama: str = "http://localhost:11434/api/chat",
        max_intentos: int = 3,
        tiempo_espera: int = 30
    ) -> Dict[str, Any]:
        """
        Analiza una imagen usando Ollama desde memoria con reintentos automáticos.
        
        Args:
            image_data: Ruta, bytes o BytesIO de la imagen
            modelo: Modelo de Ollama a usar
            url_ollama: URL del servidor Ollama
            max_intentos: Número máximo de intentos
            tiempo_espera: Segundos a esperar entre reintentos
        
        Returns:
            Respuesta del modelo
        """
        prompt = """Analiza la imagen adjunta y determina si es un anuncio de empleo.

Si NO es un anuncio de empleo, responde ÚNICAMENTE:
{
  "es_anuncio_empleo": false,
  "razon": "Explicación breve de por qué no es un anuncio de empleo"
}

Si SÍ es un anuncio de empleo, responde en el siguiente formato JSON (si algún dato no está presente, deja el campo vacío ""):
{
  "source": "aiGenerated",
  "es_anuncio_empleo": true,
  "position": "nombre del puesto",
  "title": "título completo incluyendo el puesto",
  "description": "descripción breve sintetizando todos los datos disponibles del anuncio",
  "city": "ciudad",
  "direction": "dirección completa",
  "company": "nombre de la empresa",
  "vacancies": "número de vacantes",
  "requeriments": "requisitos del puesto",
  "salary_range": "rango salarial",
  "phoneNumber": "teléfono de contacto",
  "email": "correo electrónico",
  "website": "sitio web",
  "workingHours": "horario de trabajo"
}

Responde SOLO con el JSON, sin texto adicional."""
        
        # Convertir a base64 según el tipo de entrada
        if isinstance(image_data, str):
            with open(image_data, "rb") as f:
                img_base64 = base64.b64encode(f.read()).decode()
        elif isinstance(image_data, bytes):
            img_base64 = base64.b64encode(image_data).decode()
        else:
            image_data.seek(0)
            img_base64 = base64.b64encode(image_data.read()).decode()
        
        payload = {
            "model": modelo,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [img_base64]
                }
            ],
            "stream": False
        }
        
        # Sistema de reintentos con contador
        for intento in range(1, max_intentos + 1):
            try:
                print(f"🔄 Intento {intento}/{max_intentos} - Consultando IA...")
                
                response = requests.post(url_ollama, json=payload, timeout=120)
                response.raise_for_status()
                
                print(f"✓ Respuesta recibida exitosamente en intento {intento}")
                return response.json()
                
            except requests.exceptions.RequestException as e:
                print(f"\n❌ Error en intento {intento}/{max_intentos}: {str(e)}")
                
                if intento < max_intentos:
                    self.countdown_timer(tiempo_espera, f"Esperando {tiempo_espera}s antes del siguiente intento")
                else:
                    print(f"\n💥 Todos los intentos fallaron después de {max_intentos} intentos")
                    raise Exception(f"No se pudo analizar la imagen después de {max_intentos} intentos: {str(e)}")
    
    def parse_json_response(self, contenido: str) -> Dict[str, Any]:
        """Extrae y parsea el JSON de la respuesta del modelo."""
        try:
            return json.loads(contenido)
        except json.JSONDecodeError:
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            matches = re.findall(json_pattern, contenido, re.DOTALL)
            
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
            
            return {
                "error": "No se pudo parsear la respuesta como JSON",
                "contenido_original": contenido
            }
    
    def upload_to_firestore(
        self,
        data: Dict[str, Any],
        collection: str = 'jobs',
        doc_id: Optional[str] = None
    ) -> str:
        """
        Sube datos a Firestore.
        
        Args:
            data: Diccionario con los datos
            collection: Nombre de la colección
            doc_id: ID personalizado (opcional)
        
        Returns:
            ID del documento creado
        """
        data['createdAt'] = firestore.SERVER_TIMESTAMP
        data['updatedAt'] = firestore.SERVER_TIMESTAMP
        
        if doc_id is None:
            city = data.get('city', 'unknown').lower().replace(' ', '_')
            position = data.get('position', 'job').lower().replace(' ', '_')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            doc_id = f"{position}_{city}_{timestamp}"
        
        doc_ref = self.db.collection(collection).document(doc_id)
        doc_ref.set(data)
        
        print(f"✓ Documento creado en Firestore:")
        print(f"  ID: {doc_id}")
        print(f"  Colección: {collection}")
        
        return doc_id
    
    def process_job_image(
        self,
        image_path: str,
        quality: int = 95,
        upload_to_storage: bool = True,
        upload_to_firestore: bool = True,
        max_intentos_ia: int = 3,
        tiempo_espera_ia: int = 30
    ) -> Dict[str, Any]:
        """
        Procesa una imagen de anuncio de empleo completamente en memoria.
        NO guarda archivos locales.
        
        Args:
            image_path: Ruta de la imagen original
            quality: Calidad de conversión WebP (0-100)
            upload_to_storage: Si True, sube la imagen a Firebase Storage
            upload_to_firestore: Si True, guarda los datos en Firestore
            max_intentos_ia: Número máximo de intentos para la IA
            tiempo_espera_ia: Segundos de espera entre intentos
        
        Returns:
            Diccionario con todos los datos procesados
        """
        print(f"\n{'='*70}")
        print("🚀 PROCESAMIENTO COMPLETO DE ANUNCIO DE EMPLEO (EN MEMORIA)")
        print(f"{'='*70}\n")
        
        # PASO 1: Convertir a WebP en memoria
        print("📸 PASO 1: Convirtiendo imagen a WebP en memoria...")
        webp_buffer = self.convert_to_webp_memory(image_path, quality=quality)
        
        # PASO 2: Analizar con Ollama (con reintentos)
        print(f"\n🤖 PASO 2: Analizando imagen con IA (hasta {max_intentos_ia} intentos)...")
        resultado = self.analyze_image_with_ollama(
            webp_buffer, 
            max_intentos=max_intentos_ia,
            tiempo_espera=tiempo_espera_ia
        )
        contenido = resultado.get("message", {}).get("content", "No hay respuesta")
        datos = self.parse_json_response(contenido)
        
        if not datos.get("es_anuncio_empleo", False):
            print("\n⚠️  La imagen NO es un anuncio de empleo")
            print(f"   Razón: {datos.get('razon', 'No especificada')}")
            return datos
        
        print("✓ Anuncio de empleo detectado correctamente")
        
        # PASO 3: Subir imagen a Firebase Storage
        if upload_to_storage:
            print("\n☁️  PASO 3: Subiendo imagen a Firebase Storage...")
            image_url = self.upload_image_to_storage_memory(webp_buffer)
            datos['url'] = image_url
        else:
            print("\n⏭️  PASO 3: Omitiendo subida a Storage")
        
        # PASO 4: Subir datos a Firestore
        if upload_to_firestore:
            print("\n📝 PASO 4: Guardando datos en Firestore...")
            doc_id = self.upload_to_firestore(datos)
            datos['firestoreDocId'] = doc_id
        else:
            print("\n⏭️  PASO 4: Omitiendo subida a Firestore")
        
        print(f"\n{'='*70}")
        print("✅ PROCESAMIENTO COMPLETADO EXITOSAMENTE")
        print(f"{'='*70}\n")
        
        return datos


# Función auxiliar para uso rápido
def procesar_anuncio_simple(image_path: str, service_account: str = 'serviceAccountKey.json'):
    """
    Función simplificada para procesar un anuncio en un solo paso (sin archivos locales).
    
    Args:
        image_path: Ruta de la imagen del anuncio
        service_account: Ruta al archivo de credenciales de Firebase
    
    Returns:
        Diccionario con los datos procesados
    """
    analyzer = JobAnalyzerFirebase(service_account)
    return analyzer.process_job_image(image_path)


# Ejemplo de uso
if __name__ == "__main__":
    # Uso simple (todo en memoria, sin archivos locales)
    resultado = procesar_anuncio_simple("asa.webp")
    
    # Mostrar resumen
    print("\n📊 RESUMEN DEL ANUNCIO:")
    print(f"   Puesto: {resultado.get('position', 'N/A')}")
    print(f"   Ciudad: {resultado.get('city', 'N/A')}")
    print(f"   Empresa: {resultado.get('company', 'N/A')}")
    print(f"   URL Imagen: {resultado.get('url', 'N/A')}")
    print(f"   Doc ID: {resultado.get('firestoreDocId', 'N/A')}")