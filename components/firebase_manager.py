"""
Módulo para gestión de Firebase (Storage y Firestore).
Maneja la subida de imágenes y almacenamiento de datos.
"""

import firebase_admin
from firebase_admin import credentials, firestore, storage
from datetime import datetime
from typing import Optional, Dict, Any
from io import BytesIO
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


class FirebaseManager:
    """Gestor centralizado para operaciones de Firebase Storage y Firestore."""
    
    def __init__(self, service_account_path: str = 'serviceAccountKey.json'):
        """
        Inicializa la conexión con Firebase.
        
        Args:
            service_account_path: Ruta al archivo de credenciales de Firebase
        """
        storage_bucket = os.getenv('FIREBASE_STORAGE_BUCKET')
        
        if not storage_bucket:
            raise ValueError("❌ FIREBASE_STORAGE_BUCKET no encontrada en archivo .env")
        
        # Inicializar Firebase solo si no está inicializado
        if not firebase_admin._apps:
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred, {
                'storageBucket': storage_bucket
            })
        
        self.db = firestore.client()
        self.bucket = storage.bucket()
        
        print("✅ Firebase inicializado correctamente")
        print(f"   Storage Bucket: {storage_bucket}")
    
    def upload_image_to_storage(
        self,
        image_buffer: BytesIO,
        filename_prefix: str = "job",
        folder: str = "jobs",
        make_public: bool = True
    ) -> str:
        """
        Sube una imagen a Firebase Storage desde memoria.
        
        Args:
            image_buffer: BytesIO con la imagen
            filename_prefix: Prefijo para el nombre del archivo
            folder: Carpeta en Storage donde se guardará
            make_public: Si True, hace la imagen públicamente accesible
        
        Returns:
            URL pública de la imagen
        """
        # Generar nombre único con timestamp
        timestamp = int(datetime.now().timestamp() * 1000)
        filename = f"{filename_prefix}_{timestamp}.webp"
        blob_path = f"{folder}/{filename}"
        
        # Subir desde memoria
        blob = self.bucket.blob(blob_path)
        image_buffer.seek(0)
        blob.upload_from_file(image_buffer, content_type='image/webp')
        
        # Hacer público si se solicita
        if make_public:
            blob.make_public()
            public_url = blob.public_url
        else:
            public_url = f"gs://{self.bucket.name}/{blob_path}"
        
        print(f"✓ Imagen subida a Firebase Storage:")
        print(f"  Path: {blob_path}")
        print(f"  URL: {public_url}")
        
        return public_url
    
    def delete_image_from_storage(
        self,
        blob_path: str
    ) -> bool:
        """
        Elimina una imagen de Firebase Storage.
        
        Args:
            blob_path: Ruta del blob en Storage (ej: "jobs/job_123456.webp")
        
        Returns:
            True si se eliminó correctamente, False si hubo error
        """
        try:
            blob = self.bucket.blob(blob_path)
            blob.delete()
            print(f"✓ Imagen eliminada de Storage: {blob_path}")
            return True
        except Exception as e:
            print(f"❌ Error al eliminar imagen: {str(e)}")
            return False
    
    def upload_to_firestore(
        self,
        data: Dict[str, Any],
        collection: str = 'jobs',
        doc_id: Optional[str] = None,
        auto_timestamps: bool = True
    ) -> str:
        """
        Sube datos a Firestore.
        
        Args:
            data: Diccionario con los datos a guardar
            collection: Nombre de la colección
            doc_id: ID personalizado del documento (opcional)
            auto_timestamps: Si True, añade createdAt y updatedAt automáticamente
        
        Returns:
            ID del documento creado
        """
        # Añadir timestamps si se solicita
        if auto_timestamps:
            data['createdAt'] = firestore.SERVER_TIMESTAMP
            data['updatedAt'] = firestore.SERVER_TIMESTAMP
        
        # Generar ID automático si no se proporciona
        if doc_id is None:
            city = data.get('city', 'unknown').lower().replace(' ', '_')
            position = data.get('position', 'job').lower().replace(' ', '_')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            doc_id = f"{position}_{city}_{timestamp}"
        
        # Crear el documento
        doc_ref = self.db.collection(collection).document(doc_id)
        doc_ref.set(data)
        
        print(f"✓ Documento creado en Firestore:")
        print(f"  ID: {doc_id}")
        print(f"  Colección: {collection}")
        
        return doc_id
    
    def update_firestore_document(
        self,
        doc_id: str,
        data: Dict[str, Any],
        collection: str = 'jobs',
        merge: bool = True
    ) -> bool:
        """
        Actualiza un documento existente en Firestore.
        
        Args:
            doc_id: ID del documento a actualizar
            data: Diccionario con los datos a actualizar
            collection: Nombre de la colección
            merge: Si True, combina con datos existentes. Si False, sobrescribe
        
        Returns:
            True si se actualizó correctamente
        """
        try:
            data['updatedAt'] = firestore.SERVER_TIMESTAMP
            doc_ref = self.db.collection(collection).document(doc_id)
            
            if merge:
                doc_ref.set(data, merge=True)
            else:
                doc_ref.set(data)
            
            print(f"✓ Documento actualizado en Firestore:")
            print(f"  ID: {doc_id}")
            print(f"  Colección: {collection}")
            return True
        except Exception as e:
            print(f"❌ Error al actualizar documento: {str(e)}")
            return False
    
    def get_firestore_document(
        self,
        doc_id: str,
        collection: str = 'jobs'
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene un documento de Firestore.
        
        Args:
            doc_id: ID del documento
            collection: Nombre de la colección
        
        Returns:
            Diccionario con los datos del documento o None si no existe
        """
        try:
            doc_ref = self.db.collection(collection).document(doc_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            else:
                print(f"⚠️  Documento no encontrado: {doc_id}")
                return None
        except Exception as e:
            print(f"❌ Error al obtener documento: {str(e)}")
            return None
    
    def delete_firestore_document(
        self,
        doc_id: str,
        collection: str = 'jobs'
    ) -> bool:
        """
        Elimina un documento de Firestore.
        
        Args:
            doc_id: ID del documento a eliminar
            collection: Nombre de la colección
        
        Returns:
            True si se eliminó correctamente
        """
        try:
            doc_ref = self.db.collection(collection).document(doc_id)
            doc_ref.delete()
            print(f"✓ Documento eliminado de Firestore: {doc_id}")
            return True
        except Exception as e:
            print(f"❌ Error al eliminar documento: {str(e)}")
            return False
    
    def query_firestore(
        self,
        collection: str = 'jobs',
        filters: Optional[list] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None
    ) -> list:
        """
        Realiza una consulta en Firestore.
        
        Args:
            collection: Nombre de la colección
            filters: Lista de tuplas (campo, operador, valor)
                    Ej: [('city', '==', 'Asunción'), ('salary', '>', 1000)]
            order_by: Campo por el cual ordenar
            limit: Número máximo de resultados
        
        Returns:
            Lista de diccionarios con los documentos encontrados
        """
        try:
            query = self.db.collection(collection)
            
            # Aplicar filtros
            if filters:
                for field, operator, value in filters:
                    query = query.where(field, operator, value)
            
            # Aplicar ordenamiento
            if order_by:
                query = query.order_by(order_by)
            
            # Aplicar límite
            if limit:
                query = query.limit(limit)
            
            # Ejecutar consulta
            docs = query.stream()
            results = []
            
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                results.append(data)
            
            print(f"✓ Consulta ejecutada: {len(results)} documentos encontrados")
            return results
            
        except Exception as e:
            print(f"❌ Error en consulta: {str(e)}")
            return []


# Ejemplo de uso
if __name__ == "__main__":
    # Inicializar manager
    fb_manager = FirebaseManager()
    
    # Ejemplo: Subir imagen
    # with open("ejemplo.webp", "rb") as f:
    #     image_buffer = BytesIO(f.read())
    #     url = fb_manager.upload_image_to_storage(image_buffer)
    
    # Ejemplo: Guardar datos
    datos = {
        'position': 'Desarrollador Python',
        'city': 'Asunción',
        'company': 'Tech Corp',
        'salary_range': '3000-5000'
    }
    doc_id = fb_manager.upload_to_firestore(datos)
    
    # Ejemplo: Consultar datos
    resultados = fb_manager.query_firestore(
        filters=[('city', '==', 'Asunción')],
        limit=10
    )
    print(f"\n📊 Resultados encontrados: {len(resultados)}")