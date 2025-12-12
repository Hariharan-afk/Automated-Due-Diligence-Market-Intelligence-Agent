"""
Comprehensive Apple 2024 Data Processing Test

Fetches and processes ALL Apple data for 2024:
- SEC Filings: 10-K, 10-Q (all quarters)
- Wikipedia: Company page
- News: Recent articles

Uploads everything to cloud infrastructure:
- Google Cloud Storage (raw data)
- Qdrant (vector embeddings)
- PostgreSQL (state tracking)

Usage:
    python scripts/test_apple_2024.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_ingestion.sec_fetcher import SECFetcher
from src.data_ingestion.wikipedia_fetcher import WikipediaFetcher
from src.data_ingestion.news_fetcher import NewsFetcher
from src.data_processing.chunker import TextChunker
from src.data_processing.table_processor import TableProcessor
from src.utils.table_summarizer import GroqTableSummarizer
from src.embedding import Embedder
from src.cloud import GCSConnector, QdrantConnector
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# Load environment variables
load_dotenv()


# ============================================================
# Configuration
# ============================================================
COMPANY = {
    'ticker': 'AAPL',
    'name': 'Apple Inc.',
    'cik': '0000320193',
    'wikipedia_title': 'Apple Inc.'
}

YEAR = 2024
COLLECTION_NAME = "company_data"


def process_sec_filings(
    embedder, chunker, table_processor, gcs, qdrant,
    ticker, company_name, cik
):
    """Process SEC 10-K and 10-Q filings"""
    
    print("\n" + "=" * 80)
    print(f"📄 PROCESSING SEC FILINGS FOR {ticker} ({YEAR})")
    print("=" * 80 + "\n")
    
    # Initialize fetcher
    sec_fetcher = SECFetcher(user_identity=os.getenv('SEC_API_KEY', 'your.email@example.com'))
    
    # Fetch 10-K and 10-Q
    filings = sec_fetcher.fetch_filings_by_cik(
        cik=cik,
        filing_types=['10-K', '10-Q'],
        start_date=f'{YEAR}-01-01',
        end_date=f'{YEAR}-12-31'
    )
    
    print(f"✅ Fetched {len(filings)} filings: {[f['filing_type'] for f in filings]}\n")
    
    total_chunks = 0
    total_tables = 0
    
    for filing in filings:
        print(f"\n🔄 Processing: {filing['filing_type']} - {filing['filing_date']}")
        print(f"   Accession: {filing['accession_number']}")
        print(f"   Sections: {filing['total_sections']}")
        
        # Note: Skipping state tracking for this test
        # Focusing on cloud uploads only (GCS + Qdrant)
        
        filing_chunks = 0
        filing_tables = 0
        
        # Process EACH section
        for section in filing['sections']:
            section_metadata = {
                'ticker': ticker,
                'company': company_name,
                'filing_type': filing['filing_type'],
                'filing_year': filing['fiscal_year'],
                'fiscal_quarter': filing.get('fiscal_quarter'),
                'accession_number': filing['accession_number'],
                'section': section['section_code'],
                'section_name': section['section_name']
            }
            
            # Process tables
            processed_text, tables = table_processor.process_section(
                section_html=section.get('section_html_doc'),
                section_text=section['section_text'],
                metadata=section_metadata
            )
            
            filing_tables += len(tables)
            
            # Chunk the text
            chunks = chunker.chunk_text(processed_text)
            filing_chunks += len(chunks)
            
            if not chunks:
                continue
            
            # Generate embeddings
            embeddings = embedder.embed_documents(chunks, batch_size=32)
            
            # Upload raw data to GCS
            raw_data = {
                'filing_metadata': {
                    'ticker': ticker,
                    'company': company_name,
                    'filing_type': filing['filing_type'],
                    'accession_number': filing['accession_number'],
                    'filing_date': filing['filing_date'],
                    'fiscal_year': filing['fiscal_year'],
                    'fiscal_quarter': filing.get('fiscal_quarter')
                },
                'section': {
                    'code': section['section_code'],
                    'name': section['section_name'],
                    'length': section['section_length']
                },
                'tables': tables,
                'chunks': chunks,
                'total_chunks': len(chunks),
                'processed_at': datetime.utcnow().isoformat()
            }
            
            gcs_path = f"raw/sec/{ticker}/{filing['fiscal_year']}/{filing['accession_number']}_section_{section['section_code']}.json"
            gcs.upload_data(data=raw_data, gcs_path=gcs_path)
            
            # Prepare payloads for Qdrant with comprehensive metadata
            payloads = []
            current_time = datetime.utcnow().isoformat() + 'Z'
            
            # Generate table references if any
            table_refs = []
            num_tables = 0
            if tables:
                for t_idx, table in enumerate(tables):
                    table_refs.append(f"TABLE_{ticker}_{filing['accession_number']}_{section['section_code']}_{t_idx}")
                num_tables = len(tables)
            
            for i, chunk_text in enumerate(chunks):
                chunk_tokens = len(chunker.encoding.encode(chunk_text))
                chunk_id = f"{ticker}_sec_{filing['accession_number']}_{section['section_code']}_{i}"
                
                payloads.append({
                    # Core identifiers
                    'chunk_id': chunk_id,
                    'ticker': ticker,
                    'company': company_name,
                    'data_source': 'sec',
                    
                    # Filing metadata
                    'filing_type': filing['filing_type'],
                    'filing_date': filing['filing_date'],
                    'fiscal_year': filing['fiscal_year'],
                    'fiscal_quarter': filing.get('fiscal_quarter'),
                    'accession_number': filing['accession_number'],
                    'url': filing.get('filing_url', f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={filing['filing_type']}&dateb=&owner=exclude&count=40"),
                    
                    # Section metadata
                    'section': section['section_code'],
                    'section_name': section['section_name'],
                    
                    # Chunk metadata
                    'chunk_index': i,
                    'total_chunks_in_section': len(chunks),
                    'chunk_text': chunk_text,
                    'chunk_length': len(chunk_text),
                    'chunk_tokens': chunk_tokens,
                    
                    # Table metadata
                    'has_tables': len(tables) > 0,
                    'table_references': table_refs,
                    'num_tables_in_chunk': num_tables,
                    
                    # Storage
                    'gcs_path': gcs_path,
                    
                    # Timestamps
                    'created_at': current_time,
                    'fetched_at': current_time,
                    'expires_at': None,
                    
                    # Bias mitigation & coverage
                    'coverage_classification': 'medium',
                    'boost_factor': 0.12
                })
            
            # Upload to Qdrant
            qdrant.upload_vectors(
                collection_name=COLLECTION_NAME,
                vectors=embeddings,
                payloads=payloads
            )
            
            print(f"      ✓ {section['section_code']}: {len(chunks)} chunks, {len(tables)} tables")

        
        total_chunks += filing_chunks
        total_tables += filing_tables
        
        print(f"   ✅ Completed: {filing_chunks} chunks, {filing_tables} tables")
    
    print(f"\n✅ SEC Processing Complete:")
    print(f"   Total Filings: {len(filings)}")
    print(f"   Total Chunks: {total_chunks}")
    print(f"   Total Tables: {total_tables}")
    
    return len(filings), total_chunks, total_tables


def process_wikipedia(
    embedder, chunker, gcs, qdrant,
    ticker, company_name, wikipedia_title
):
    """Process Wikipedia page"""
    
    print("\n" + "=" * 80)
    print(f"📖 PROCESSING WIKIPEDIA FOR {company_name}")
    print("=" * 80 + "\n")
    
    # Initialize fetcher
    wiki_fetcher = WikipediaFetcher()
    
    # Fetch page
    try:
        page = wiki_fetcher.fetch(wikipedia_title)
    except Exception as e:
        print(f"❌ Failed to fetch Wikipedia page: {e}")
        return 0, 0
    
    print(f"✅ Fetched: {page['page_title']}")
    print(f"   URL: {page['page_url']}")
    print(f"   Length: {len(page['text_content']):,} chars")
    print(f"   Page ID: {page.get('revision_id', 'Unknown')}\n")
    
    # Note: State checking for Wikipedia not implemented yet
    # Will process every time for now

    
    # Chunk the content (use text_content)
    chunks = chunker.chunk_text(page['text_content'])
    
    print(f"   ✓ Created {len(chunks)} chunks")
    
    # Generate embeddings
    embeddings = embedder.embed_documents(chunks, batch_size=32)
    
    # Upload raw data to GCS
    raw_data = {
        'page_metadata': {
            'title': page['page_title'],
            'ticker': ticker,
            'company': company_name,
            'url': page['page_url'],
            'revision_id': page.get('revision_id'),
            'last_modified': page.get('timestamp')
        },
        'content': page['text_content'],
        'summary': page.get('summary', ''),
        'chunks': chunks,
        'total_chunks': len(chunks),
        'processed_at': datetime.utcnow().isoformat()
    }
    
    gcs_path = f"raw/wikipedia/{ticker}/{page['page_title'].replace(' ', '_')}.json"
    gcs.upload_data(data=raw_data, gcs_path=gcs_path)
    
    # Prepare payloads for Qdrant with comprehensive metadata
    payloads = []
    current_time = datetime.utcnow().isoformat() + 'Z'
    
    for i, chunk_text in enumerate(chunks):
        chunk_tokens = len(chunker.encoding.encode(chunk_text))
        chunk_id = f"{ticker}_wiki_{i}"
        
        payloads.append({
            # Core identifiers
            'chunk_id': chunk_id,
            'ticker': ticker,
            'company': company_name,
            'data_source': 'wikipedia',
            
            # Wikipedia metadata
            'page_title': page['page_title'],
            'page_url': page['page_url'],
            'revision_id': page.get('revision_id'),
            
            # Chunk metadata
            'chunk_index': i,
            'total_chunks': len(chunks),
            'chunk_text': chunk_text,
            'chunk_length': len(chunk_text),
            'chunk_tokens': chunk_tokens,
            
            # Table metadata (Wikipedia doesn't have tables in this implementation)
            'has_tables': False,
            'table_references': [],
            
            # Storage
            'gcs_path': gcs_path,
            
            # Timestamps
            'created_at': current_time,
            'fetched_at': current_time,
            'last_revision_check': current_time,
            'expires_at': None,
            
            # Bias mitigation & coverage
            'coverage_classification': 'medium',
            'boost_factor': 0.12
        })
    
    # Upload to Qdrant
    qdrant.upload_vectors(
        collection_name=COLLECTION_NAME,
        vectors=embeddings,
        payloads=payloads
    )

    
    print(f"✅ Wikipedia Processing Complete: {len(chunks)} chunks")
    
    return 1, len(chunks)


def process_news(
    embedder, chunker, gcs, qdrant,
    ticker, company_name
):
    """Process news articles"""
    
    print("\n" + "=" * 80)
    print(f"📰 PROCESSING NEWS FOR {company_name}")
    print("=" * 80 + "\n")
    
    # Initialize fetcher
    news_fetcher = NewsFetcher(mode="auto")
    
    # Fetch recent news (last 30 days)
    articles = news_fetcher.fetch_by_ticker(
        ticker=ticker,
        days_back=30,
        max_records=20,
        relevance_threshold=0.3
    )
    
    if not articles:
        print("ℹ️  No news articles found")
        return 0, 0
    
    print(f"✅ Fetched {len(articles)} articles\n")
    
    total_chunks = 0
    processed_articles = 0
    
    for article in articles:
        # Note: State checking for news not implemented yet
        # Will process all articles for now
        
        # Calculate expiration (6 months from publication)
        pub_date_str = article.get('published_at') or article.get('publishedAt')
        if pub_date_str:
            pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
        else:
            pub_date = datetime.now()
        
        expires_at = pub_date + timedelta(days=180)

        
        # Chunk the content
        chunks = chunker.chunk_text(article['content'])
        
        if not chunks:
            continue
        
        # Generate embeddings
        embeddings = embedder.embed_documents(chunks, batch_size=32)
        
        # Upload raw data to GCS
        raw_data = {
            'article_metadata': {
                'title': article['title'],
                'ticker': ticker,
                'company': company_name,
                'url': article['url'],
                'published_at': pub_date.isoformat(),
                'source': article.get('source', {}).get('name', 'Unknown') if isinstance(article.get('source'), dict) else article.get('source', 'Unknown'),
                'expires_at': expires_at.isoformat(),
                'relevance_score': article.get('relevance_score', 0)
            },
            'content': article['content'],
            'chunks': chunks,
            'total_chunks': len(chunks),
            'processed_at': datetime.utcnow().isoformat()
        }
        
        gcs_path = f"raw/news/{ticker}/{pub_date.strftime('%Y%m%d')}_{article['url'].split('/')[-1][:50]}.json"
        gcs.upload_data(data=raw_data, gcs_path=gcs_path)
        
        # Prepare payloads for Qdrant with comprehensive metadata
        payloads = []
        current_time = datetime.utcnow().isoformat() + 'Z'
        article_id = article['url'].split('/')[-1][:50]  # Use URL slug as article_id
        source_name = article.get('source', {}).get('name', 'Unknown') if isinstance(article.get('source'), dict) else article.get('source', 'Unknown')
        
        for i, chunk_text in enumerate(chunks):
            chunk_tokens = len(chunker.encoding.encode(chunk_text))
            chunk_id = f"{ticker}_news_{article_id}_{i}"
            
            payloads.append({
                # Core identifiers
                'chunk_id': chunk_id,
                'ticker': ticker,
                'company': company_name,
                'data_source': 'news',
                
                # Article metadata
                'article_title': article['title'],
                'article_url': article['url'],
                'article_id': article_id,
                'source': source_name,
                'author': article.get('authors', ['Unknown'])[0] if article.get('authors') else 'Unknown',
                'published_date': pub_date.isoformat() + 'Z',
                'relevance_score': article.get('relevance_score', 0.0),
                
                # Chunk metadata
                'chunk_index': i,
                'total_chunks_in_article': len(chunks),
                'chunk_text': chunk_text,
                'chunk_length': len(chunk_text),
                'chunk_tokens': chunk_tokens,
                
                # Table metadata (news articles don't have tables in this implementation)
                'has_tables': False,
                'table_references': [],
                
                # Storage
                'gcs_path': gcs_path,
                
                # Timestamps
                'created_at': current_time,
                'fetched_at': current_time,
                'expires_at': expires_at.isoformat() + 'Z',
                
                # Bias mitigation & coverage
                'coverage_classification': 'medium',
                'boost_factor': 0.12
            })
        
        # Upload to Qdrant
        qdrant.upload_vectors(
            collection_name=COLLECTION_NAME,
            vectors=embeddings,
            payloads=payloads
        )

        
        total_chunks += len(chunks)
        processed_articles += 1
        
        print(f"   ✓ {article['title'][:60]}... ({len(chunks)} chunks)")
    
    print(f"\n✅ News Processing Complete:")
    print(f"   Articles Processed: {processed_articles}")
    print(f"   Total Chunks: {total_chunks}")
    
    return processed_articles, total_chunks


def main():
    """Run comprehensive Apple 2024 data processing"""
    
    print("\n" + "=" * 80)
    print(f"🍎 COMPREHENSIVE APPLE {YEAR} DATA PROCESSING TEST")
    print("=" * 80)
    print()
    print(f"Company: {COMPANY['name']} ({COMPANY['ticker']})")
    print(f"Data Sources: SEC Filings (10-K, 10-Q), Wikipedia, News")
    print(f"Target Year: {YEAR}")
    print()
    
    try:
        # ============================================================
        # Initialize Components
        # ============================================================
        print("🔧 Initializing components...")
        
        # Cloud connectors (GCS and Qdrant only for this test)
        gcs = GCSConnector(
            bucket_name=os.getenv('GCP_BUCKET_NAME'),
            project_id=os.getenv('GCP_PROJECT_ID'),
            credentials_path=os.getenv('GCP_CREDENTIALS_PATH')
        )
        
        qdrant = QdrantConnector(
            url=os.getenv('QDRANT_URL'),
            api_key=os.getenv('QDRANT_API_KEY')
        )
        
        # Processing components
        embedder = Embedder()
        chunker = TextChunker(chunk_size=512, overlap=128)
        
        table_summarizer = GroqTableSummarizer(api_key=os.getenv('GROQ_API_KEY'))
        table_processor = TableProcessor(summarizer=table_summarizer, min_table_size=0)
        
        # Create Qdrant collection
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vector_size=1024,
            distance='Cosine',
            recreate=False
        )
        
        print("✅ All components initialized\n")
        
        # ============================================================
        # Process Data Sources
        # ============================================================
        
        # 1. SEC Filings
        sec_filings, sec_chunks, sec_tables = process_sec_filings(
            embedder, chunker, table_processor, gcs, qdrant,
            COMPANY['ticker'], COMPANY['name'], COMPANY['cik']
        )
        
        # 2. Wikipedia
        wiki_pages, wiki_chunks = process_wikipedia(
            embedder, chunker, gcs, qdrant,
            COMPANY['ticker'], COMPANY['name'], COMPANY['wikipedia_title']
        )
        
        # 3. News
        news_articles, news_chunks = process_news(
            embedder, chunker, gcs, qdrant,
            COMPANY['ticker'], COMPANY['name']
        )
        
        # ============================================================
        # Final Summary
        # ============================================================
        print("\n" + "=" * 80)
        print("✅ PROCESSING COMPLETE!")
        print("=" * 80)
        print()
        print("📊 Summary:")
        print(f"   SEC Filings: {sec_filings} ({sec_chunks} chunks, {sec_tables} tables)")
        print(f"   Wikipedia: {wiki_pages} page ({wiki_chunks} chunks)")
        print(f"   News: {news_articles} articles ({news_chunks} chunks)")
        print()
        
        total_chunks = sec_chunks + wiki_chunks + news_chunks
        print(f"   🎯 Total Chunks Processed: {total_chunks:,}")
        print()
        
        # Get statistics
        collection_info = qdrant.get_collection_info(COLLECTION_NAME)
        
        print("☁️  Cloud Storage:")
        print(f"   GCS Bucket: {os.getenv('GCP_BUCKET_NAME')}")
        print(f"   Qdrant Collection: {COLLECTION_NAME} ({collection_info.get('vectors_count', 0):,} vectors)")
        print()
        print("🎉 All data successfully processed and uploaded to cloud!")
        
    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        print(f"\n❌ Processing failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
