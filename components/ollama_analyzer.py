"""
Módulo para análisis de imágenes y texto usando Ollama Cloud.
Maneja la comunicación con la API de Ollama y el parseo de respuestas.
"""

import json
import base64
import re
from typing import Dict, Any, Union, Optional
from io import BytesIO
import time
import os
from dotenv import load_dotenv
import requests

# Cargar variables de entorno
load_dotenv()


class OllamaAnalyzer:
    """Analizador de imágenes y texto usando Ollama Cloud API."""
    
    # Prompt por defecto para análisis de anuncios de empleo
    DEFAULT_JOB_PROMPT = """Analiza la imagen adjunta y determina si es un anuncio de empleo.

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

    # Prompt para análisis solo de texto
    DEFAULT_TEXT_JOB_PROMPT = """Analiza el texto adjunto y determina si es un anuncio de empleo.

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
    
    def __init__(self, api_key: str = None, api_url: str = "https://ollama.com/api/chat"):
        """
        Inicializa el analizador de Ollama Cloud.
        
        Args:
            api_key: API Key de Ollama Cloud (si no se proporciona, busca en .env)
            api_url: URL de la API de Ollama Cloud
        """
        self.api_key = api_key or os.getenv('OLLAMA_API_KEY')
        self.api_url = api_url
        
        if not self.api_key:
            raise ValueError("❌ OLLAMA_API_KEY no encontrada. Proporciona api_key o configura .env")
        
        print(f"✅ Ollama Cloud configurado")
        print(f"   API URL: {self.api_url}")
        print(f"   API Key: {self.api_key[:20]}...")
    
    def _convert_to_base64(self, image_data: Union[str, bytes, BytesIO]) -> str:
        """
        Convierte una imagen a base64.
        
        Args:
            image_data: Ruta del archivo, bytes o BytesIO
        
        Returns:
            String en base64
        """
        if isinstance(image_data, str):
            with open(image_data, "rb") as f:
                return base64.b64encode(f.read()).decode()
        elif isinstance(image_data, bytes):
            return base64.b64encode(image_data).decode()
        else:  # BytesIO
            image_data.seek(0)
            return base64.b64encode(image_data.read()).decode()
    
    def analyze_image(
        self,
        image_data: Union[str, bytes, BytesIO],
        prompt: str = None,
        additional_text: str = None,
        model: str = "qwen3-vl:235b-cloud",
        timeout: int = 30,
        max_retries: int = None,
        retry_delay: int = 1
    ) -> Dict[str, Any]:
        """
        Analiza una imagen usando Ollama Cloud, con texto adicional opcional.
        
        Args:
            image_data: Ruta, bytes o BytesIO de la imagen
            prompt: Prompt personalizado (usa DEFAULT_JOB_PROMPT si no se proporciona)
            additional_text: Texto adicional para enviar junto con la imagen
            model: Modelo de Ollama Cloud a usar
            timeout: Timeout en segundos por intento
            max_retries: Número máximo de reintentos (None = infinito)
            retry_delay: Segundos de espera entre reintentos
        
        Returns:
            Respuesta completa de la API
        """
        # Usar prompt por defecto si no se proporciona
        prompt = prompt or self.DEFAULT_JOB_PROMPT
        
        # Si hay texto adicional, agregarlo al prompt
        if additional_text:
            prompt = f"{prompt}\n\nTexto adicional proporcionado:\n{additional_text}"
        
        # Convertir imagen a base64
        img_base64 = self._convert_to_base64(image_data)
        
        # Preparar payload
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [img_base64]
                }
            ],
            "stream": False
        }
        
        # Headers con autenticación
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Sistema de reintentos
        intento = 0
        tiempo_inicio = time.time()
        
        while max_retries is None or intento < max_retries:
            intento += 1
            try:
                print(f"🔄 Intento {intento} - Consultando Ollama Cloud (timeout: {timeout}s)...")
                
                tiempo_inicio = time.time()
                
                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=timeout
                )
                
                tiempo_transcurrido = time.time() - tiempo_inicio
                
                print(f"   Status Code: {response.status_code} (Tiempo: {tiempo_transcurrido:.2f}s)")
                
                if response.status_code != 200:
                    print(f"   Response Text: {response.text[:500]}")
                    raise requests.exceptions.RequestException(f"Status code {response.status_code}")
                
                response.raise_for_status()
                
                if not response.text:
                    raise ValueError("Respuesta vacía del servidor")
                
                print(f"✅ Respuesta recibida exitosamente en intento {intento} ({tiempo_transcurrido:.2f}s)")
                return response.json()
                
            except (requests.exceptions.Timeout, requests.exceptions.RequestException, ValueError) as e:
                tiempo_transcurrido = time.time() - tiempo_inicio
                
                print(f"\n❌ Error en intento {intento} ({tiempo_transcurrido:.2f}s): {str(e)}")
                
                if max_retries is not None and intento >= max_retries:
                    raise Exception(f"Máximo de {max_retries} reintentos alcanzado")
                
                print(f"⚡ Reintentando en {retry_delay}s...")
                time.sleep(retry_delay)
    
    def analyze_text(
        self,
        text: str,
        prompt: str = None,
        model: str = "qwen3-vl:235b-cloud",
        timeout: int = 30,
        max_retries: int = None,
        retry_delay: int = 1
    ) -> Dict[str, Any]:
        """
        Analiza solo texto usando Ollama Cloud (sin imagen).
        
        Args:
            text: Texto a analizar
            prompt: Prompt personalizado (usa DEFAULT_TEXT_JOB_PROMPT si no se proporciona)
            model: Modelo de Ollama Cloud a usar
            timeout: Timeout en segundos por intento
            max_retries: Número máximo de reintentos (None = infinito)
            retry_delay: Segundos de espera entre reintentos
        
        Returns:
            Respuesta completa de la API
        """
        # Usar prompt por defecto si no se proporciona
        prompt = prompt or self.DEFAULT_TEXT_JOB_PROMPT
        
        # Combinar prompt con el texto
        full_prompt = f"{prompt}\n\nTexto a analizar:\n{text}"
        
        # Preparar payload (sin imágenes)
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": full_prompt
                }
            ],
            "stream": False
        }
        
        # Headers con autenticación
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Sistema de reintentos
        intento = 0
        tiempo_inicio = time.time()
        
        while max_retries is None or intento < max_retries:
            intento += 1
            try:
                print(f"🔄 Intento {intento} - Consultando Ollama Cloud para texto (timeout: {timeout}s)...")
                
                tiempo_inicio = time.time()
                
                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=timeout
                )
                
                tiempo_transcurrido = time.time() - tiempo_inicio
                
                print(f"   Status Code: {response.status_code} (Tiempo: {tiempo_transcurrido:.2f}s)")
                
                if response.status_code != 200:
                    print(f"   Response Text: {response.text[:500]}")
                    raise requests.exceptions.RequestException(f"Status code {response.status_code}")
                
                response.raise_for_status()
                
                if not response.text:
                    raise ValueError("Respuesta vacía del servidor")
                
                print(f"✅ Respuesta recibida exitosamente en intento {intento} ({tiempo_transcurrido:.2f}s)")
                return response.json()
                
            except (requests.exceptions.Timeout, requests.exceptions.RequestException, ValueError) as e:
                tiempo_transcurrido = time.time() - tiempo_inicio
                
                print(f"\n❌ Error en intento {intento} ({tiempo_transcurrido:.2f}s): {str(e)}")
                
                if max_retries is not None and intento >= max_retries:
                    raise Exception(f"Máximo de {max_retries} reintentos alcanzado")
                
                print(f"⚡ Reintentando en {retry_delay}s...")
                time.sleep(retry_delay)
    
    def parse_json_response(self, content: str) -> Dict[str, Any]:
        """
        Extrae y parsea el JSON de la respuesta del modelo.
        
        Args:
            content: Contenido de texto de la respuesta
        
        Returns:
            Diccionario con los datos parseados
        """
        # Intentar parsear directamente
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Buscar JSON en el texto usando regex
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, content, re.DOTALL)
        
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        # Si no se pudo parsear
        return {
            "error": "No se pudo parsear la respuesta como JSON",
            "contenido_original": content
        }
    
    def analyze_job_image(
        self,
        image_data: Union[str, bytes, BytesIO],
        additional_text: str = None,
        model: str = "qwen3-vl:235b-cloud",
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Método simplificado para analizar anuncios de empleo desde imagen.
        Combina analyze_image y parse_json_response.
        
        Args:
            image_data: Ruta, bytes o BytesIO de la imagen
            additional_text: Texto adicional para complementar el análisis
            model: Modelo de Ollama Cloud
            timeout: Timeout en segundos
        
        Returns:
            Diccionario con los datos del anuncio parseados
        """
        # Analizar imagen
        resultado = self.analyze_image(
            image_data=image_data,
            additional_text=additional_text,
            model=model,
            timeout=timeout,
            max_retries=None  # Reintentos infinitos
        )
        
        # Extraer contenido
        contenido = resultado.get("message", {}).get("content", "No hay respuesta")
        
        # Parsear JSON
        return self.parse_json_response(contenido)
    
    def analyze_job_text(
        self,
        text: str,
        model: str = "qwen3-vl:235b-cloud",
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Método simplificado para analizar anuncios de empleo desde texto puro.
        Combina analyze_text y parse_json_response.
        
        Args:
            text: Texto del anuncio a analizar
            model: Modelo de Ollama Cloud
            timeout: Timeout en segundos
        
        Returns:
            Diccionario con los datos del anuncio parseados
        """
        # Analizar texto
        resultado = self.analyze_text(
            text=text,
            model=model,
            timeout=timeout,
            max_retries=None  # Reintentos infinitos
        )
        
        # Extraer contenido
        contenido = resultado.get("message", {}).get("content", "No hay respuesta")
        
        # Parsear JSON
        return self.parse_json_response(contenido)


# Ejemplo de uso
if __name__ == "__main__":
    # Inicializar analizador
    analyzer = OllamaAnalyzer()
    
    print("\n" + "="*80)
    print("EJEMPLO 1: Analizar imagen")
    print("="*80)
    
    # Analizar una imagen
    resultado = analyzer.analyze_job_image("ee.webp")
    
    # Mostrar resultado
    print("\n📊 RESULTADO DEL ANÁLISIS:")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    
    if resultado.get("es_anuncio_empleo"):
        print(f"\n✅ Anuncio de empleo detectado:")
        print(f"   Puesto: {resultado.get('position', 'N/A')}")
        print(f"   Ciudad: {resultado.get('city', 'N/A')}")
        print(f"   Empresa: {resultado.get('company', 'N/A')}")
    else:
        print(f"\n⚠️  No es un anuncio de empleo")
        print(f"   Razón: {resultado.get('razon', 'N/A')}")
    
    print("\n" + "="*80)
    print("EJEMPLO 2: Analizar imagen con texto adicional")
    print("="*80)
    
    # Analizar imagen con texto adicional
    resultado2 = analyzer.analyze_job_image(
        "ee.webp",
        additional_text="La empresa se encuentra en Asunción, zona céntrica. Contacto: 0981-123456"
    )
    print("\n📊 RESULTADO CON TEXTO ADICIONAL:")
    print(json.dumps(resultado2, indent=2, ensure_ascii=False))
    
    print("\n" + "="*80)
    print("EJEMPLO 3: Analizar solo texto (sin imagen)")
    print("="*80)
    
    # Analizar solo texto
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
    
    resultado3 = analyzer.analyze_job_text(texto_anuncio)
    
    print("\n📊 RESULTADO DEL ANÁLISIS DE TEXTO:")
    print(json.dumps(resultado3, indent=2, ensure_ascii=False))
    
    if resultado3.get("es_anuncio_empleo"):
        print(f"\n✅ Anuncio de empleo detectado:")
        print(f"   Puesto: {resultado3.get('position', 'N/A')}")
        print(f"   Ciudad: {resultado3.get('city', 'N/A')}")
        print(f"   Empresa: {resultado3.get('company', 'N/A')}")
        print(f"   Salario: {resultado3.get('salary_range', 'N/A')}")