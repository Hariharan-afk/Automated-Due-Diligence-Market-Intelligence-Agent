"""
Data Preprocessing Module - FINAL VERSION
Handles data cleaning, transformation, and validation
"""

import pandas as pd
import json
import logging
import re
from typing import Dict, List, Any
from datetime import datetime
import os
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataCleaner:
    """Clean and normalize raw data"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Remove special characters and normalize text"""
        if not text or text == "N/A":
            return ""
        
        # Remove HTML tags
        text = BeautifulSoup(text, "html.parser").get_text()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove special characters but keep punctuation
        text = re.sub(r'[^\w\s\.\,\!\?\-\:\;]', '', text)
        
        return text
    
    @staticmethod
    def clean_url(url: str) -> str:
        """Validate and clean URLs"""
        if not url or url == "N/A":
            return ""
        
        # Basic URL validation
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        return url.strip()
    
    @staticmethod
    def parse_date(date_str: str) -> str:
        """Standardize date format"""
        if not date_str or date_str == "N/A":
            return ""
        
        try:
            # Try parsing ISO format
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d')
        except:
            try:
                # Try GDELT format (YYYYMMDDHHMMSS)
                if len(date_str) >= 8 and date_str.isdigit():
                    dt = datetime.strptime(date_str[:8], '%Y%m%d')
                    return dt.strftime('%Y-%m-%d')
            except:
                pass
        
        logger.warning(f"Could not parse date: {date_str}")
        return date_str
    
    @staticmethod
    def remove_duplicates(items: List[Dict], key: str = 'url') -> List[Dict]:
        """Remove duplicate items based on key"""
        seen = set()
        unique_items = []
        
        for item in items:
            identifier = item.get(key, '')
            if identifier and identifier not in seen:
                seen.add(identifier)
                unique_items.append(item)
        
        return unique_items


class WikipediaPreprocessor:
    """Preprocess Wikipedia data"""
    
    def __init__(self):
        self.cleaner = DataCleaner()
    
    def process(self, wiki_data: Dict) -> Dict:
        """Process Wikipedia data"""
        if "error" in wiki_data:
            return wiki_data
        
        processed = {
            "title": wiki_data.get("title", ""),
            "summary": self.cleaner.clean_text(wiki_data.get("summary", "")),
            "full_text": self.cleaner.clean_text(wiki_data.get("full_text", "")),
            "url": self.cleaner.clean_url(wiki_data.get("url", "")),
            "word_count": len(wiki_data.get("full_text", "").split()),
            "section_count": len(wiki_data.get("sections", [])),
            "has_infobox": self._check_infobox(wiki_data.get("full_text", "")),
            "timestamp": wiki_data.get("timestamp", "")
        }
        
        return processed
    
    @staticmethod
    def _check_infobox(text: str) -> bool:
        """Check if Wikipedia page has infobox"""
        return "infobox" in text.lower() or "founded" in text.lower()


class NewsPreprocessor:
    """Preprocess news articles"""
    
    def __init__(self):
        self.cleaner = DataCleaner()
    
    def process(self, news_articles: List[Dict]) -> List[Dict]:
        """Process news articles"""
        # Remove duplicates
        articles = self.cleaner.remove_duplicates(news_articles)
        
        processed_articles = []
        for article in articles:
            processed = {
                "title": self.cleaner.clean_text(article.get("title", "")),
                "url": self.cleaner.clean_url(article.get("url", "")),
                "source": article.get("source", "Unknown"),
                "published_date": self.cleaner.parse_date(article.get("published_date", "")),
                "description": self.cleaner.clean_text(article.get("description", "")),
                "content": self.cleaner.clean_text(article.get("content", "")),
                "word_count": len(article.get("content", "").split()),
                "has_content": bool(article.get("content", ""))
            }
            
            # Filter out low-quality articles
            if self._is_valid_article(processed):
                processed_articles.append(processed)
        
        return processed_articles
    
    @staticmethod
    def _is_valid_article(article: Dict) -> bool:
        """Validate article quality"""
        # Must have title and URL
        if not article.get("title") or not article.get("url"):
            return False
        
        # Filter out removed/unavailable articles
        if "[Removed]" in article.get("title", ""):
            return False
        
        return True


class SECFilingPreprocessor:
    """Preprocess SEC filings (10-K and 10-Q)"""

    def __init__(self):
        self.cleaner = DataCleaner()
        # Common boilerplate patterns to remove
        self.boilerplate_patterns = [
            r'Table of Contents',
            r'UNITED STATES\s+SECURITIES AND EXCHANGE COMMISSION',
            r'Washington, D\.C\. 20549',
            r'FORM \d{1,2}-[KQ]',
            r'\(Mark One\)',
            r'Page \d+ of \d+',
            r'^\s*\d+\s*$',  # Standalone page numbers
        ]

    def process(self, sec_data: Dict) -> Dict:
        """
        Process SEC filing data

        Args:
            sec_data: Dictionary with '10-K' and/or '10-Q' keys containing filing data

        Returns:
            Processed SEC filing data with cleaned sections
        """
        if not sec_data or "error" in sec_data:
            return sec_data

        processed = {}

        # Process each filing type (10-K, 10-Q)
        for filing_type, filing_data in sec_data.items():
            if filing_type not in ['10-K', '10-Q']:
                continue

            if not filing_data or "error" in filing_data:
                processed[filing_type] = filing_data
                continue

            processed_filing = {
                "ticker": filing_data.get("ticker", ""),
                "company_name": filing_data.get("company_name", ""),
                "cik": filing_data.get("cik", ""),
                "filing_type": filing_data.get("filing_type", filing_type),
                "filing_date": filing_data.get("filing_date", ""),
                "fiscal_year": self._parse_fiscal_year(filing_data.get("filing_date", "")),
                "fiscal_period": self._get_fiscal_period(filing_type),
                "accession_number": filing_data.get("accession_number", ""),
                "filing_url": filing_data.get("filing_url", ""),
                "sections": {},
                "statistics": {}
            }

            # Process each section
            sections = filing_data.get("sections", {})
            if sections:
                for section_name, section_text in sections.items():
                    cleaned_text = self._clean_section(section_text)

                    if cleaned_text:
                        processed_filing["sections"][section_name] = cleaned_text

                        # Calculate section statistics
                        processed_filing["statistics"][section_name] = {
                            "word_count": len(cleaned_text.split()),
                            "char_count": len(cleaned_text),
                            "has_tables": self._has_tables(cleaned_text),
                            "table_count": self._count_tables(cleaned_text)
                        }

            # Overall filing statistics
            processed_filing["statistics"]["total_sections"] = len(processed_filing["sections"])
            processed_filing["statistics"]["total_words"] = sum(
                stats["word_count"]
                for stats in processed_filing["statistics"].values()
                if isinstance(stats, dict) and "word_count" in stats
            )
            processed_filing["statistics"]["total_tables"] = sum(
                stats["table_count"]
                for stats in processed_filing["statistics"].values()
                if isinstance(stats, dict) and "table_count" in stats
            )

            processed[filing_type] = processed_filing

        return processed

    def _clean_section(self, text: str) -> str:
        """Clean a section of SEC filing text"""
        if not text:
            return ""

        # Remove common boilerplate
        for pattern in self.boilerplate_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)

        # Remove excessive newlines (but preserve some structure)
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Remove leading/trailing whitespace from each line
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)

        # Remove lines that are just underscores or dashes
        text = re.sub(r'^[_\-]{3,}$', '', text, flags=re.MULTILINE)

        # Normalize spaces (but preserve table markers and structure)
        # Don't collapse multiple spaces if we're in a table
        if '##TABLE_START' not in text:
            text = re.sub(r'[ \t]+', ' ', text)

        # Clean up but preserve table markers
        text = text.strip()

        return text

    def _has_tables(self, text: str) -> bool:
        """Check if section contains tables"""
        return '##TABLE_START' in text and '##TABLE_END' in text

    def _count_tables(self, text: str) -> int:
        """Count number of tables in section"""
        return text.count('##TABLE_START')

    @staticmethod
    def _parse_fiscal_year(filing_date: str) -> int:
        """Extract fiscal year from filing date"""
        if not filing_date:
            return 0

        try:
            # Try parsing YYYY-MM-DD format
            if '-' in filing_date:
                year = int(filing_date.split('-')[0])
                return year
            # Try parsing YYYYMMDD format
            elif len(filing_date) >= 4:
                year = int(filing_date[:4])
                return year
        except:
            pass

        return 0

    @staticmethod
    def _get_fiscal_period(filing_type: str) -> str:
        """Get fiscal period based on filing type"""
        if filing_type == '10-K':
            return 'FY'  # Full Year
        elif filing_type == '10-Q':
            return 'Q'  # Quarter (specific quarter not always available)
        return 'Unknown'

    def validate_filing(self, filing_data: Dict) -> Dict[str, Any]:
        """
        Validate SEC filing data quality

        Returns:
            Dictionary with validation results
        """
        validation = {
            "is_valid": True,
            "errors": [],
            "warnings": []
        }

        # Check required fields
        required_fields = ["ticker", "filing_type", "sections"]
        for field in required_fields:
            if not filing_data.get(field):
                validation["is_valid"] = False
                validation["errors"].append(f"Missing required field: {field}")

        # Check sections content
        sections = filing_data.get("sections", {})
        if not sections:
            validation["is_valid"] = False
            validation["errors"].append("No sections found in filing")
        else:
            # Check if sections have content
            empty_sections = [name for name, text in sections.items() if not text or len(text.strip()) < 100]
            if empty_sections:
                validation["warnings"].append(f"Sections with little content: {empty_sections}")

        # Check fiscal year
        fiscal_year = filing_data.get("fiscal_year", 0)
        current_year = datetime.now().year
        if fiscal_year < 2000 or fiscal_year > current_year + 1:
            validation["warnings"].append(f"Unusual fiscal year: {fiscal_year}")

        return validation


class DataPreprocessingPipeline:
    """Main preprocessing pipeline"""

    def __init__(self):
        self.wiki_processor = WikipediaPreprocessor()
        self.news_processor = NewsPreprocessor()
        self.sec_processor = SECFilingPreprocessor()
    
    def process_company_data(self, raw_data: Dict) -> Dict:
        """
        Process all company data

        Args:
            raw_data: Raw data from acquisition pipeline

        Returns:
            Processed and validated data
        """
        logger.info(f"🔄 Processing data for: {raw_data.get('company_name')}")

        # Process Wikipedia data
        wiki_processed = self.wiki_processor.process(raw_data.get("wikipedia", {}))

        # Process news articles
        news_processed = self.news_processor.process(raw_data.get("news_articles", []))

        # Process SEC filings
        sec_processed = {}
        sec_validations = {}
        if "sec_filings" in raw_data:
            logger.info("  📄 Processing SEC filings...")
            result = self.sec_processor.process(raw_data.get("sec_filings", {}))
            # Handle case where process returns None (no SEC filings available)
            sec_processed = result if result is not None else {}

            # Validate each filing
            for filing_type, filing_data in sec_processed.items():
                if filing_data and "error" not in filing_data:
                    validation = self.sec_processor.validate_filing(filing_data)
                    sec_validations[filing_type] = validation

                    if not validation["is_valid"]:
                        logger.warning(f"  ⚠️  {filing_type} validation failed: {validation['errors']}")
                    elif validation["warnings"]:
                        logger.warning(f"  ⚠️  {filing_type} warnings: {validation['warnings']}")
                    else:
                        logger.info(f"  ✅ {filing_type} validated successfully")

        # Compile processed data
        processed_data = {
            "query": raw_data.get("query"),
            "ticker": raw_data.get("ticker"),
            "company_name": raw_data.get("company_name"),
            "cik": raw_data.get("cik"),
            "wikipedia": wiki_processed,
            "news_articles": news_processed,
            "sec_filings": sec_processed,
            "validations": {
                "sec_filings": sec_validations
            },
            "statistics": {
                "total_news_articles": len(news_processed),
                "wikipedia_word_count": wiki_processed.get("word_count", 0),
                "news_sources": list(set(article.get("source", "") for article in news_processed)),
                "date_range": self._get_date_range(news_processed),
                "sec_filings": self._get_sec_statistics(sec_processed)
            },
            "timestamp": datetime.now().isoformat()
        }

        # Save processed data
        self._save_processed_data(processed_data)

        logger.info(f"✅ Processing complete for: {raw_data.get('company_name')}")
        return processed_data
    
    @staticmethod
    def _get_date_range(articles: List[Dict]) -> Dict:
        """Get date range of articles"""
        dates = [article.get("published_date", "") for article in articles if article.get("published_date")]

        if not dates:
            return {"earliest": None, "latest": None}

        valid_dates = sorted([d for d in dates if d])
        return {
            "earliest": valid_dates[0] if valid_dates else None,
            "latest": valid_dates[-1] if valid_dates else None
        }

    @staticmethod
    def _get_sec_statistics(sec_data: Dict) -> Dict:
        """Get statistics for SEC filings"""
        stats = {
            "filings_available": [],
            "total_sections": 0,
            "total_words": 0,
            "total_tables": 0,
            "fiscal_years": []
        }

        for filing_type, filing_data in sec_data.items():
            if filing_data and "error" not in filing_data:
                stats["filings_available"].append(filing_type)

                filing_stats = filing_data.get("statistics", {})
                stats["total_sections"] += filing_stats.get("total_sections", 0)
                stats["total_words"] += filing_stats.get("total_words", 0)
                stats["total_tables"] += filing_stats.get("total_tables", 0)

                fiscal_year = filing_data.get("fiscal_year")
                if fiscal_year and fiscal_year not in stats["fiscal_years"]:
                    stats["fiscal_years"].append(fiscal_year)

        stats["fiscal_years"] = sorted(stats["fiscal_years"], reverse=True)
        return stats

    @staticmethod
    def _save_processed_data(data: Dict):
        """Save processed data to file"""
        import shutil
        os.makedirs("data/processed", exist_ok=True)
        filename = f"data/processed/{data['company_name'].replace(' ', '_')}_processed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        # Create latest.json as a copy of the most recent file for the pipeline
        latest_file = "data/processed/latest.json"
        shutil.copy2(filename, latest_file)

        logger.info(f"💾 Processed data saved to: {filename}")
        logger.info(f"💾 Latest copy created at: {latest_file}")


def main():
    """Example usage"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python data_preprocessing.py <raw_data_file.json>")
        sys.exit(1)
    
    raw_file = sys.argv[1]
    
    if os.path.exists(raw_file):
        with open(raw_file, 'r') as f:
            raw_data = json.load(f)
        
        pipeline = DataPreprocessingPipeline()
        processed_data = pipeline.process_company_data(raw_data)

        print(f"\n{'='*60}")
        print(f"Processed: {processed_data['company_name']}")
        print(f"-" * 60)
        print(f"Wikipedia Words: {processed_data['statistics']['wikipedia_word_count']}")
        print(f"News Articles: {processed_data['statistics']['total_news_articles']}")

        # Display SEC statistics
        sec_stats = processed_data['statistics'].get('sec_filings', {})
        if sec_stats.get('filings_available'):
            print(f"\nSEC Filings:")
            print(f"  Available: {', '.join(sec_stats['filings_available'])}")
            print(f"  Total Sections: {sec_stats['total_sections']}")
            print(f"  Total Words: {sec_stats['total_words']:,}")
            print(f"  Total Tables: {sec_stats['total_tables']}")
            print(f"  Fiscal Years: {sec_stats['fiscal_years']}")

        print(f"{'='*60}\n")
    else:
        print(f"File not found: {raw_file}")
        sys.exit(1)


if __name__ == "__main__":
    main()