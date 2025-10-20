"""
Analizador de anuncios de empleo usando Ollama Cloud y Firebase.
Versión refactorizada completamente modular con soporte para imágenes y texto.
"""

from typing import Dict, Any, Optional, Union
from io import BytesIO

# Importar todos los componentes modulares
from components.image_converter import ImageConverter
from components.firebase_manager import FirebaseManager
from components.ollama_analyzer import OllamaAnalyzer


class JobAnalyzerFirebase:
    """
    Sistema completo para analizar anuncios de empleo y subirlos a Firebase.
    Orquesta los componentes: ImageConverter, OllamaAnalyzer y FirebaseManager.
    Soporta análisis de imágenes, texto o combinación de ambos.
    """
    
    def __init__(self, service_account_path: str = 'serviceAccountKey.json'):
        """
        Inicializa todos los componentes necesarios.
        
        Args:
            service_account_path: Ruta al archivo de credenciales de Firebase
        """
        # Inicializar componentes modulares
        self.image_converter = ImageConverter()
        self.ollama_analyzer = OllamaAnalyzer()
        self.firebase_manager = FirebaseManager(service_account_path)
        
        print("✅ JobAnalyzerFirebase inicializado con todos los componentes")
    
    def process_job_image(
        self,
        image_path: str,
        additional_text: str = None,
        quality: int = 95,
        upload_to_storage: bool = True,
        upload_to_firestore: bool = True,
        timeout_ia: int = 30
    ) -> Dict[str, Any]:
        """
        Procesa una imagen de anuncio de empleo completamente en memoria.
        NO guarda archivos locales.
        
        Args:
            image_path: Ruta de la imagen original
            additional_text: Texto adicional para complementar el análisis de la imagen
            quality: Calidad de conversión WebP (0-100)
            upload_to_storage: Si True, sube la imagen a Firebase Storage
            upload_to_firestore: Si True, guarda los datos en Firestore
            timeout_ia: Timeout en segundos por cada intento de la IA
        
        Returns:
            Diccionario con todos los datos procesados
        """
        print(f"\n{'='*70}")
        print("🚀 PROCESAMIENTO COMPLETO DE ANUNCIO DE EMPLEO (IMAGEN)")
        if additional_text:
            print("   + Texto adicional incluido")
        print(f"{'='*70}\n")
        
        # PASO 1: Convertir imagen a WebP en memoria
        print("📸 PASO 1: Convirtiendo imagen a WebP en memoria...")
        webp_buffer = self.image_converter.convert_to_webp(
            image_path, 
            quality=quality,
            verbose=True
        )
        
        # PASO 2: Analizar con Ollama Cloud
        print(f"\n🤖 PASO 2: Analizando imagen con Ollama Cloud...")
        datos = self.ollama_analyzer.analyze_job_image(
            webp_buffer,
            additional_text=additional_text,
            timeout=timeout_ia
        )
        
        # Verificar si es un anuncio de empleo
        if not datos.get("es_anuncio_empleo", False):
            print("\n⚠️  La imagen NO es un anuncio de empleo")
            print(f"   Razón: {datos.get('razon', 'No especificada')}")
            return datos
        
        print("✓ Anuncio de empleo detectado correctamente")
        
        # PASO 3: Subir imagen a Firebase Storage
        if upload_to_storage:
            print("\n☁️  PASO 3: Subiendo imagen a Firebase Storage...")
            image_url = self.firebase_manager.upload_image_to_storage(
                webp_buffer,
                filename_prefix="job",
                folder="jobs",
                make_public=True
            )
            datos['url'] = image_url
        else:
            print("\n⏭️  PASO 3: Omitiendo subida a Storage")
        
        # PASO 4: Subir datos a Firestore
        if upload_to_firestore:
            print("\n📝 PASO 4: Guardando datos en Firestore...")
            doc_id = self.firebase_manager.upload_to_firestore(
                datos,
                collection='jobs',
                auto_timestamps=True
            )
            datos['firestoreDocId'] = doc_id
        else:
            print("\n⏭️  PASO 4: Omitiendo subida a Firestore")
        
        print(f"\n{'='*70}")
        print("✅ PROCESAMIENTO COMPLETADO EXITOSAMENTE")
        print(f"{'='*70}\n")
        
        return datos
    
    def process_job_text(
        self,
        text: str,
        upload_to_firestore: bool = True,
        timeout_ia: int = 30
    ) -> Dict[str, Any]:
        """
        Procesa un anuncio de empleo desde texto puro (sin imagen).
        
        Args:
            text: Texto del anuncio de empleo
            upload_to_firestore: Si True, guarda los datos en Firestore
            timeout_ia: Timeout en segundos por cada intento de la IA
        
        Returns:
            Diccionario con todos los datos procesados
        """
        print(f"\n{'='*70}")
        print("🚀 PROCESAMIENTO COMPLETO DE ANUNCIO DE EMPLEO (TEXTO)")
        print(f"{'='*70}\n")
        
        # PASO 1: Analizar texto con Ollama Cloud
        print(f"🤖 PASO 1: Analizando texto con Ollama Cloud...")
        datos = self.ollama_analyzer.analyze_job_text(
            text,
            timeout=timeout_ia
        )
        
        # Verificar si es un anuncio de empleo
        if not datos.get("es_anuncio_empleo", False):
            print("\n⚠️  El texto NO es un anuncio de empleo")
            print(f"   Razón: {datos.get('razon', 'No especificada')}")
            return datos
        
        print("✓ Anuncio de empleo detectado correctamente")
        
        # PASO 2: Subir datos a Firestore
        if upload_to_firestore:
            print("\n📝 PASO 2: Guardando datos en Firestore...")
            doc_id = self.firebase_manager.upload_to_firestore(
                datos,
                collection='jobs',
                auto_timestamps=True
            )
            datos['firestoreDocId'] = doc_id
        else:
            print("\n⏭️  PASO 2: Omitiendo subida a Firestore")
        
        print(f"\n{'='*70}")
        print("✅ PROCESAMIENTO COMPLETADO EXITOSAMENTE")
        print(f"{'='*70}\n")
        
        return datos
    
    def process_job(
        self,
        image_path: str = None,
        text: str = None,
        quality: int = 95,
        upload_to_storage: bool = True,
        upload_to_firestore: bool = True,
        timeout_ia: int = 30
    ) -> Dict[str, Any]:
        """
        Método universal para procesar anuncios de empleo.
        Puede recibir imagen, texto o ambos.
        
        Args:
            image_path: Ruta de la imagen (opcional)
            text: Texto del anuncio (opcional)
            quality: Calidad de conversión WebP (0-100)
            upload_to_storage: Si True, sube la imagen a Firebase Storage
            upload_to_firestore: Si True, guarda los datos en Firestore
            timeout_ia: Timeout en segundos por cada intento de la IA
        
        Returns:
            Diccionario con todos los datos procesados
        
        Raises:
            ValueError: Si no se proporciona ni imagen ni texto
        """
        if not image_path and not text:
            raise ValueError("❌ Debes proporcionar al menos una imagen o texto")
        
        # Caso 1: Solo imagen
        if image_path and not text:
            return self.process_job_image(
                image_path=image_path,
                quality=quality,
                upload_to_storage=upload_to_storage,
                upload_to_firestore=upload_to_firestore,
                timeout_ia=timeout_ia
            )
        
        # Caso 2: Solo texto
        if text and not image_path:
            return self.process_job_text(
                text=text,
                upload_to_firestore=upload_to_firestore,
                timeout_ia=timeout_ia
            )
        
        # Caso 3: Imagen + texto adicional
        return self.process_job_image(
            image_path=image_path,
            additional_text=text,
            quality=quality,
            upload_to_storage=upload_to_storage,
            upload_to_firestore=upload_to_firestore,
            timeout_ia=timeout_ia
        )


# Funciones auxiliares para uso rápido
def procesar_anuncio_simple(
    image_path: str = None,
    text: str = None,
    service_account: str = 'serviceAccountKey.json'
) -> Dict[str, Any]:
    """
    Función simplificada para procesar un anuncio en un solo paso.
    
    Args:
        image_path: Ruta de la imagen del anuncio (opcional)
        text: Texto del anuncio (opcional)
        service_account: Ruta al archivo de credenciales de Firebase
    
    Returns:
        Diccionario con los datos procesados
    """
    analyzer = JobAnalyzerFirebase(service_account)
    return analyzer.process_job(image_path=image_path, text=text)


def procesar_imagen(
    image_path: str,
    service_account: str = 'serviceAccountKey.json'
) -> Dict[str, Any]:
    """
    Procesa solo una imagen.
    
    Args:
        image_path: Ruta de la imagen
        service_account: Ruta al archivo de credenciales de Firebase
    
    Returns:
        Diccionario con los datos procesados
    """
    analyzer = JobAnalyzerFirebase(service_account)
    return analyzer.process_job_image(image_path)


def procesar_texto(
    text: str,
    service_account: str = 'serviceAccountKey.json'
) -> Dict[str, Any]:
    """
    Procesa solo texto.
    
    Args:
        text: Texto del anuncio
        service_account: Ruta al archivo de credenciales de Firebase
    
    Returns:
        Diccionario con los datos procesados
    """
    analyzer = JobAnalyzerFirebase(service_account)
    return analyzer.process_job_text(text)


# Ejemplo de uso
if __name__ == "__main__":
    print("\n" + "="*70)
    print("EJEMPLO 1: Procesar solo imagen")
    print("="*70)
    
    # Uso simple (solo imagen)
    resultado1 = procesar_imagen("ee.webp")
    
    # Mostrar resumen
    print("\n📊 RESUMEN DEL ANUNCIO:")
    print(f"   Puesto: {resultado1.get('position', 'N/A')}")
    print(f"   Ciudad: {resultado1.get('city', 'N/A')}")
    print(f"   Empresa: {resultado1.get('company', 'N/A')}")
    print(f"   Salario: {resultado1.get('salary_range', 'N/A')}")
    print(f"   URL Imagen: {resultado1.get('url', 'N/A')}")
    print(f"   Doc ID: {resultado1.get('firestoreDocId', 'N/A')}")
    
    print("\n" + "="*70)
    print("EJEMPLO 2: Procesar solo texto")
    print("="*70)
    
    # Procesar solo texto
    texto_anuncio = """
    SE BUSCA DESARROLLADOR PYTHON
    
    Empresa: Tech Solutions SA
    Ubicación: Asunción, Paraguay
    Salario: 3.000.000 - 4.500.000 Gs
    
    Requisitos:
    - 2 años de experiencia en Python
    - Conocimientos en Django y Flask
    - Trabajo en equipo
    
    Contacto: rrhh@techsolutions.com.py
    Tel: 021-456789
    """
    
    resultado2 = procesar_texto(texto_anuncio)
    
    print("\n📊 RESUMEN DEL ANUNCIO:")
    print(f"   Puesto: {resultado2.get('position', 'N/A')}")
    print(f"   Ciudad: {resultado2.get('city', 'N/A')}")
    print(f"   Empresa: {resultado2.get('company', 'N/A')}")
    print(f"   Salario: {resultado2.get('salary_range', 'N/A')}")
    print(f"   Doc ID: {resultado2.get('firestoreDocId', 'N/A')}")
    
    print("\n" + "="*70)
    print("EJEMPLO 3: Procesar imagen + texto adicional")
    print("="*70)
    
    # Procesar imagen con texto adicional
    analyzer = JobAnalyzerFirebase()
    resultado3 = analyzer.process_job(
        image_path="ee.webp",
        text="Información adicional: La empresa está ubicada en el centro de Asunción. Contacto WhatsApp: 0981-123456"
    )
    
    print("\n📊 RESUMEN DEL ANUNCIO:")
    print(f"   Puesto: {resultado3.get('position', 'N/A')}")
    print(f"   Ciudad: {resultado3.get('city', 'N/A')}")
    print(f"   Empresa: {resultado3.get('company', 'N/A')}")
    print(f"   URL Imagen: {resultado3.get('url', 'N/A')}")
    print(f"   Doc ID: {resultado3.get('firestoreDocId', 'N/A')}")