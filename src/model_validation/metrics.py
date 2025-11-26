"""
validation/metrics.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RAG Evaluation Metrics (Deterministic / No-LLM Version)
"""

import sys
sys.path.append('.')

import re
import string
from typing import List, Dict, Set

class RAGMetrics:
    """Compute evaluation metrics using deterministic heuristics"""
    
    def __init__(self):
        # Basic stopwords to filter out for keyword analysis
        self.stopwords = {
            'a', 'an', 'the', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'is', 'are', 'was', 'were', 'be', 'been', 'has', 'have',
            'had', 'do', 'does', 'did', 'but', 'and', 'or', 'as', 'if',
            'what', 'where', 'when', 'who', 'how', 'why', 'which'
        }

    def _tokenize(self, text: str) -> Set[str]:
        """Helper to clean and tokenize text into a set of words"""
        if not text:
            return set()
        # Remove punctuation and convert to lower case
        text = text.lower().translate(str.maketrans('', '', string.punctuation))
        # Split and filter stopwords
        tokens = {word for word in text.split() if word not in self.stopwords and len(word) > 1}
        return tokens

    # ═══════════════════════════════════════════════════════════════
    # 1. GROUNDEDNESS (Token Overlap)
    # ═══════════════════════════════════════════════════════════════
    
    def compute_groundedness(self, answer: str, retrieved_chunks: List[Dict]) -> Dict:
        """
        Measure overlap between Answer tokens and Context tokens.
        Assumption: A grounded answer uses vocabulary found in the context.
        """
        if not answer or not retrieved_chunks:
            return {"score": 0.0, "overlap_count": 0}
        
        # 1. Tokenize Answer
        answer_tokens = self._tokenize(answer)
        if not answer_tokens:
            return {"score": 0.0}
            
        # 2. Tokenize All Context
        context_text = " ".join([c.get('raw_chunk', '') for c in retrieved_chunks])
        context_tokens = self._tokenize(context_text)
        
        # 3. Calculate Intersection
        # How many unique answer words exist in the context?
        intersection = answer_tokens.intersection(context_tokens)
        
        score = len(intersection) / len(answer_tokens)
        
        return {
            "score": score,
            "supported_tokens": len(intersection),
            "total_answer_tokens": len(answer_tokens),
            "details": "Computed via Token Overlap"
        }
    
    # ═══════════════════════════════════════════════════════════════
    # 2. CITATION METRICS (Regex - Unchanged)
    # ═══════════════════════════════════════════════════════════════
    
    def compute_citation_metrics(self, answer: str, sources: List[Dict], 
                                 retrieved_chunks: List[Dict]) -> Dict:
        """
        Measure citation precision and recall using Regex
        """
        # Extract citations from answer (format: [Company - Source - Date])
        citation_pattern = r'\[([^\]]+)\]'
        citations = re.findall(citation_pattern, answer)
        
        has_facts = any(keyword in answer.lower() 
                      for keyword in ['revenue', '$', 'founded', 'employees', 'growth'])

        if not citations:
            return {
                "precision": 0.0,
                "recall": 0.0 if has_facts else 1.0,
                "f1_score": 0.0,
                "citations_found": 0
            }
        
        # Precision: Check if citations match actual sources
        valid_citations = 0
        for citation in citations:
            for source in sources:
                # flexible matching of source name or type
                if (source.get('company', '').lower() in citation.lower() or
                    source.get('source_type', '').lower() in citation.lower()):
                    valid_citations += 1
                    break
        
        precision = valid_citations / len(citations)
        
        # Recall: Should have cited each unique source used
        expected_citations = len(sources)
        recall = min(len(citations) / expected_citations, 1.0) if expected_citations > 0 else 0.0
        
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        
        return {
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "citations_found": len(citations),
            "expected_citations": expected_citations
        }
    
    # ═══════════════════════════════════════════════════════════════
    # 3. ANSWER RELEVANCY (Query Keyword Recall)
    # ═══════════════════════════════════════════════════════════════
    
    def compute_answer_relevancy(self, query: str, answer: str) -> Dict:
        """
        Measure if the answer contains key terms from the query.
        """
        if not answer or not query:
            return {"score": 0.0, "explanation": "Empty inputs"}
        
        query_tokens = self._tokenize(query)
        answer_text = answer.lower()
        
        if not query_tokens:
            return {"score": 1.0} # No distinct keywords to check
            
        found_keywords = [token for token in query_tokens if token in answer_text]
        
        score = len(found_keywords) / len(query_tokens)
        
        return {
            "score": score,
            "found_keywords": found_keywords,
            "missing_keywords": list(query_tokens - set(found_keywords)),
            "explanation": f"Found {len(found_keywords)}/{len(query_tokens)} query keywords"
        }
    
    # ═══════════════════════════════════════════════════════════════
    # 4. CONTEXT RELEVANCY (Keyword Overlap)
    # ═══════════════════════════════════════════════════════════════
    
    def compute_context_relevancy(self, query: str, retrieved_chunks: List[Dict]) -> Dict:
        """
        Measure if retrieved chunks contain query keywords
        """
        if not retrieved_chunks:
            return {"score": 0.0, "relevant_chunks": 0}
        
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return {"score": 1.0}

        relevant_count = 0
        for chunk in retrieved_chunks:
            chunk_text = chunk.get('raw_chunk', '').lower()
            # Check if at least one query keyword is in the chunk
            if any(token in chunk_text for token in query_tokens):
                relevant_count += 1
        
        return {
            "score": relevant_count / len(retrieved_chunks),
            "relevant_chunks": relevant_count,
            "total_chunks": len(retrieved_chunks)
        }
    
    # ═══════════════════════════════════════════════════════════════
    # 5. SECTION COMPLETENESS (String Matching)
    # ═══════════════════════════════════════════════════════════════
    
    def compute_section_completeness(self, answer: str, required_sections: List[str]) -> Dict:
        """
        Check if all required sections are present in answer
        """
        if not required_sections:
            return {"score": 1.0}
        
        present = []
        missing = []
        answer_lower = answer.lower()
        
        for section in required_sections:
            # Loose matching: check if the section words appear sequentially or close
            # Simple check: is the exact section header roughly there?
            if section.lower() in answer_lower:
                present.append(section)
            else:
                missing.append(section)
        
        return {
            "score": len(present) / len(required_sections),
            "present_sections": present,
            "missing_sections": missing
        }
    
    # ═══════════════════════════════════════════════════════════════
    # 6. FACTUAL ACCURACY (Exact String / Substring Match)
    # ═══════════════════════════════════════════════════════════════
    
    def compute_factual_accuracy(self, answer: str, expected_contains: List[str]) -> Dict:
        """
        Check if expected facts/strings are present in answer
        """
        if not expected_contains:
            return {"score": 1.0}
        
        found = []
        missing = []
        answer_lower = answer.lower()
        
        for expected in expected_contains:
            if expected.lower() in answer_lower:
                found.append(expected)
            else:
                missing.append(expected)
        
        return {
            "score": len(found) / len(expected_contains),
            "found": found,
            "missing": missing
        }
    
    # ═══════════════════════════════════════════════════════════════
    # 7. SOURCE COVERAGE (List Matching)
    # ═══════════════════════════════════════════════════════════════
    
    def compute_source_coverage(self, sources: List[Dict], required_sources: List[str]) -> Dict:
        """
        Check if all required source types were used
        """
        if not required_sources:
            return {"score": 1.0}
        
        source_types = [s.get('source_type', '').lower() for s in sources]
        covered = [req for req in required_sources if req.lower() in source_types]
        
        return {
            "score": len(covered) / len(required_sources),
            "covered_sources": covered
        }


# ═══════════════════════════════════════════════════════════════
# Aggregate Metrics
# ═══════════════════════════════════════════════════════════════

def compute_all_metrics(query: str, answer: str, sources: List[Dict], 
                       retrieved_chunks: List[Dict], test_case: Dict) -> Dict:
    """
    Compute all metrics for a single test case
    """
    metrics = RAGMetrics()
    
    results = {
        "query_id": test_case.get('query_id'),
        "query": query,
    }
    
    # 1. Compute Base Metrics
    results['groundedness'] = metrics.compute_groundedness(answer, retrieved_chunks)
    results['citation'] = metrics.compute_citation_metrics(answer, sources, retrieved_chunks)
    results['answer_relevancy'] = metrics.compute_answer_relevancy(query, answer)
    results['context_relevancy'] = metrics.compute_context_relevancy(query, retrieved_chunks)
    
    # 2. Compute Task-Specific Metrics (if defined in test case)
    if 'required_sections' in test_case:
        results['section_completeness'] = metrics.compute_section_completeness(
            answer, test_case['required_sections']
        )
    
    if 'expected_answer_contains' in test_case:
        results['factual_accuracy'] = metrics.compute_factual_accuracy(
            answer, test_case['expected_answer_contains']
        )
    
    if 'required_sources' in test_case:
        results['source_coverage'] = metrics.compute_source_coverage(
            sources, test_case['required_sources']
        )
    
    # 3. Calculate Overall Score (Weighted Average)
    # We adjust weights to prioritize Factual Accuracy since we aren't using LLM-Judge
    scores = []
    
    # High Priority: Did it find the specific facts we wanted?
    if 'factual_accuracy' in results:
        scores.append(results['factual_accuracy']['score'] * 0.30)
    
    # Medium Priority: Is it grounded in context?
    if 'groundedness' in results:
        scores.append(results['groundedness']['score'] * 0.20)
        
    # Medium Priority: Did it answer the prompt keywords?
    if 'answer_relevancy' in results:
        scores.append(results['answer_relevancy']['score'] * 0.20)
        
    # Low Priority: Formatting and Citations
    if 'citation' in results:
        scores.append(results['citation'].get('f1_score', 0) * 0.15)
        
    if 'section_completeness' in results:
        scores.append(results['section_completeness']['score'] * 0.15)

    # If specific test case metrics aren't present, normalize the remaining weights
    # (Simple sum for now, assuming a "standard" test case has all of them)
    results['overall_score'] = min(sum(scores), 1.0) if scores else 0.0
    
    return results