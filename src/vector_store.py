"""
Vector Store Module
FAISS-based vector storage for document embeddings and similarity search
"""

import os
import json
import logging
import pickle
from typing import List, Dict, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class VectorStore:
    """FAISS vector store for document embeddings"""

    def __init__(self, index_path: str = "data/vector_store", embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.index_path = index_path
        self.embedding_model_name = embedding_model
        self.index = None
        self.documents = []
        self.embeddings_model = None

        # Create directory
        os.makedirs(index_path, exist_ok=True)

    def initialize_model(self):
        """Initialize embedding model"""
        try:
            from sentence_transformers import SentenceTransformer
            self.embeddings_model = SentenceTransformer(self.embedding_model_name)
            logger.info(f"Initialized embedding model: {self.embedding_model_name}")
        except ImportError:
            logger.error("sentence-transformers not installed. Install with: pip install sentence-transformers")
            raise

    def create_index(self, dimension: int = 384):
        """Create FAISS index"""
        try:
            import faiss
            self.index = faiss.IndexFlatL2(dimension)
            logger.info(f"Created FAISS index with dimension {dimension}")
        except ImportError:
            logger.error("faiss not installed. Install with: pip install faiss-cpu")
            raise

    def add_documents(self, documents: List[Dict]):
        """Add documents to vector store"""
        if not self.embeddings_model:
            self.initialize_model()

        if not self.index:
            self.create_index()

        logger.info(f"Adding {len(documents)} documents to vector store...")

        # Extract text from documents
        texts = [doc.get('text', '') for doc in documents]

        # Generate embeddings
        embeddings = self.embeddings_model.encode(texts, show_progress_bar=True)

        # Add to FAISS index
        self.index.add(np.array(embeddings).astype('float32'))

        # Store document metadata
        self.documents.extend(documents)

        logger.info(f"Added {len(documents)} documents to vector store")

    def search(self, query: str, top_k: int = 5) -> List[Tuple[Dict, float]]:
        """Search for similar documents"""
        if not self.embeddings_model:
            self.initialize_model()

        if not self.index or self.index.ntotal == 0:
            logger.warning("Vector store is empty")
            return []

        # Generate query embedding
        query_embedding = self.embeddings_model.encode([query])

        # Search FAISS index
        distances, indices = self.index.search(
            np.array(query_embedding).astype('float32'),
            min(top_k, self.index.ntotal)
        )

        # Retrieve documents
        results = []
        for idx, dist in zip(indices[0], distances[0]):
            if idx < len(self.documents):
                results.append((self.documents[idx], float(dist)))

        logger.info(f"Found {len(results)} results for query")
        return results

    def save(self):
        """Save index and documents to disk"""
        try:
            import faiss

            # Save FAISS index
            index_file = os.path.join(self.index_path, "faiss.index")
            faiss.write_index(self.index, index_file)

            # Save documents
            docs_file = os.path.join(self.index_path, "documents.pkl")
            with open(docs_file, 'wb') as f:
                pickle.dump(self.documents, f)

            # Save metadata
            metadata_file = os.path.join(self.index_path, "metadata.json")
            metadata = {
                'total_documents': len(self.documents),
                'embedding_model': self.embedding_model_name,
                'dimension': self.index.d,
                'last_updated': str(np.datetime64('now'))
            }
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Saved vector store to {self.index_path}")

        except Exception as e:
            logger.error(f"Failed to save vector store: {e}")
            raise

    def load(self):
        """Load index and documents from disk"""
        try:
            import faiss

            # Load FAISS index
            index_file = os.path.join(self.index_path, "faiss.index")
            if not os.path.exists(index_file):
                logger.warning(f"Index file not found: {index_file}")
                return False

            self.index = faiss.read_index(index_file)

            # Load documents
            docs_file = os.path.join(self.index_path, "documents.pkl")
            with open(docs_file, 'rb') as f:
                self.documents = pickle.load(f)

            # Load metadata
            metadata_file = os.path.join(self.index_path, "metadata.json")
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)

            logger.info(f"Loaded vector store from {self.index_path}")
            logger.info(f"  Documents: {metadata['total_documents']}")
            logger.info(f"  Dimension: {metadata['dimension']}")
            logger.info(f"  Last updated: {metadata['last_updated']}")

            return True

        except Exception as e:
            logger.error(f"Failed to load vector store: {e}")
            return False

    def get_stats(self) -> Dict:
        """Get vector store statistics"""
        return {
            'total_documents': len(self.documents),
            'total_vectors': self.index.ntotal if self.index else 0,
            'embedding_model': self.embedding_model_name,
            'index_dimension': self.index.d if self.index else 0
        }


def build_vector_store_from_chunks(chunks: List[Dict], index_path: str = "data/vector_store") -> VectorStore:
    """Build vector store from document chunks"""
    logger.info(f"Building vector store from {len(chunks)} chunks...")

    store = VectorStore(index_path=index_path)
    store.initialize_model()
    store.create_index()
    store.add_documents(chunks)
    store.save()

    logger.info("Vector store built successfully")
    return store


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example documents
    documents = [
        {
            'text': 'Apple Inc. is a technology company that designs and manufactures consumer electronics.',
            'source': 'wikipedia',
            'chunk_id': 'chunk_0'
        },
        {
            'text': 'The iPhone is Apple most successful product with billions in revenue.',
            'source': 'wikipedia',
            'chunk_id': 'chunk_1'
        },
        {
            'text': 'Apple reported strong quarterly earnings with revenue growth in all segments.',
            'source': 'news',
            'chunk_id': 'chunk_2'
        }
    ]

    # Create vector store
    store = VectorStore()
    store.initialize_model()
    store.create_index()
    store.add_documents(documents)

    # Search
    results = store.search("What are Apple's products?", top_k=2)
    print("\nSearch Results:")
    for doc, distance in results:
        print(f"  Distance: {distance:.4f}")
        print(f"  Text: {doc['text'][:80]}...")
        print(f"  Source: {doc['source']}")
        print()

    # Save
    store.save()

    # Load
    new_store = VectorStore()
    new_store.load()
    print(f"\nLoaded store stats: {new_store.get_stats()}")
