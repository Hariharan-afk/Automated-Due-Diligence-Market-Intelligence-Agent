"""
main.py - Main System Orchestrator
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Run: python main.py
"""

from src.agents.analyser_agent import AnalyserAgent
from src.agents.researcher_agent import ResearcherAgent
from src.agents.synthesiser_agent import SynthesiserAgent
from src.tools.hybrid_search import HybridSearchEngine
from src.tools.reranker import Reranker

from src.utils.logger import get_system_logger

class DueDiligenceSystem:
    """Main orchestrator for the agent system"""
    
    def __init__(self):
        self.logger = get_system_logger()
        self.logger.info("="*70)
        self.logger.info("🚀 INITIALIZING DUE DILIGENCE SYSTEM")
        self.logger.info("="*70)
        
        # Initialize tools
        self.logger.info("📚 Initializing search tools...")
        self.search_engine = HybridSearchEngine()
        self.reranker = Reranker()
        
        # Initialize agents
        self.logger.info("🤖 Initializing agents...")
        self.analyser = AnalyserAgent()
        self.researcher = ResearcherAgent(self.search_engine, self.reranker)
        self.synthesiser = SynthesiserAgent()
        
        self.logger.info("="*70)
        self.logger.info("✅ SYSTEM READY!")
        self.logger.info("="*70)
    
    def query(self, user_query: str):
        """Process user query through all agents"""
        
        self.logger.info("="*70)
        self.logger.info(f"USER QUERY: {user_query}")
        self.logger.info("="*70)
        
        # Agent 1: Decompose query
        self.logger.info("🧠 AGENT 1: ANALYSER")
        self.logger.info("-" * 70)
        sub_queries = self.analyser.execute(user_query)
        
        # Agent 2: Research
        self.logger.info("🔍 AGENT 2: RESEARCHER")
        self.logger.info("-" * 70)
        chunks = self.researcher.execute(sub_queries)
        
        # Agent 3: Synthesize
        self.logger.info("✍️  AGENT 3: SYNTHESISER")
        self.logger.info("-" * 70)
        result = self.synthesiser.execute(user_query, chunks)
        
        # Display result
        self.logger.info("="*70)
        self.logger.info("FINAL ANSWER:")
        self.logger.info("="*70)
        self.logger.info(result['answer'])
        self.logger.info("-" * 70)
        self.logger.info(f"CONFIDENCE: {result['confidence']:.2f}")
        self.logger.info(f"SOURCES: {len(result['sources'])} unique documents")
        self.logger.info("="*70)
        
        # Save result to Markdown
        self._save_result(user_query, result)
        
        return result

    def _save_result(self, query: str, result: dict):
        """Save the analysis result to a Markdown file"""
        import os
        from datetime import datetime
        
        # Create results directory if it doesn't exist
        results_dir = "results"
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
            
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{results_dir}/response_{timestamp}.md"
        
        # Format content
        content = f"""# Analysis Report
**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Query:** {query}

## Answer
{result['answer']}

## Confidence Score
**{result['confidence']:.2f}**

## Sources
"""
        for i, source in enumerate(result['sources'], 1):
            content += f"\n### Source {i}\n"
            content += f"- **File:** {source.get('source', 'Unknown')}\n"
            content += f"- **Score:** {source.get('score', 0):.4f}\n"
            content += f"- **Content:**\n> {source.get('content', '').replace(chr(10), chr(10)+'> ')}\n"
            
        # Write to file
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            self.logger.info(f"💾 Saved report to: {filename}")
        except Exception as e:
            self.logger.error(f"❌ Failed to save report: {str(e)}")


def main():
    """Main execution"""
    
    # Initialize system
    system = DueDiligenceSystem()
    
    # Interactive mode
    print("\n" + "="*70)
    print("💬 INTERACTIVE MODE")
    print("="*70)
    print("Type your query (or 'quit' to exit)\n")
    
    while True:
        user_input = input("Your query: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye!")
            break
        
        if user_input:
            system.query(user_input)


if __name__ == "__main__":
    main()


"""
agents/__init__.py
"""
from base_agent import BaseAgent
from analyser_agent import AnalyserAgent
from researcher_agent import ResearcherAgent
from synthesiser_agent import SynthesiserAgent

__all__ = ['BaseAgent', 'AnalyserAgent', 'ResearcherAgent', 'SynthesiserAgent']


"""
tools/__init__.py
"""
from .gcp_client import get_gcp_client, get_embedding, chat_completion
from .hybrid_search import HybridSearchEngine
from .reranker import Reranker

__all__ = ['get_gcp_client', 'get_embedding', 'chat_completion', 'HybridSearchEngine', 'Reranker']