from unittest.mock import MagicMock, patch
from uuid import uuid4
import pytest
from app.infrastructure.repositories.qdrant_supplier_repository import QdrantSupplierRepository

# Fixture para instanciar el cliente mockeado de Qdrant
@pytest.fixture
def client() -> MagicMock:
    return MagicMock()

# Fixture para instanciar el repositorio bajo prueba inyectando el cliente mock
@pytest.fixture
def repository(client: MagicMock) -> QdrantSupplierRepository:
    return QdrantSupplierRepository(client)

def test_upsert_stores_supplier_id_in_payload(repository: QdrantSupplierRepository, client: MagicMock) -> None:
    # Verifica que el método upsert construya el PointStruct correctamente
    # e incluya el supplier_id en el payload de Qdrant.
    supplier_id = uuid4()
    embedding = [0.1] * 1024
    
    _svc = "app.infrastructure.repositories.qdrant_supplier_repository"
    with patch(f"{_svc}.PointStruct") as mock_ps:
        mock_ps.return_value = MagicMock()
        repository.upsert(supplier_id, embedding)
        
    client.upsert.assert_called_once()
    call_kwargs = client.upsert.call_args.kwargs
    assert call_kwargs["collection_name"] == "suppliers"
    
    # Valida los parámetros pasados al constructor de PointStruct
    mock_ps.assert_called_once_with(
        id=str(supplier_id),
        vector=embedding,
        payload={"supplier_id": str(supplier_id)}
    )

def test_delete_calls_client_delete(repository: QdrantSupplierRepository, client: MagicMock) -> None:
    # Verifica que el método delete llame a client.delete con la lista de IDs del punto a borrar.
    supplier_id = uuid4()
    
    _svc = "app.infrastructure.repositories.qdrant_supplier_repository"
    with patch(f"{_svc}.PointIdsList") as mock_pil:
        mock_pil.return_value = MagicMock()
        repository.delete(supplier_id)
        
    client.delete.assert_called_once()
    call_kwargs = client.delete.call_args.kwargs
    assert call_kwargs["collection_name"] == "suppliers"
    # Valida que PointIdsList se cree con la lista correcta de UUIDs formateados a string
    mock_pil.assert_called_once_with(points=[str(supplier_id)])

def test_get_vector_returns_embedding_when_found(repository: QdrantSupplierRepository, client: MagicMock) -> None:
    # Verifica que get_vector obtenga correctamente el vector desde Qdrant cuando existe el punto.
    supplier_id = uuid4()
    mock_record = MagicMock()
    mock_record.vector = [0.2] * 1024
    client.retrieve.return_value = [mock_record]
    
    vector = repository.get_vector(supplier_id)
    
    # Valida que se busque en la colección correcta usando el ID correcto y solicitando el vector
    client.retrieve.assert_called_once_with(
        collection_name="suppliers",
        ids=[str(supplier_id)],
        with_vectors=True
    )
    assert vector == [0.2] * 1024

def test_get_vector_returns_none_when_not_found(repository: QdrantSupplierRepository, client: MagicMock) -> None:
    # Verifica que get_vector retorne None si el proveedor no existe en Qdrant.
    supplier_id = uuid4()
    client.retrieve.return_value = []
    
    vector = repository.get_vector(supplier_id)
    
    assert vector is None
