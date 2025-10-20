import requests
import base64
import time

# Configuración
IMAGEN = "job.jpg"  # 👈 Cambia esto por tu imagen
MODELO = "gemma3:latest"

print("\n🤖 Probando Ollama con Gemma3...\n")

# Leer imagen y convertir a base64
with open(IMAGEN, "rb") as f:
    img_base64 = base64.b64encode(f.read()).decode()

# Iniciar el timer
tiempo_inicio = time.time()

# Petición a Ollama
response = requests.post(
    "http://localhost:11434/api/chat",
    json={
        "model": MODELO,
        "messages": [{
            "role": "user",
            "content": """Analiza la imagen adjunta y determina si es un anuncio de empleo.

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

    Responde SOLO con el JSON, sin texto adicional.""",
            "images": [img_base64]
        }],
        "stream": False
    }
)

# Detener el timer
tiempo_fin = time.time()
tiempo_total = tiempo_fin - tiempo_inicio

# Mostrar respuesta
if response.status_code == 200:
    contenido = response.json()["message"]["content"]
    print("✅ RESPUESTA:\n")
    print(contenido)
    print(f"\n⏱️  Tiempo de respuesta: {tiempo_total:.2f} segundos")
else:
    print(f"❌ Error: {response.status_code}")
    print(response.text)
    print(f"\n⏱️  Tiempo hasta el error: {tiempo_total:.2f} segundos")


