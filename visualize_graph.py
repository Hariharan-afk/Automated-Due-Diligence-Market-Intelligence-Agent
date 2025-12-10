"""
Visualize the LangGraph workflow
Run: python visualize_graph.py
"""

from dotenv import load_dotenv
load_dotenv()

from src.graph import app

# Generate Mermaid diagram
try:
    mermaid_code = app.get_graph().draw_mermaid()
    
    print("="*70)
    print("LANGGRAPH VISUALIZATION (Mermaid)")
    print("="*70)
    print("\nCopy this code to https://mermaid.live to visualize:\n")
    print(mermaid_code)
    print("\n" + "="*70)
    
    # Save to file
    with open("graph_visualization.md", "w") as f:
        f.write("# LangGraph Workflow Visualization\n\n")
        f.write("```mermaid\n")
        f.write(mermaid_code)
        f.write("\n```\n")
    
    print("\n✅ Saved to graph_visualization.md")
    print("   Open this file in VS Code to see the diagram!")
    
except Exception as e:
    print(f"Error: {e}")
    print("\nAlternative: Install graphviz to generate PNG")
    print("  brew install graphviz")
    print("  pip install pygraphviz")
