# researcher_agent/src/embeddings_manager.py
from typing import List, Dict, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from qdrant_client.http import models

from utils.config import config


class EmbeddingsManager:
    """Handles embedding generation and vector database operations"""
    
    def __init__(self):
        # Initialize embedding model
        print(f"Loading embedding model: {config.EMBEDDING_MODEL}")
        self.embedding_model = SentenceTransformer(config.EMBEDDING_MODEL)
        
        # Initialize Qdrant client
        self.qdrant_client = QdrantClient(
            host=config.QDRANT_HOST,
            port=config.QDRANT_PORT
        )
        
        self.collection_name = config.QDRANT_COLLECTION
        self._ensure_collection_exists()
    
    def _ensure_collection_exists(self):
        """Create collection if it doesn't exist"""
        try:
            self.qdrant_client.get_collection(self.collection_name)
            print(f"✓ Collection '{self.collection_name}' exists")
        except Exception:
            # Collection doesn't exist, create it
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=config.EMBEDDING_DIMENSION,
                    distance=Distance.COSINE
                )
            )
            print(f"✓ Created collection: {self.collection_name}")
    
    def generate_embeddings(
        self, 
        chunks: List[Dict],
        show_progress: bool = True
    ) -> List[Dict]:
        """
        Generate embeddings for all chunks
        
        Args:
            chunks: List of chunk dictionaries with 'embedding_text' field
            show_progress: Whether to show progress bar
            
        Returns:
            Chunks with added 'embedding' field
        """
        # Extract texts to embed
        texts_to_embed = [chunk['embedding_text'] for chunk in chunks]
        
        print(f"Generating embeddings for {len(texts_to_embed)} chunks...")
        
        # Generate embeddings in batch
        embeddings = self.embedding_model.encode(
            texts_to_embed,
            show_progress_bar=show_progress,
            batch_size=32,
            normalize_embeddings=True  # Normalize for cosine similarity
        )
        
        # Add embeddings to chunks
        for chunk, embedding in zip(chunks, embeddings):
            chunk['embedding'] = embedding.tolist()
        
        print(f"✓ Generated {len(embeddings)} embeddings")
        
        return chunks
    
    def create_chunks_with_embeddings(
        self,
        components: List[Dict],
        processed_tables: List[Dict],
        section_name: str,
        filing_metadata: Dict
    ) -> List[Dict]:
        """
        Create final chunks with embeddings for both tables and text
    
        Args:
            components: List of document components
            processed_tables: List of processed tables with summaries
            section_name: Name of the section being processed
            filing_metadata: Metadata about the filing
            
        Returns:
            List of chunks with embeddings
        """
        from researcher_agent.src.document_processor import DocumentProcessor
        
        processor = DocumentProcessor()
        chunks = []
        table_lookup = {t['component_index']: t for t in processed_tables}
        
        # Create chunks from components
        for i, component in enumerate(components):
            if component['type'] == 'table':
                # Get processed table with summary
                table_data = table_lookup.get(i)
                
                if not table_data:
                    print(f"Warning: Table at index {i} not found in processed_tables")
                    continue
                
                # Create embedding text (summary + context + original table)
                embedding_text = f"""Table Summary: {table_data['summary']}

    Context: {table_data['context_before']}

    Original Table Data:
    {table_data['content']}

    {table_data['context_after']}"""
                
                chunk = {
                    'chunk_id': f"{filing_metadata['ticker']}_{filing_metadata['formType']}_{section_name}_table_{i}",
                    'type': 'table',
                    'summary': table_data['summary'],
                    'table_content': table_data['content'],
                    'embedding_text': embedding_text,
                    'context_before': table_data['context_before'],
                    'context_after': table_data['context_after'],
                    'metadata': {
                        'ticker': filing_metadata['ticker'],
                        'company_name': filing_metadata['companyName'],
                        'filing_type': filing_metadata['formType'],
                        'filing_date': filing_metadata['filedAt'],
                        'accession_number': filing_metadata['accessionNo'],
                        'section': section_name,
                        'chunk_type': 'table',
                        'position': component['position']
                    }
                }
                chunks.append(chunk)
                
            else:  # text component
                # Apply semantic chunking
                text_chunks = processor.semantic_chunk_text(component['content'])
                
                for j, text_chunk in enumerate(text_chunks):
                    chunk = {
                        'chunk_id': f"{filing_metadata['ticker']}_{filing_metadata['formType']}_{section_name}_text_{i}_{j}",
                        'type': 'text',
                        'embedding_text': text_chunk,
                        'metadata': {
                            'ticker': filing_metadata['ticker'],
                            'company_name': filing_metadata['companyName'],
                            'filing_type': filing_metadata['formType'],
                            'filing_date': filing_metadata['filedAt'],
                            'accession_number': filing_metadata['accessionNo'],
                            'section': section_name,
                            'chunk_type': 'text',
                            'position': component['position'],
                            'chunk_index': j
                        }
                    }
                    chunks.append(chunk)
        
        # Generate embeddings for all chunks
        chunks = self.generate_embeddings(chunks, show_progress=True)
        
        return chunks
    
    def store_in_qdrant(self, chunks: List[Dict]) -> int:
        """
        Store chunks with embeddings in Qdrant
        
        Args:
            chunks: List of chunks with embeddings
            
        Returns:
            Number of points stored
        """
        if not chunks:
            print("No chunks to store")
            return 0
        
        print(f"Storing {len(chunks)} chunks in Qdrant...")
        
        # Prepare points for insertion
        points = []
        for chunk in chunks:
            # Generate unique ID from chunk_id
            point_id = abs(hash(chunk['chunk_id'])) % (10 ** 10)
            
            # Prepare payload (everything except embedding)
            payload = {
                'chunk_id': chunk['chunk_id'],
                'type': chunk['type'],
                'metadata': chunk['metadata']
            }
            
            # Add type-specific fields
            if chunk['type'] == 'table':
                payload['summary'] = chunk.get('summary', '')
                payload['table_content'] = chunk.get('table_content', '')
                payload['context_before'] = chunk.get('context_before', '')
                payload['context_after'] = chunk.get('context_after', '')
            else:
                payload['content'] = chunk.get('embedding_text', '')
            
            point = PointStruct(
                id=point_id,
                vector=chunk['embedding'],
                payload=payload
            )
            points.append(point)
        
        # Insert in batches
        batch_size = 100
        total_batches = (len(points) + batch_size - 1) // batch_size
        
        for i in range(0, len(points), batch_size):
            batch = points[i:i+batch_size]
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=batch
            )
            print(f"  ✓ Inserted batch {i//batch_size + 1}/{total_batches}")
        
        print(f"✓ Stored {len(chunks)} chunks in Qdrant")
        return len(chunks)
    
    def search(
        self,
        query_text: str,
        limit: int = 10,
        filter_conditions: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Search for similar chunks using semantic similarity
        
        Args:
            query_text: Text to search for
            limit: Maximum number of results
            filter_conditions: Optional Qdrant filter conditions
            
        Returns:
            List of search results with scores
        """
        # Generate query embedding
        query_embedding = self.embedding_model.encode(
            query_text,
            normalize_embeddings=True
        ).tolist()
        
        # Build filter if provided
        query_filter = None
        if filter_conditions:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value)
                    )
                    for key, value in filter_conditions.items()
                ]
            )
        
        # Search
        search_results = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            query_filter=query_filter,
            limit=limit
        )
        
        # Format results
        results = []
        for hit in search_results:
            results.append({
                'score': hit.score,
                'chunk_id': hit.payload['chunk_id'],
                'type': hit.payload['type'],
                'metadata': hit.payload['metadata'],
                'content': hit.payload.get('summary') or hit.payload.get('content', ''),
                'full_data': hit.payload
            })
        
        return results
    
    def delete_by_filing(self, accession_number: str) -> bool:
        """
        Delete all chunks for a specific filing
        
        Args:
            accession_number: Accession number of the filing
            
        Returns:
            Success status
        """
        try:
            self.qdrant_client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="metadata.accession_number",
                                match=models.MatchValue(value=accession_number)
                            )
                        ]
                    )
                )
            )
            print(f"✓ Deleted chunks for filing: {accession_number}")
            return True
        except Exception as e:
            print(f"✗ Error deleting chunks: {e}")
            return False


# # Example usage
# if __name__ == "__main__":
#     # Initialize
#     embeddings_mgr = EmbeddingsManager()
    
#     # Sample chunks (simulating processed data)
#     sample_chunks = [
#         {
#             'chunk_id': 'AAPL_10-K_1A_text_0_0',
#             'type': 'text',
#             'embedding_text': 'Our business faces various operational risks including supply chain disruptions.',
#             'metadata': {
#                 'ticker': 'AAPL',
#                 'filing_type': '10-K',
#                 'section': '1A',
#                 'accession_number': '0000320193-24-000123'
#             }
#         },
#         {
#             'chunk_id': 'AAPL_10-K_1A_table_1',
#             'type': 'table',
#             'embedding_text': 'Table Summary: Revenue breakdown by segment...\n\nOriginal Table:\n...',
#             'summary': 'Revenue breakdown by segment for 2022-2024',
#             'table_content': 'Revenue table content...',
#             'context_before': 'Context before',
#             'context_after': 'Context after',
#             'metadata': {
#                 'ticker': 'AAPL',
#                 'filing_type': '10-K',
#                 'section': '1A',
#                 'accession_number': '0000320193-24-000123'
#             }
#         }
#     ]
    
#     # Generate embeddings
#     chunks_with_embeddings = embeddings_mgr.generate_embeddings(sample_chunks)
    
#     # Store in Qdrant
#     embeddings_mgr.store_in_qdrant(chunks_with_embeddings)
    
#     # Test search
#     results = embeddings_mgr.search("What are the revenue trends?", limit=5)
#     print(f"\nSearch Results:")
#     for result in results:
#         print(f"  Score: {result['score']:.3f} - {result['content'][:100]}...")
