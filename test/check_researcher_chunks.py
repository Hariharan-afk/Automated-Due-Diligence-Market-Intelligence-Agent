
import sys
import os

# Ensure src is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from src.tools.hybrid_search import HybridSearchEngine
from src.tools.reranker import Reranker
from src.agents.researcher_agent import ResearcherAgent

def main():
    print("\n" + "="*70)
    print("🕵️ RESEARCHER AGENT CHUNK INSPECTOR")
    print("="*70)
    
    # Initialize
    print("⚙️ Initializing Agent (this may take a moment)...")
    try:
        search_engine = HybridSearchEngine()
        reranker = Reranker()
        researcher = ResearcherAgent(search_engine, reranker)
        print("✅ Agent Initialized.\n")
    except Exception as e:
        print(f"❌ Initialization Failed: {e}")
        return

    from src.config import SEARCH_CONFIG
    alpha = SEARCH_CONFIG["alpha"]
    print(f"ℹ️  Score Explanation: Hybrid Score = ({alpha} * Semantic Score) + ({1-alpha:.1f} * Keyword Score)")
    print(f"    - Semantic Score: Cosine similarity from Qdrant")
    print(f"    - Keyword Score: Normalized BM25 score")
    print(f"ℹ️  Note: Scores are specific to the retrieval pool and may vary based on distribution.")
    print("-" * 70)

    print("Type your query to see retrieved chunks (or 'quit' to exit)\n")

    while True:
        user_input = input("Query: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye!")
            break
            
        if not user_input:
            continue
            
        print(f"\n🔍 Searching chunks for: '{user_input}'...")
        
        try:
            # Execute researcher agent
            # We treat the input as a single "sub-query" to test retrieval for that specific topic
            # The second argument is the original_query, used for reranking
            results = researcher.execute(sub_queries=[user_input], original_query=user_input)
            
            print(f"\nFound {len(results)} chunks.\n")
            
            for i, chunk in enumerate(results, 1):
                score = chunk.get('final_score', chunk.get('score', 0))
                chunk_id = chunk.get('chunk_id', chunk.get('id', 'N/A'))
                source = chunk.get('metadata', {}).get('source', 'unknown')
                content = chunk.get('raw_chunk', chunk.get('content', ''))
                
                # Truncate content for display
                display_content = (content[:200] + '...') if len(content) > 200 else content
                display_content = display_content.replace('\n', ' ')
                
                print(f"[{i}] Chunk ID: {chunk_id} | Score: {score:.4f} | Source: {source}")
                print(f"    {display_content}")
                print("-" * 50)
                
        except Exception as e:
            print(f"❌ Error during execution: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
