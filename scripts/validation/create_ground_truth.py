# scripts/validation/create_ground_truth.py
"""
Create ground truth dataset for retrieval evaluation

This script helps you build a test dataset of query-document pairs
by querying the vector database and manually labeling relevant results.
"""

import json
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.researcher_agent import ResearcherAgent


def create_sample_ground_truth():
    """
    Create a sample ground truth dataset
    
    In production, you would:
    1. Run searches
    2. Manually label which results are relevant
    3. Build this dataset iteratively
    """
    
    ground_truth = {
        "created_at": datetime.now().isoformat(),
        "description": "Ground truth dataset for retrieval evaluation",
        "version": "1.0",
        "queries": [
            {
                "query": "What are Apple's main revenue sources?",
                "ticker": "AAPL",
                "category": "revenue",
                "relevant_chunks": [
                    # These would be actual chunk IDs from your database
                    # You get these by:
                    # 1. Running the query
                    # 2. Manually reviewing results
                    # 3. Marking which chunks correctly answer the query
                ]
            },
            {
                "query": "What are the regulatory risks facing tech companies?",
                "ticker": None,  # Multi-company query
                "category": "risk",
                "relevant_chunks": []
            },
            {
                "query": "Describe Microsoft's cloud computing business",
                "ticker": "MSFT",
                "category": "business_model",
                "relevant_chunks": []
            },
            {
                "query": "What is Amazon's AI and machine learning strategy?",
                "ticker": "AMZN",
                "category": "technology",
                "relevant_chunks": []
            },
            {
                "query": "Tesla's manufacturing capacity and production numbers",
                "ticker": "TSLA",
                "category": "operations",
                "relevant_chunks": []
            },
            {
                "query": "Google's advertising revenue trends",
                "ticker": "GOOGL",
                "category": "revenue",
                "relevant_chunks": []
            },
            {
                "query": "What are the cybersecurity risks mentioned in filings?",
                "ticker": None,
                "category": "risk",
                "relevant_chunks": []
            },
            {
                "query": "R&D spending and innovation initiatives",
                "ticker": None,
                "category": "innovation",
                "relevant_chunks": []
            },
            {
                "query": "Supply chain dependencies and risks",
                "ticker": None,
                "category": "risk",
                "relevant_chunks": []
            },
            {
                "query": "Employee headcount and talent strategy",
                "ticker": None,
                "category": "hr",
                "relevant_chunks": []
            }
        ]
    }
    
    return ground_truth


def interactive_labeling(agent: ResearcherAgent, output_file: str):
    """
    Interactive tool to build ground truth by labeling search results
    
    Args:
        agent: ResearcherAgent instance
        output_file: Where to save ground truth
    """
    print("\n" + "="*80)
    print("🏷️  INTERACTIVE GROUND TRUTH LABELING")
    print("="*80 + "\n")
    
    print("This tool helps you create a ground truth dataset by:")
    print("1. Running test queries")
    print("2. Showing you the top results")
    print("3. Letting you mark which ones are relevant\n")
    
    # Load existing or create new
    output_path = Path(output_file)
    if output_path.exists():
        with open(output_path, 'r') as f:
            ground_truth = json.load(f)
        print(f"✓ Loaded existing ground truth with {len(ground_truth['queries'])} queries\n")
    else:
        ground_truth = create_sample_ground_truth()
        print(f"✓ Created new ground truth template\n")
    
    # Process each query
    for i, query_data in enumerate(ground_truth['queries'], 1):
        query = query_data['query']
        ticker = query_data.get('ticker')
        
        print(f"\n{'='*80}")
        print(f"Query {i}/{len(ground_truth['queries'])}")
        print(f"{'='*80}")
        print(f"Query: {query}")
        print(f"Ticker: {ticker or 'ALL'}")
        print(f"Category: {query_data.get('category', 'general')}\n")
        
        # Skip if already labeled
        if query_data.get('relevant_chunks') and len(query_data['relevant_chunks']) > 0:
            print(f"✓ Already labeled ({len(query_data['relevant_chunks'])} relevant chunks)")
            continue
        
        # Run search
        print("Running search...\n")
        results = agent.search(query, ticker=ticker, top_k=10, verbose=False)
        
        # Show results
        print("Results:")
        print("-" * 80)
        for j, result in enumerate(results, 1):
            print(f"\n[{j}] Score: {result.hybrid_score:.3f}")
            print(f"    Ticker: {result.metadata.get('ticker', 'N/A')}")
            print(f"    Source: {result.metadata.get('source_type', 'N/A')}")
            print(f"    Content: {result.content[:300]}...")
        
        # Get user input
        print("\n" + "-" * 80)
        print("Mark relevant results (e.g., '1,3,5' or 'none' or 'skip'):")
        user_input = input("> ").strip().lower()
        
        if user_input == 'skip':
            continue
        elif user_input == 'none':
            query_data['relevant_chunks'] = []
        else:
            try:
                indices = [int(x.strip()) - 1 for x in user_input.split(',')]
                query_data['relevant_chunks'] = [
                    results[idx].chunk_id 
                    for idx in indices 
                    if 0 <= idx < len(results)
                ]
                print(f"✓ Marked {len(query_data['relevant_chunks'])} chunks as relevant")
            except:
                print("❌ Invalid input, skipping")
                continue
        
        # Save after each query
        with open(output_path, 'w') as f:
            json.dump(ground_truth, f, indent=2)
        print(f"✓ Saved to {output_path}")
    
    print("\n" + "="*80)
    print("✅ LABELING COMPLETE")
    print("="*80 + "\n")
    print(f"Ground truth saved to: {output_path}")
    
    # Summary
    total_queries = len(ground_truth['queries'])
    labeled_queries = sum(1 for q in ground_truth['queries'] if q.get('relevant_chunks'))
    print(f"\nSummary:")
    print(f"  Total queries: {total_queries}")
    print(f"  Labeled: {labeled_queries}")
    print(f"  Remaining: {total_queries - labeled_queries}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Create ground truth dataset')
    parser.add_argument(
        '--mode',
        choices=['sample', 'interactive'],
        default='sample',
        help='Creation mode'
    )
    parser.add_argument(
        '--output',
        default='data/validation/ground_truth.json',
        help='Output file path'
    )
    
    args = parser.parse_args()
    
    if args.mode == 'sample':
        # Create sample template
        ground_truth = create_sample_ground_truth()
        
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(ground_truth, f, indent=2)
        
        print(f"\n✅ Sample ground truth created: {output_path}")
        print(f"\n💡 Next steps:")
        print(f"   1. Review the template")
        print(f"   2. Run: python scripts/validation/create_ground_truth.py --mode interactive")
        print(f"   3. Label relevant documents for each query\n")
    
    else:
        # Interactive labeling
        agent = ResearcherAgent(
            qdrant_host='localhost',
            alpha=0.5,
            top_k=10
        )
        
        print("\nLoading corpus...")
        agent.load_corpus()
        
        interactive_labeling(agent, args.output)