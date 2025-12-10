import sys
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv()

from src.graph import app
from src.utils.result_saver import save_result

def main():
    """Main execution"""
    
    print("\n" + "="*70)
    print("🚀 MARKET DUE DILIGENCE SYSTEM (5-AGENT ARCHITECTURE)")
    print("="*70)
    print("Type your query (or 'quit' to exit)\n")
    
    while True:
        user_input = input("Your query: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye!")
            break
        
        if user_input:
            print(f"\nProcessing: {user_input}")
            try:
                # Run the graph
                inputs = {"query": user_input}
                final_state = app.invoke(inputs)
                
                print("\n" + "="*70)
                print("FINAL ANSWER")
                print("="*70)
                print(final_state["answer"])
                print("-" * 70)
                print(f"Confidence: {final_state.get('confidence', 0.0):.2f}")
                print(f"Hallucination Score: {final_state.get('hallucination_score', 0.0):.2f}")
                print(f"Sources: {len(final_state['sources'])}")
                print("="*70)
                
                # Save results
                md_path, html_path = save_result(user_input, final_state)
                print(f"\n💾 Results saved:")
                print(f"   📄 Markdown: {md_path}")
                print(f"   🌐 HTML: {html_path}")
                
            except Exception as e:
                print(f"\n❌ Error: {e}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    main()