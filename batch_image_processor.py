"""
Procesador por lotes de anuncios de empleo - Multi-formato.
Procesa IMÁGENES y ARCHIVOS DE TEXTO desde una carpeta.
"""

import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from queue import Queue
from threading import Lock
import json

from main import JobAnalyzerFirebase


class BatchMultiFormatProcessor:
    """
    Procesador por lotes que acepta tanto imágenes como archivos de texto.
    Escanea una carpeta y procesa automáticamente todos los archivos soportados.
    """
    
    # Extensiones soportadas
    IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif']
    TEXT_EXTENSIONS = ['.txt', '.md', '.text']
    
    def __init__(
        self,
        service_account_path: str = 'serviceAccountKey.json',
        output_folder: str = 'resultados',
        auto_save_results: bool = True
    ):
        """
        Inicializa el procesador multi-formato.
        
        Args:
            service_account_path: Ruta al archivo de credenciales de Firebase
            output_folder: Carpeta donde guardar los resultados
            auto_save_results: Si True, guarda automáticamente los resultados en JSON
        """
        self.analyzer = JobAnalyzerFirebase(service_account_path)
        self.output_folder = output_folder
        self.auto_save_results = auto_save_results
        
        # Cola de procesamiento con información del tipo
        self.queue = Queue()
        
        # Resultados y estadísticas
        self.results = []
        self.stats = {
            'total': 0,
            'procesados': 0,
            'exitosos': 0,
            'fallidos': 0,
            'no_anuncios': 0,
            'en_cola': 0,
            'imagenes': 0,
            'textos': 0
        }
        
        # Control de estado
        self.is_processing = False
        self.is_paused = False
        self.lock = Lock()
        
        # Parámetros de configuración
        self.config = {
            'quality': 95,
            'upload_to_storage': True,
            'upload_to_firestore': True,
            'timeout_ia': 30
        }
        
        # Crear carpeta de resultados
        os.makedirs(output_folder, exist_ok=True)
        
        print("✅ BatchMultiFormatProcessor inicializado")
        print(f"   📸 Soporta imágenes: {', '.join(self.IMAGE_EXTENSIONS)}")
        print(f"   📄 Soporta textos: {', '.join(self.TEXT_EXTENSIONS)}")
        print(f"   📁 Carpeta de resultados: {output_folder}")
    
    def add_files_from_folder(
        self,
        folder_path: str,
        include_images: bool = True,
        include_texts: bool = True,
        recursive: bool = False
    ) -> Dict[str, int]:
        """
        Agrega todos los archivos soportados de una carpeta a la cola.
        
        Args:
            folder_path: Ruta de la carpeta
            include_images: Si True, incluye archivos de imagen
            include_texts: Si True, incluye archivos de texto
            recursive: Si True, busca en subcarpetas
        
        Returns:
            Diccionario con conteo de archivos agregados por tipo
        """
        folder = Path(folder_path)
        
        if not folder.exists():
            print(f"❌ La carpeta no existe: {folder_path}")
            return {'imagenes': 0, 'textos': 0}
        
        conteo = {'imagenes': 0, 'textos': 0}
        
        # Función para procesar archivos
        def procesar_archivos(directorio):
            # Procesar imágenes
            if include_images:
                for ext in self.IMAGE_EXTENSIONS:
                    for file_path in directorio.glob(f"*{ext}"):
                        if file_path.is_file():
                            self.add_file(str(file_path), file_type='image')
                            conteo['imagenes'] += 1
            
            # Procesar textos
            if include_texts:
                for ext in self.TEXT_EXTENSIONS:
                    for file_path in directorio.glob(f"*{ext}"):
                        if file_path.is_file():
                            self.add_file(str(file_path), file_type='text')
                            conteo['textos'] += 1
        
        # Procesar carpeta principal
        procesar_archivos(folder)
        
        # Procesar subcarpetas si es recursivo
        if recursive:
            for subfolder in folder.rglob('*'):
                if subfolder.is_dir():
                    procesar_archivos(subfolder)
        
        total = conteo['imagenes'] + conteo['textos']
        print(f"\n✅ Se agregaron {total} archivos a la cola desde: {folder_path}")
        print(f"   📸 Imágenes: {conteo['imagenes']}")
        print(f"   📄 Textos: {conteo['textos']}")
        
        return conteo
    
    def add_file(self, file_path: str, file_type: str = None) -> bool:
        """
        Agrega un archivo individual a la cola.
        
        Args:
            file_path: Ruta del archivo
            file_type: 'image' o 'text' (si None, se detecta automáticamente)
        
        Returns:
            True si se agregó correctamente
        """
        path = Path(file_path)
        
        if not path.exists():
            print(f"❌ Archivo no encontrado: {file_path}")
            return False
        
        # Detectar tipo si no se especificó
        if file_type is None:
            ext = path.suffix.lower()
            if ext in self.IMAGE_EXTENSIONS:
                file_type = 'image'
            elif ext in self.TEXT_EXTENSIONS:
                file_type = 'text'
            else:
                print(f"⚠️  Extensión no soportada: {ext}")
                return False
        
        with self.lock:
            self.queue.put({
                'path': file_path,
                'type': file_type,
                'name': path.name
            })
            self.stats['total'] += 1
            self.stats['en_cola'] += 1
            if file_type == 'image':
                self.stats['imagenes'] += 1
            else:
                self.stats['textos'] += 1
        
        emoji = "📸" if file_type == 'image' else "📄"
        print(f"➕ {emoji} Archivo agregado: {path.name}")
        return True
    
    def _print_banner(self):
        """Imprime el banner inicial."""
        print("\n" + "="*80)
        print("🚀 PROCESADOR POR LOTES MULTI-FORMATO DE ANUNCIOS DE EMPLEO")
        print("="*80)
        print(f"   Total en cola: {self.stats['total']}")
        print(f"   📸 Imágenes: {self.stats['imagenes']}")
        print(f"   📄 Textos: {self.stats['textos']}")
        print(f"   Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80 + "\n")
    
    def _print_progress(self, current: int, total: int, file_info: Dict):
        """Imprime el progreso actual."""
        porcentaje = (current / total * 100) if total > 0 else 0
        emoji = "📸" if file_info['type'] == 'image' else "📄"
        tipo = "Imagen" if file_info['type'] == 'image' else "Texto"
        
        print(f"\n{'='*80}")
        print(f"📊 PROGRESO: {current}/{total} ({porcentaje:.1f}%)")
        print(f"   {emoji} Archivo actual: {file_info['name']} ({tipo})")
        print(f"   ✅ Exitosos: {self.stats['exitosos']}")
        print(f"   ⚠️  No anuncios: {self.stats['no_anuncios']}")
        print(f"   ❌ Fallidos: {self.stats['fallidos']}")
        print(f"   📥 En cola: {self.stats['en_cola']}")
        print("="*80)
    
    def _print_summary(self, tiempo_total: float):
        """Imprime el resumen final."""
        print("\n" + "="*80)
        print("✅ PROCESAMIENTO COMPLETADO")
        print("="*80)
        print(f"   Total procesados: {self.stats['procesados']}")
        print(f"   📸 Imágenes: {self.stats['imagenes']}")
        print(f"   📄 Textos: {self.stats['textos']}")
        print(f"   ✅ Exitosos: {self.stats['exitosos']}")
        print(f"   ⚠️  No anuncios: {self.stats['no_anuncios']}")
        print(f"   ❌ Fallidos: {self.stats['fallidos']}")
        print(f"   Tiempo total: {tiempo_total:.2f}s")
        if self.stats['procesados'] > 0:
            print(f"   Tiempo promedio: {tiempo_total/self.stats['procesados']:.2f}s por archivo")
        print("="*80 + "\n")
    
    def _clean_for_json(self, obj):
        """Limpia un objeto para que sea serializable a JSON."""
        if obj is None:
            return None
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, dict):
            return {k: self._clean_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._clean_for_json(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            try:
                return str(obj)
            except:
                return None
    
    def _save_results(self):
        """Guarda los resultados en un archivo JSON."""
        if not self.auto_save_results:
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"resultados_multiformat_{timestamp}.json"
        filepath = os.path.join(self.output_folder, filename)
        
        data = {
            'fecha': datetime.now().isoformat(),
            'estadisticas': self._clean_for_json(self.stats),
            'resultados': self._clean_for_json(self.results)
        }
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"💾 Resultados guardados en: {filepath}")
        except Exception as e:
            print(f"❌ Error al guardar resultados: {str(e)}")
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False, default=str)
                print(f"💾 Resultados guardados (modo seguro) en: {filepath}")
            except Exception as e2:
                print(f"❌ No se pudieron guardar los resultados: {str(e2)}")
    
    def _read_text_file(self, file_path: str) -> str:
        """Lee el contenido de un archivo de texto."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Intentar con otra codificación
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except Exception as e:
                raise Exception(f"Error al leer archivo: {str(e)}")
    
    def _process_single_file(self, file_info: Dict) -> Dict[str, Any]:
        """
        Procesa un archivo individual (imagen o texto).
        
        Args:
            file_info: Diccionario con información del archivo
        
        Returns:
            Diccionario con el resultado del procesamiento
        """
        file_path = file_info['path']
        file_type = file_info['type']
        
        resultado = {
            'archivo': file_info['name'],
            'ruta': file_path,
            'tipo': file_type,
            'timestamp': datetime.now().isoformat(),
            'exito': False,
            'es_anuncio': False,
            'datos': None,
            'error': None
        }
        
        try:
            # Procesar según el tipo
            if file_type == 'image':
                datos = self.analyzer.process_job_image(
                    file_path,
                    quality=self.config['quality'],
                    upload_to_storage=self.config['upload_to_storage'],
                    upload_to_firestore=self.config['upload_to_firestore'],
                    timeout_ia=self.config['timeout_ia']
                )
            else:  # text
                text_content = self._read_text_file(file_path)
                datos = self.analyzer.process_job_text(
                    text_content,
                    upload_to_firestore=self.config['upload_to_firestore'],
                    timeout_ia=self.config['timeout_ia']
                )
            
            resultado['datos'] = datos
            resultado['exito'] = True
            resultado['es_anuncio'] = datos.get('es_anuncio_empleo', False)
            
            if resultado['es_anuncio']:
                self.stats['exitosos'] += 1
                print(f"   ✅ Anuncio detectado: {datos.get('position', 'N/A')}")
            else:
                self.stats['no_anuncios'] += 1
                print(f"   ⚠️  No es anuncio: {datos.get('razon', 'N/A')}")
                
        except Exception as e:
            resultado['error'] = str(e)
            self.stats['fallidos'] += 1
            print(f"   ❌ Error: {str(e)}")
        
        return resultado
    
    def process_queue(
        self,
        quality: int = 95,
        upload_to_storage: bool = True,
        upload_to_firestore: bool = True,
        timeout_ia: int = 30,
        pause_between: float = 0.5
    ):
        """
        Procesa todos los archivos en la cola.
        
        Args:
            quality: Calidad de conversión WebP para imágenes (0-100)
            upload_to_storage: Si True, sube imágenes a Firebase Storage
            upload_to_firestore: Si True, guarda datos en Firestore
            timeout_ia: Timeout para las llamadas a la IA en segundos
            pause_between: Segundos de pausa entre cada archivo
        """
        if self.is_processing:
            print("⚠️  Ya hay un procesamiento en curso")
            return
        
        if self.queue.empty():
            print("⚠️  La cola está vacía. Agrega archivos primero.")
            return
        
        self.is_processing = True
        tiempo_inicio = time.time()
        
        # Actualizar configuración
        self.config.update({
            'quality': quality,
            'upload_to_storage': upload_to_storage,
            'upload_to_firestore': upload_to_firestore,
            'timeout_ia': timeout_ia
        })
        
        self._print_banner()
        
        # Procesar cola
        while not self.queue.empty():
            # Verificar si está pausado
            while self.is_paused:
                time.sleep(0.5)
            
            file_info = self.queue.get()
            
            with self.lock:
                self.stats['en_cola'] -= 1
                self.stats['procesados'] += 1
            
            # Mostrar progreso
            self._print_progress(
                self.stats['procesados'],
                self.stats['total'],
                file_info
            )
            
            # Procesar archivo
            resultado = self._process_single_file(file_info)
            self.results.append(resultado)
            
            # Pausa entre archivos
            if pause_between > 0 and not self.queue.empty():
                time.sleep(pause_between)
        
        # Resumen final
        tiempo_total = time.time() - tiempo_inicio
        self._print_summary(tiempo_total)
        
        # Guardar resultados
        self._save_results()
        
        self.is_processing = False
    
    def pause(self):
        """Pausa el procesamiento."""
        self.is_paused = True
        print("⏸️  Procesamiento pausado")
    
    def resume(self):
        """Reanuda el procesamiento."""
        self.is_paused = False
        print("▶️  Procesamiento reanudado")
    
    def get_stats(self) -> Dict[str, int]:
        """Retorna las estadísticas actuales."""
        return self.stats.copy()
    
    def clear_queue(self):
        """Limpia la cola de procesamiento."""
        with self.lock:
            while not self.queue.empty():
                self.queue.get()
            self.stats = {
                'total': 0,
                'procesados': 0,
                'exitosos': 0,
                'fallidos': 0,
                'no_anuncios': 0,
                'en_cola': 0,
                'imagenes': 0,
                'textos': 0
            }
        print("🗑️  Cola limpiada")


# Función simplificada para uso rápido
def procesar_carpeta_completa(
    folder_path: str,
    recursive: bool = False,
    include_images: bool = True,
    include_texts: bool = True
):
    """
    Procesa una carpeta completa con imágenes y textos.
    
    Args:
        folder_path: Ruta de la carpeta
        recursive: Si True, incluye subcarpetas
        include_images: Si True, procesa imágenes
        include_texts: Si True, procesa archivos de texto
    """
    processor = BatchMultiFormatProcessor()
    
    # Cargar archivos
    processor.add_files_from_folder(
        folder_path,
        include_images=include_images,
        include_texts=include_texts,
        recursive=recursive
    )
    
    # Procesar
    processor.process_queue(
        quality=95,
        upload_to_storage=True,
        upload_to_firestore=True,
        timeout_ia=30,
        pause_between=1.0
    )
    
    return processor


# Ejemplo de uso
if __name__ == "__main__":
    print("\n" + "="*80)
    print("EJEMPLO 1: Procesar carpeta con imágenes y textos")
    print("="*80 + "\n")
    
    # Crear procesador
    processor = BatchMultiFormatProcessor()
    
    # Agregar todos los archivos de una carpeta
    processor.add_files_from_folder(
        "anuncios_empleo",
        include_images=True,
        include_texts=True,
        recursive=False  # True para incluir subcarpetas
    )
    
    # También puedes agregar archivos individuales durante el procesamiento
    # processor.add_file("mi_anuncio.txt", file_type='text')
    # processor.add_file("mi_imagen.jpg", file_type='image')
    
    # Iniciar procesamiento
    processor.process_queue(
        quality=95,
        upload_to_storage=True,
        upload_to_firestore=True,
        timeout_ia=30,
        pause_between=1.0
    )
    
    # Ver estadísticas finales
    print("\n📊 Estadísticas finales:")
    stats = processor.get_stats()
    print(json.dumps(stats, indent=2))
    
    print("\n" + "="*80)
    print("EJEMPLO 2: Uso simplificado con función helper")
    print("="*80 + "\n")
    
    # Forma más simple
    resultado = procesar_carpeta_completa(
        "anuncios_empleo",
        recursive=True,  # Incluir subcarpetas
        include_images=True,
        include_texts=True
    )