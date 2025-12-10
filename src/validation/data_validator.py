"""
Data Validator

Comprehensive validation for fetched company data.
Checks completeness, quality, schema compliance, and more.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# Try to import tiktoken for token validation
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("tiktoken not available, token validation will be skipped")


class DataValidator:
    """
    Comprehensive data validator
    
    Validates:
    - Data completeness (all expected sources present)
    - Schema compliance (correct structure and fields)
    - Token sizes (chunks within acceptable limits)
    - Content quality (no corruption or placeholder text)
    - Statistical properties (reasonable distributions)
    - Table references (all referenced tables exist)
    """
    
    def __init__(self):
        if TIKTOKEN_AVAILABLE:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'checks': {},
            'overall_valid': True,
            'critical_issues': [],
            'warnings': [],
            'stats': {}
        }
    
    def validate_completeness(self, data: Dict) -> Dict:
        """Validate data completeness"""
        logger.debug("Running completeness validation...")
        
        issues = []
        warnings = []
        
        # Check main data sources
        if not data.get('sec'):
            issues.append("Missing SEC data")
        if not data.get('wikipedia'):
            warnings.append("Missing Wikipedia data")
        
        # SEC-specific checks
        sec_data = data.get('sec', {})
        if sec_data:
            sec_chunks = sec_data.get('chunks', [])
            if len(sec_chunks) == 0:
                issues.append("SEC data present but no chunks extracted")
            
            # Critical SEC sections
            sections = {c.get('section') for c in sec_chunks if c.get('section')}
            critical = {'1', '1A', '7', '8'}
            missing = critical - sections
            if missing:
                warnings.append(f"Missing critical SEC sections: {missing}")
        
        # Table validation
        num_tables = data.get('sec', {}).get('num_tables', 0)
        if num_tables == 0:
            warnings.append("No tables extracted from SEC filing")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'completeness_score': 1.0 - (len(issues) / 3.0)
        }
    
    def validate_schema(self, chunks: List[Dict]) -> Dict:
        """Validate chunk schema"""
        logger.debug(f"Running schema validation on {len(chunks)} chunks...")
        
        errors = []
        warnings = []
        
        # Sample chunks for validation
        sample_size = min(100, len(chunks))
        sample = chunks[:sample_size] if len(chunks) <= 100 else np.random.choice(chunks, sample_size, replace=False).tolist()
        
        for chunk in sample:
            chunk_id = chunk.get('chunk_id', 'unknown')
            
            # Required fields
            required = ['chunk_id', 'chunk_text', 'data_source', 'chunk_length']
            for field in required:
                if field not in chunk:
                    errors.append(f"{chunk_id}: Missing required field '{field}'")
            
            # Type validation
            if 'chunk_length' in chunk and not isinstance(chunk['chunk_length'], int):
                errors.append(f"{chunk_id}: chunk_length must be integer")
            
            if 'chunk_text' in chunk and not isinstance(chunk['chunk_text'], str):
                errors.append(f"{chunk_id}: chunk_text must be string")
            
            # Source-specific validation
            source = chunk.get('data_source')
            if source == 'sec':
                sec_required = ['ticker', 'section', 'filing_type']
                for field in sec_required:
                    if field not in chunk:
                        warnings.append(f"{chunk_id}: SEC chunk missing '{field}'")
            
            # Data quality
            if chunk.get('chunk_text', '').strip() == '':
                errors.append(f"{chunk_id}: Empty chunk_text")
            
            if chunk.get('chunk_length', 0) < 50:
                warnings.append(f"{chunk_id}: Very short chunk ({chunk.get('chunk_length')} chars)")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors[:10],
            'warnings': warnings[:10],
            'total_errors': len(errors),
            'total_warnings': len(warnings),
            'sampled_chunks': sample_size
        }
    
    def validate_token_sizes(self, chunks: List[Dict], max_tokens=900, min_tokens=50) -> Dict:
        """Validate chunk token sizes"""
        if not TIKTOKEN_AVAILABLE:
            return {'valid': True, 'skipped': 'tiktoken not available'}
        
        logger.debug("Running token size validation...")
        
        oversized = []
        undersized = []
        token_counts = []
        
        for chunk in chunks:
            text = chunk.get('chunk_text', '')
            tokens = len(self.encoding.encode(text))
            token_counts.append(tokens)
            
            chunk_id = chunk.get('chunk_id', 'unknown')
            
            if tokens > max_tokens:
                oversized.append({
                    'chunk_id': chunk_id,
                    'tokens': tokens,
                    'excess': tokens - max_tokens
                })
            
            if tokens < min_tokens and tokens > 0:
                undersized.append({
                    'chunk_id': chunk_id,
                    'tokens': tokens
                })
        
        return {
            'valid': len(oversized) == 0,
            'oversized_chunks': len(oversized),
            'undersized_chunks': len(undersized),
            'oversized_examples': oversized[:5],
            'undersized_examples': undersized[:5],
            'stats': {
                'avg_tokens': np.mean(token_counts) if token_counts else 0,
                'min_tokens': np.min(token_counts) if token_counts else 0,
                'max_tokens': np.max(token_counts) if token_counts else 0,
                'median_tokens': np.median(token_counts) if token_counts else 0
            }
        }
    
    def validate_table_references(self, data: Dict, tables_dir: Path) -> Dict:
        """Validate table references"""
        logger.debug("Running table reference validation...")
        
        # Get all SEC chunks
        sec_chunks = data.get('sec', {}).get('chunks', [])
        
        # Find all table files
        tables = {}
        if tables_dir.exists():
            for table_file in tables_dir.glob("tables_*.json"):
                try:
                    with open(table_file, encoding='utf-8') as f:
                        table_data = json.load(f)
                        for table in table_data:
                            tables[table['table_id']] = table
                except Exception as e:
                    logger.warning(f"Failed to load {table_file}: {e}")
        
        # Find all references
        referenced_tables = set()
        chunks_with_refs = []
        
        for chunk in sec_chunks:
            refs = chunk.get('table_references', [])
            if refs:
                referenced_tables.update(refs)
                chunks_with_refs.append(chunk['chunk_id'])
        
        # Validate references
        issues = []
        for ref in referenced_tables:
            if ref not in tables:
                issues.append(f"Referenced table not found: {ref}")
        
        # Check for orphaned tables
        actual_tables = set(tables.keys())
        orphaned = actual_tables - referenced_tables
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'stats': {
                'total_tables': len(actual_tables),
                'referenced_tables': len(referenced_tables),
                'orphaned_tables': len(orphaned),
                'chunks_with_tables': len(chunks_with_refs)
            }
        }
    
    def validate_content_quality(self, chunks: List[Dict]) -> Dict:
        """Check for content quality issues"""
        logger.debug("Running content quality validation...")
        
        issues = []
        sample_size = min(100, len(chunks))
        sample = chunks[:sample_size]
        
        for chunk in sample:
            text = chunk.get('chunk_text', '')
            chunk_id = chunk.get('chunk_id')
            
            # Check for excessive non-ASCII
            if text:
                ascii_ratio = sum(c.isascii() for c in text) / len(text)
                if ascii_ratio < 0.6:
                    issues.append({
                        'chunk_id': chunk_id,
                        'issue': 'high_non_ascii',
                        'ratio': f"{ascii_ratio:.2f}"
                    })
            
            # Check for repeated characters
            if re.search(r'(.)\1{20,}', text):
                issues.append({
                    'chunk_id': chunk_id,
                    'issue': 'repeated_characters'
                })
            
            # Check for placeholder text
            placeholders = ['lorem ipsum', 'test test', 'xxx xxx', 'placeholder']
            text_lower = text.lower()
            found = [p for p in placeholders if p in text_lower]
            if found:
                issues.append({
                    'chunk_id': chunk_id,
                    'issue': 'placeholder_text',
                    'found': found
                })
            
            # Check minimum word count
            words = len(text.split())
            if words < 10 and words > 0:
                issues.append({
                    'chunk_id': chunk_id,
                    'issue': 'too_few_words',
                    'word_count': words
                })
        
        return {
            'valid': len(issues) == 0,
            'issues': issues[:20],
            'total_issues': len(issues),
            'sampled_chunks': sample_size
        }
    
    def validate_statistics(self, all_chunks: List[Dict]) -> Dict:
        """Validate statistical properties"""
        logger.debug("Running statistical validation...")
        
        lengths = [c.get('chunk_length', 0) for c in all_chunks]
        
        stats = {
            'mean': float(np.mean(lengths)),
            'median': float(np.median(lengths)),
            'std': float(np.std(lengths)),
            'min': int(np.min(lengths)),
            'max': int(np.max(lengths))
        }
        
        warnings = []
        
        # Check for outliers
        outliers = [l for l in lengths if abs(l - stats['mean']) > 3 * stats['std']]
        if len(outliers) > len(lengths) * 0.05:
            warnings.append(f"High outlier ratio: {len(outliers)/len(lengths):.1%}")
        
        # Check for reasonable range
        if stats['max'] > stats['mean'] * 3:
            warnings.append(f"Max length {stats['max']} >> mean {stats['mean']:.0f}")
        
        # Source distribution
        source_dist = {}
        for chunk in all_chunks:
            source = chunk.get('data_source', 'unknown')
            source_dist[source] = source_dist.get(source, 0) + 1
        
        if source_dist.get('sec', 0) < 10:
            warnings.append("Very few SEC chunks")
        
        return {
            'valid': len(warnings) < 3,
            'warnings': warnings,
            'stats': stats,
            'source_distribution': source_dist,
            'total_chunks': len(all_chunks)
        }
    
    def _convert_numpy_types(self, obj):
        """Convert numpy types to native Python types for JSON serialization"""
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {key: self._convert_numpy_types(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_types(item) for item in obj]
        return obj
    
    def run_all_validations(self, data: Dict, tables_dir: Path = None) -> Dict:
        """Run all validation checks"""
        logger.info("="*70)
        logger.info("STARTING DATA VALIDATION")
        logger.info("="*70)
        
        # Combine all chunks
        all_chunks = []
        all_chunks.extend(data.get('sec', {}).get('chunks', []))
        all_chunks.extend(data.get('wikipedia', {}).get('chunks', []))
        all_chunks.extend(data.get('news', {}).get('chunks', []))
        
        if not all_chunks:
            logger.error("No chunks found in data!")
            return {
                'overall_valid': False,
                'critical_issues': ['No chunks found in data'],
                'checks': {}
            }
        
        # Run all checks
        self.results['checks']['completeness'] = self.validate_completeness(data)
        self.results['checks']['schema'] = self.validate_schema(all_chunks)
        self.results['checks']['token_sizes'] = self.validate_token_sizes(all_chunks)
        self.results['checks']['content_quality'] = self.validate_content_quality(all_chunks)
        self.results['checks']['statistics'] = self.validate_statistics(all_chunks)
        
        if tables_dir:
            self.results['checks']['table_references'] = self.validate_table_references(data, tables_dir)
        
        # Collect critical issues and warnings
        for check_name, check_result in self.results['checks'].items():
            if not check_result.get('valid', True):
                self.results['overall_valid'] = False
                
                # Add issues
                issues = check_result.get('issues', [])
                if isinstance(issues, list) and issues:
                    self.results['critical_issues'].extend(
                        [f"{check_name}: {issue}" for issue in issues[:5]]
                    )
            
            # Add warnings
            warnings = check_result.get('warnings', [])
            if isinstance(warnings, list) and warnings:
                self.results['warnings'].extend(
                    [f"{check_name}: {warning}" for warning in warnings[:5]]
                )
        
        # Add summary stats
        self.results['stats'] = {
            'total_chunks': len(all_chunks),
            'ticker': data.get('ticker'),
            'year': data.get('year'),
            'fetched_at': data.get('fetched_at')
        }
        
        # Convert numpy types
        self.results = self._convert_numpy_types(self.results)
        
        return self.results
