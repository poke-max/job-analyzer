"""
Módulo para conversión de imágenes a formato WebP.
Realiza todas las operaciones en memoria sin guardar archivos locales.
"""

from PIL import Image
from typing import Union
from io import BytesIO
import os


class ImageConverter:
    """Conversor de imágenes a formato WebP optimizado."""
    
    @staticmethod
    def convert_to_webp(
        image_data: Union[str, bytes, BytesIO],
        quality: int = 95,
        verbose: bool = True
    ) -> BytesIO:
        """
        Convierte una imagen a formato WebP en memoria (sin guardar archivo).
        
        Args:
            image_data: Ruta del archivo, bytes o BytesIO de la imagen
            quality: Calidad de conversión (0-100)
            verbose: Si True, muestra información del proceso
        
        Returns:
            BytesIO con la imagen WebP
        """
        # Cargar imagen según el tipo de entrada
        if isinstance(image_data, str):
            with open(image_data, 'rb') as f:
                img = Image.open(f)
                img.load()  # Cargar completamente antes de cerrar el archivo
            original_size = os.path.getsize(image_data)
        elif isinstance(image_data, bytes):
            img = Image.open(BytesIO(image_data))
            original_size = len(image_data)
        else:
            img = Image.open(image_data)
            image_data.seek(0)
            original_size = len(image_data.getvalue())
        
        # Convertir modo de color si es necesario
        if img.mode in ('RGBA', 'LA', 'P'):
            if img.mode == 'P':
                img = img.convert('RGBA')
        elif img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGB')
        
        # Guardar en memoria
        output = BytesIO()
        img.save(
            output, 
            format='WEBP', 
            quality=quality, 
            method=6, 
            lossless=False
        )
        output.seek(0)
        
        # Mostrar estadísticas si verbose está activado
        if verbose:
            compressed_size = len(output.getvalue())
            compression_ratio = (1 - compressed_size / original_size) * 100
            
            print(f"✓ Imagen convertida a WebP en memoria:")
            print(f"  Original: {original_size / 1024:.2f} KB → WebP: {compressed_size / 1024:.2f} KB")
            print(f"  Reducción: {compression_ratio:.2f}%")
        
        return output
    
    @staticmethod
    def get_image_info(image_data: Union[str, bytes, BytesIO]) -> dict:
        """
        Obtiene información sobre una imagen sin convertirla.
        
        Args:
            image_data: Ruta del archivo, bytes o BytesIO de la imagen
        
        Returns:
            Diccionario con información de la imagen
        """
        if isinstance(image_data, str):
            with open(image_data, 'rb') as f:
                img = Image.open(f)
                img.load()
        elif isinstance(image_data, bytes):
            img = Image.open(BytesIO(image_data))
        else:
            img = Image.open(image_data)
        
        return {
            'format': img.format,
            'mode': img.mode,
            'size': img.size,
            'width': img.width,
            'height': img.height
        }


# Ejemplo de uso
if __name__ == "__main__":
    converter = ImageConverter()
    
    # Convertir una imagen
    webp_buffer = converter.convert_to_webp("ejemplo.jpg", quality=90)
    
    # Obtener información de la imagen
    info = converter.get_image_info("ejemplo.jpg")
    print(f"\n📊 Información de la imagen:")
    print(f"   Formato: {info['format']}")
    print(f"   Dimensiones: {info['width']}x{info['height']}")
    print(f"   Modo de color: {info['mode']}")