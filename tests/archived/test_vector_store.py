"""
Comprehensive unit tests for Vector Store module.
Tests include edge cases, missing values, anomalies, and FAISS operations.
"""

import pytest
import numpy as np
import os
import json
import pickle
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path

from src.vector_store import VectorStore, build_vector_store_from_chunks


@pytest.fixture
def temp_index_path():
    """Create temporary directory for index storage."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def sample_documents():
    """Provide sample documents for testing."""
    return [
        {"text": "Apple Inc. is a technology company.", "source": "wiki", "id": "1"},
        {"text": "Microsoft develops software products.", "source": "wiki", "id": "2"},
        {"text": "Google is a search engine company.", "source": "wiki", "id": "3"},
    ]


@pytest.fixture
def mock_sentence_transformer():
    """Mock SentenceTransformer for testing without dependencies."""
    mock_model = Mock()
    mock_model.encode = Mock(return_value=np.random.rand(3, 384).astype('float32'))
    return mock_model


@pytest.fixture
def mock_faiss_index():
    """Mock FAISS index for testing."""
    mock_index = Mock()
    mock_index.d = 384  # dimension
    mock_index.ntotal = 0  # number of vectors
    mock_index.add = Mock()
    mock_index.search = Mock(return_value=(np.array([[0.1, 0.2, 0.3]]), np.array([[0, 1, 2]])))
    return mock_index


class TestVectorStoreInitialization:
    """Test VectorStore initialization."""

    def test_init_default_parameters(self, temp_index_path):
        """Test initialization with default parameters."""
        store = VectorStore(index_path=temp_index_path)
        assert store.index_path == temp_index_path
        assert store.embedding_model_name == "sentence-transformers/all-MiniLM-L6-v2"
        assert store.index is None
        assert store.documents == []
        assert store.embeddings_model is None

    def test_init_custom_parameters(self, temp_index_path):
        """Test initialization with custom parameters."""
        custom_model = "sentence-transformers/paraphrase-MiniLM-L6-v2"
        store = VectorStore(index_path=temp_index_path, embedding_model=custom_model)
        assert store.embedding_model_name == custom_model

    def test_init_creates_directory(self, temp_index_path):
        """Test that initialization creates index directory."""
        new_path = os.path.join(temp_index_path, "new_index")
        store = VectorStore(index_path=new_path)
        assert os.path.exists(new_path)

    def test_init_multiple_instances(self, temp_index_path):
        """Test multiple independent instances."""
        store1 = VectorStore(index_path=os.path.join(temp_index_path, "store1"))
        store2 = VectorStore(index_path=os.path.join(temp_index_path, "store2"))
        assert store1 is not store2
        assert store1.index_path != store2.index_path


@pytest.mark.unit
class TestModelInitialization:
    """Test embedding model initialization."""

    @patch('src.vector_store.SentenceTransformer')
    def test_initialize_model_success(self, mock_st, temp_index_path):
        """Test successful model initialization."""
        mock_model = Mock()
        mock_st.return_value = mock_model

        store = VectorStore(index_path=temp_index_path)
        store.initialize_model()

        assert store.embeddings_model is not None
        mock_st.assert_called_once_with(store.embedding_model_name)

    def test_initialize_model_import_error(self, temp_index_path):
        """Test handling of missing sentence-transformers package."""
        store = VectorStore(index_path=temp_index_path)

        with patch.dict('sys.modules', {'sentence_transformers': None}):
            with pytest.raises(ImportError):
                store.initialize_model()

    @patch('src.vector_store.SentenceTransformer')
    def test_initialize_model_twice(self, mock_st, temp_index_path):
        """Test initializing model multiple times."""
        mock_model = Mock()
        mock_st.return_value = mock_model

        store = VectorStore(index_path=temp_index_path)
        store.initialize_model()
        first_model = store.embeddings_model

        store.initialize_model()
        second_model = store.embeddings_model

        # Should create new model each time
        assert second_model is not None


@pytest.mark.unit
class TestIndexCreation:
    """Test FAISS index creation."""

    @patch('src.vector_store.faiss')
    def test_create_index_default_dimension(self, mock_faiss, temp_index_path):
        """Test index creation with default dimension."""
        mock_index = Mock()
        mock_faiss.IndexFlatL2.return_value = mock_index

        store = VectorStore(index_path=temp_index_path)
        store.create_index()

        mock_faiss.IndexFlatL2.assert_called_once_with(384)
        assert store.index is not None

    @patch('src.vector_store.faiss')
    def test_create_index_custom_dimension(self, mock_faiss, temp_index_path):
        """Test index creation with custom dimension."""
        mock_index = Mock()
        mock_faiss.IndexFlatL2.return_value = mock_index

        store = VectorStore(index_path=temp_index_path)
        store.create_index(dimension=768)

        mock_faiss.IndexFlatL2.assert_called_once_with(768)

    def test_create_index_faiss_not_installed(self, temp_index_path):
        """Test handling of missing faiss package."""
        store = VectorStore(index_path=temp_index_path)

        with patch.dict('sys.modules', {'faiss': None}):
            with pytest.raises(ImportError):
                store.create_index()

    @patch('src.vector_store.faiss')
    def test_create_index_zero_dimension(self, mock_faiss, temp_index_path):
        """Test index creation with zero dimension (edge case)."""
        store = VectorStore(index_path=temp_index_path)

        # FAISS should raise error for zero dimension
        mock_faiss.IndexFlatL2.side_effect = RuntimeError("Invalid dimension")

        with pytest.raises(RuntimeError):
            store.create_index(dimension=0)


@pytest.mark.data_quality
class TestAddDocumentsEdgeCases:
    """Test add_documents with edge cases."""

    @patch('src.vector_store.faiss')
    @patch('src.vector_store.SentenceTransformer')
    def test_add_empty_documents(self, mock_st, mock_faiss, temp_index_path):
        """Test adding empty document list."""
        mock_model = Mock()
        mock_model.encode = Mock(return_value=np.array([]).reshape(0, 384).astype('float32'))
        mock_st.return_value = mock_model

        mock_index = Mock()
        mock_index.ntotal = 0
        mock_faiss.IndexFlatL2.return_value = mock_index

        store = VectorStore(index_path=temp_index_path)
        store.add_documents([])

        assert len(store.documents) == 0

    @patch('src.vector_store.faiss')
    @patch('src.vector_store.SentenceTransformer')
    def test_add_documents_missing_text_field(self, mock_st, mock_faiss, temp_index_path, sample_documents):
        """Test adding documents without 'text' field."""
        mock_model = Mock()
        mock_model.encode = Mock(return_value=np.random.rand(2, 384).astype('float32'))
        mock_st.return_value = mock_model

        mock_index = Mock()
        mock_index.ntotal = 2
        mock_faiss.IndexFlatL2.return_value = mock_index

        store = VectorStore(index_path=temp_index_path)
        docs = [
            {"source": "wiki", "id": "1"},  # Missing 'text' field
            {"source": "news", "id": "2"},
        ]
        store.add_documents(docs)

        # Should handle missing text gracefully (empty string)
        assert len(store.documents) == 2

    @patch('src.vector_store.faiss')
    @patch('src.vector_store.SentenceTransformer')
    def test_add_documents_empty_text(self, mock_st, mock_faiss, temp_index_path):
        """Test adding documents with empty text."""
        mock_model = Mock()
        mock_model.encode = Mock(return_value=np.random.rand(1, 384).astype('float32'))
        mock_st.return_value = mock_model

        mock_index = Mock()
        mock_index.ntotal = 1
        mock_faiss.IndexFlatL2.return_value = mock_index

        store = VectorStore(index_path=temp_index_path)
        store.add_documents([{"text": "", "id": "1"}])

        assert len(store.documents) == 1

    @patch('src.vector_store.faiss')
    @patch('src.vector_store.SentenceTransformer')
    def test_add_documents_very_long_text(self, mock_st, mock_faiss, temp_index_path):
        """Test adding documents with very long text."""
        mock_model = Mock()
        mock_model.encode = Mock(return_value=np.random.rand(1, 384).astype('float32'))
        mock_st.return_value = mock_model

        mock_index = Mock()
        mock_faiss.IndexFlatL2.return_value = mock_index

        store = VectorStore(index_path=temp_index_path)
        long_text = "word " * 10000  # Very long text
        store.add_documents([{"text": long_text, "id": "1"}])

        assert len(store.documents) == 1

    @patch('src.vector_store.faiss')
    @patch('src.vector_store.SentenceTransformer')
    def test_add_documents_special_characters(self, mock_st, mock_faiss, temp_index_path):
        """Test adding documents with special characters."""
        mock_model = Mock()
        mock_model.encode = Mock(return_value=np.random.rand(1, 384).astype('float32'))
        mock_st.return_value = mock_model

        mock_index = Mock()
        mock_faiss.IndexFlatL2.return_value = mock_index

        store = VectorStore(index_path=temp_index_path)
        special_text = "Test with 日本語, émojis 🎉, and symbols @#$%"
        store.add_documents([{"text": special_text, "id": "1"}])

        assert len(store.documents) == 1

    @patch('src.vector_store.faiss')
    @patch('src.vector_store.SentenceTransformer')
    def test_add_documents_multiple_batches(self, mock_st, mock_faiss, temp_index_path):
        """Test adding documents in multiple batches."""
        mock_model = Mock()
        mock_model.encode = Mock(return_value=np.random.rand(2, 384).astype('float32'))
        mock_st.return_value = mock_model

        mock_index = Mock()
        mock_index.ntotal = 4
        mock_faiss.IndexFlatL2.return_value = mock_index

        store = VectorStore(index_path=temp_index_path)
        store.add_documents([{"text": "doc1"}, {"text": "doc2"}])
        store.add_documents([{"text": "doc3"}, {"text": "doc4"}])

        assert len(store.documents) == 4


@pytest.mark.unit
class TestSearchFunctionality:
    """Test search functionality with edge cases."""

    @patch('src.vector_store.faiss')
    @patch('src.vector_store.SentenceTransformer')
    def test_search_empty_store(self, mock_st, mock_faiss, temp_index_path):
        """Test searching in empty vector store."""
        mock_model = Mock()
        mock_model.encode = Mock(return_value=np.random.rand(1, 384).astype('float32'))
        mock_st.return_value = mock_model

        mock_index = Mock()
        mock_index.ntotal = 0
        mock_faiss.IndexFlatL2.return_value = mock_index

        store = VectorStore(index_path=temp_index_path)
        store.initialize_model()
        store.create_index()

        results = store.search("test query")
        assert results == []

    @patch('src.vector_store.faiss')
    @patch('src.vector_store.SentenceTransformer')
    def test_search_no_index(self, mock_st, mock_faiss, temp_index_path):
        """Test searching without creating index."""
        mock_model = Mock()
        mock_model.encode = Mock(return_value=np.random.rand(1, 384).astype('float32'))
        mock_st.return_value = mock_model

        store = VectorStore(index_path=temp_index_path)
        store.initialize_model()
        # Don't create index

        results = store.search("test query")
        assert results == []

    @patch('src.vector_store.faiss')
    @patch('src.vector_store.SentenceTransformer')
    def test_search_empty_query(self, mock_st, mock_faiss, temp_index_path):
        """Test searching with empty query string."""
        mock_model = Mock()
        mock_model.encode = Mock(side_effect=[
            np.random.rand(1, 384).astype('float32'),  # For add
            np.random.rand(1, 384).astype('float32'),  # For search
        ])
        mock_st.return_value = mock_model

        mock_index = Mock()
        mock_index.ntotal = 1
        mock_index.search = Mock(return_value=(np.array([[0.1]]), np.array([[0]])))
        mock_faiss.IndexFlatL2.return_value = mock_index

        store = VectorStore(index_path=temp_index_path)
        store.add_documents([{"text": "test doc"}])

        results = store.search("")
        # Should handle empty query gracefully
        assert isinstance(results, list)

    @patch('src.vector_store.faiss')
    @patch('src.vector_store.SentenceTransformer')
    def test_search_top_k_exceeds_documents(self, mock_st, mock_faiss, temp_index_path):
        """Test search with top_k larger than number of documents."""
        mock_model = Mock()
        mock_model.encode = Mock(side_effect=[
            np.random.rand(2, 384).astype('float32'),  # For add
            np.random.rand(1, 384).astype('float32'),  # For search
        ])
        mock_st.return_value = mock_model

        mock_index = Mock()
        mock_index.ntotal = 2
        mock_index.search = Mock(return_value=(np.array([[0.1, 0.2]]), np.array([[0, 1]])))
        mock_faiss.IndexFlatL2.return_value = mock_index

        store = VectorStore(index_path=temp_index_path)
        store.add_documents([{"text": "doc1"}, {"text": "doc2"}])

        results = store.search("query", top_k=100)
        # Should return only available documents
        assert len(results) <= 2

    @patch('src.vector_store.faiss')
    @patch('src.vector_store.SentenceTransformer')
    def test_search_top_k_zero(self, mock_st, mock_faiss, temp_index_path):
        """Test search with top_k=0."""
        mock_model = Mock()
        mock_model.encode = Mock(side_effect=[
            np.random.rand(1, 384).astype('float32'),  # For add
            np.random.rand(1, 384).astype('float32'),  # For search
        ])
        mock_st.return_value = mock_model

        mock_index = Mock()
        mock_index.ntotal = 1
        mock_index.search = Mock(return_value=(np.array([[]]), np.array([[]])))
        mock_faiss.IndexFlatL2.return_value = mock_index

        store = VectorStore(index_path=temp_index_path)
        store.add_documents([{"text": "test"}])

        results = store.search("query", top_k=0)
        assert len(results) == 0


@pytest.mark.unit
class TestSaveLoad:
    """Test save and load functionality."""

    @patch('src.vector_store.faiss')
    def test_save_success(self, mock_faiss, temp_index_path):
        """Test successful save operation."""
        mock_index = Mock()
        mock_index.d = 384
        mock_faiss.write_index = Mock()

        store = VectorStore(index_path=temp_index_path)
        store.index = mock_index
        store.documents = [{"text": "test"}]
        store.embedding_model_name = "test-model"

        with patch("builtins.open", mock_open()):
            with patch("pickle.dump"):
                store.save()

        mock_faiss.write_index.assert_called_once()

    @patch('src.vector_store.faiss')
    def test_save_no_index(self, mock_faiss, temp_index_path):
        """Test save with no index created."""
        store = VectorStore(index_path=temp_index_path)
        store.index = None

        with pytest.raises(AttributeError):
            store.save()

    @patch('src.vector_store.faiss')
    def test_load_success(self, mock_faiss, temp_index_path):
        """Test successful load operation."""
        mock_index = Mock()
        mock_index.d = 384
        mock_faiss.read_index.return_value = mock_index

        # Create mock files
        os.makedirs(temp_index_path, exist_ok=True)
        Path(os.path.join(temp_index_path, "faiss.index")).touch()

        mock_documents = [{"text": "test"}]
        mock_metadata = {"total_documents": 1, "dimension": 384, "embedding_model": "test", "last_updated": "2023-10-15"}

        with patch("builtins.open", mock_open()):
            with patch("pickle.load", return_value=mock_documents):
                with patch("json.load", return_value=mock_metadata):
                    store = VectorStore(index_path=temp_index_path)
                    result = store.load()

        assert result is True
        assert len(store.documents) > 0

    def test_load_missing_files(self, temp_index_path):
        """Test load with missing index files."""
        store = VectorStore(index_path=temp_index_path)
        result = store.load()
        assert result is False

    @patch('src.vector_store.faiss')
    def test_load_corrupted_index(self, mock_faiss, temp_index_path):
        """Test load with corrupted index file."""
        mock_faiss.read_index.side_effect = Exception("Corrupted index")

        # Create dummy file
        os.makedirs(temp_index_path, exist_ok=True)
        Path(os.path.join(temp_index_path, "faiss.index")).touch()

        store = VectorStore(index_path=temp_index_path)
        result = store.load()
        assert result is False


@pytest.mark.unit
class TestGetStats:
    """Test statistics retrieval."""

    @patch('src.vector_store.faiss')
    def test_get_stats_empty_store(self, mock_faiss, temp_index_path):
        """Test statistics for empty store."""
        store = VectorStore(index_path=temp_index_path)
        stats = store.get_stats()

        assert stats['total_documents'] == 0
        assert stats['total_vectors'] == 0
        assert 'embedding_model' in stats

    @patch('src.vector_store.faiss')
    @patch('src.vector_store.SentenceTransformer')
    def test_get_stats_with_documents(self, mock_st, mock_faiss, temp_index_path):
        """Test statistics after adding documents."""
        mock_model = Mock()
        mock_model.encode = Mock(return_value=np.random.rand(3, 384).astype('float32'))
        mock_st.return_value = mock_model

        mock_index = Mock()
        mock_index.d = 384
        mock_index.ntotal = 3
        mock_faiss.IndexFlatL2.return_value = mock_index

        store = VectorStore(index_path=temp_index_path)
        store.add_documents([{"text": "1"}, {"text": "2"}, {"text": "3"}])

        stats = store.get_stats()
        assert stats['total_documents'] == 3
        assert stats['total_vectors'] == 3
        assert stats['index_dimension'] == 384


@pytest.mark.integration
class TestBuildVectorStoreFromChunks:
    """Test the build_vector_store_from_chunks utility function."""

    @patch('src.vector_store.VectorStore.save')
    @patch('src.vector_store.faiss')
    @patch('src.vector_store.SentenceTransformer')
    def test_build_from_chunks_success(self, mock_st, mock_faiss, mock_save, temp_index_path, sample_documents):
        """Test successful build from chunks."""
        mock_model = Mock()
        mock_model.encode = Mock(return_value=np.random.rand(3, 384).astype('float32'))
        mock_st.return_value = mock_model

        mock_index = Mock()
        mock_index.d = 384
        mock_index.ntotal = 3
        mock_faiss.IndexFlatL2.return_value = mock_index

        store = build_vector_store_from_chunks(sample_documents, index_path=temp_index_path)

        assert store is not None
        assert len(store.documents) == 3
        mock_save.assert_called_once()

    @patch('src.vector_store.faiss')
    @patch('src.vector_store.SentenceTransformer')
    def test_build_from_empty_chunks(self, mock_st, mock_faiss, temp_index_path):
        """Test building from empty chunk list."""
        mock_model = Mock()
        mock_model.encode = Mock(return_value=np.array([]).reshape(0, 384).astype('float32'))
        mock_st.return_value = mock_model

        mock_index = Mock()
        mock_index.d = 384
        mock_index.ntotal = 0
        mock_faiss.IndexFlatL2.return_value = mock_index

        with patch('src.vector_store.VectorStore.save'):
            store = build_vector_store_from_chunks([], index_path=temp_index_path)

        assert len(store.documents) == 0


@pytest.mark.edge_case
class TestEdgeCasesAndErrors:
    """Test various edge cases and error conditions."""

    @patch('src.vector_store.faiss')
    @patch('src.vector_store.SentenceTransformer')
    def test_add_documents_encoding_failure(self, mock_st, mock_faiss, temp_index_path):
        """Test handling of encoding failure."""
        mock_model = Mock()
        mock_model.encode = Mock(side_effect=Exception("Encoding failed"))
        mock_st.return_value = mock_model

        mock_index = Mock()
        mock_faiss.IndexFlatL2.return_value = mock_index

        store = VectorStore(index_path=temp_index_path)

        with pytest.raises(Exception):
            store.add_documents([{"text": "test"}])

    @patch('src.vector_store.faiss')
    @patch('src.vector_store.SentenceTransformer')
    def test_search_with_nan_embeddings(self, mock_st, mock_faiss, temp_index_path):
        """Test search handling NaN embeddings."""
        mock_model = Mock()
        mock_model.encode = Mock(return_value=np.array([[np.nan] * 384]))
        mock_st.return_value = mock_model

        mock_index = Mock()
        mock_index.ntotal = 1
        mock_index.search = Mock(side_effect=Exception("Invalid input"))
        mock_faiss.IndexFlatL2.return_value = mock_index

        store = VectorStore(index_path=temp_index_path)
        store.initialize_model()
        store.create_index()

        with pytest.raises(Exception):
            store.search("test query")

    def test_init_with_invalid_path_characters(self):
        """Test initialization with invalid path characters."""
        # On Windows, certain characters are invalid
        if os.name == 'nt':
            with pytest.raises(OSError):
                VectorStore(index_path="C:\\invalid<>path")
