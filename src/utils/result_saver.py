"""
Result Saver - Save analysis results to Markdown and HTML
"""
import os
from datetime import datetime
from typing import Dict, Any

def save_result(query: str, result: Dict[str, Any], results_dir: str = "results"):
    """
    Save analysis result to both Markdown and HTML formats
    
    Args:
        query: User query
        result: Result dictionary with answer, sources, confidence, etc.
        results_dir: Directory to save results
    """
    # Create results directory if it doesn't exist
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"response_{timestamp}"
    
    # Save Markdown
    md_path = os.path.join(results_dir, f"{base_filename}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(_generate_markdown(query, result))
    
    # Save HTML
    html_path = os.path.join(results_dir, f"{base_filename}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(_generate_html(query, result))
    
    return md_path, html_path

def _generate_markdown(query: str, result: Dict[str, Any]) -> str:
    """Generate Markdown content"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    content = f"""# Market Due Diligence Report

**Generated:** {timestamp}  
**Query:** {query}

---

## Answer

{result.get('answer', 'No answer generated')}

---

## Confidence Score

**{result.get('confidence', 0.0):.2f}** / 1.0

## Hallucination Score

**{result.get('hallucination_score', 0.0):.2f}** / 1.0  
*(0.0 = No hallucinations, 1.0 = Severe hallucinations)*

---

## Sources

"""
    
    sources = result.get('sources', [])
    if sources:
        for i, source in enumerate(sources, 1):
            content += f"\n### Source {i}\n\n"
            content += f"- **Company:** {source.get('company', 'Unknown')}\n"
            content += f"- **Type:** {source.get('source_type', 'Unknown')}\n"
            content += f"- **Date:** {source.get('date', 'Unknown')}\n"
            content += f"- **Ticker:** {source.get('ticker', 'N/A')}\n"
    else:
        content += "\nNo sources available.\n"
    
    # Add metadata
    content += f"\n---\n\n## Metadata\n\n"
    content += f"- **Evaluation:** {result.get('evaluation', {}).get('decision', 'N/A')}\n"
    content += f"- **Iterations:** {result.get('iteration', 0)}\n"
    
    return content

def _generate_html(query: str, result: Dict[str, Any]) -> str:
    """Generate HTML content with styling"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    confidence = result.get('confidence', 0.0)
    hallucination = result.get('hallucination_score', 0.0)
    
    # Determine confidence color
    if confidence >= 0.7:
        conf_color = "#22c55e"  # Green
    elif confidence >= 0.4:
        conf_color = "#f59e0b"  # Orange
    else:
        conf_color = "#ef4444"  # Red
    
    # Determine hallucination color (inverted - low is good)
    if hallucination <= 0.3:
        hall_color = "#22c55e"  # Green
    elif hallucination <= 0.6:
        hall_color = "#f59e0b"  # Orange
    else:
        hall_color = "#ef4444"  # Red
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Due Diligence Report - {timestamp}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }}
        
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2em;
            margin-bottom: 10px;
        }}
        
        .header .meta {{
            opacity: 0.9;
            font-size: 0.9em;
        }}
        
        .content {{
            padding: 40px;
        }}
        
        .query-box {{
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 20px;
            margin-bottom: 30px;
            border-radius: 4px;
        }}
        
        .query-box h2 {{
            color: #667eea;
            margin-bottom: 10px;
            font-size: 1.2em;
        }}
        
        .answer {{
            margin-bottom: 30px;
            line-height: 1.8;
        }}
        
        .answer h2 {{
            color: #333;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e5e7eb;
        }}
        
        .confidence {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
            text-align: center;
        }}
        
        .confidence h3 {{
            margin-bottom: 15px;
            color: #555;
        }}
        
        .confidence-bar {{
            background: #e5e7eb;
            height: 30px;
            border-radius: 15px;
            overflow: hidden;
            position: relative;
        }}
        
        .confidence-fill {{
            background: {conf_color};
            height: 100%;
            transition: width 0.5s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }}
        
        .sources {{
            margin-top: 30px;
        }}
        
        .sources h2 {{
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e5e7eb;
        }}
        
        .source-card {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 15px;
            border-left: 4px solid #667eea;
        }}
        
        .source-card h3 {{
            color: #667eea;
            margin-bottom: 10px;
        }}
        
        .source-card .detail {{
            margin: 5px 0;
            color: #666;
        }}
        
        .source-card .detail strong {{
            color: #333;
        }}
        
        .footer {{
            background: #f8f9fa;
            padding: 20px 40px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Market Due Diligence Report</h1>
            <div class="meta">Generated: {timestamp}</div>
        </div>
        
        <div class="content">
            <div class="query-box">
                <h2>Your Query</h2>
                <p>{query}</p>
            </div>
            
            <div class="answer">
                <h2>Analysis</h2>
                <p>{result.get('answer', 'No answer generated').replace(chr(10), '<br>')}</p>
            </div>
            
            <div class="confidence">
                <h3>Confidence Score</h3>
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: {confidence * 100}%; background: {conf_color}">
                        {confidence:.2f}
                    </div>
                </div>
            </div>
            
            <div class="confidence">
                <h3>Hallucination Score</h3>
                <p style="font-size: 0.9em; color: #666; margin-bottom: 10px;">0.0 = No hallucinations, 1.0 = Severe hallucinations</p>
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: {hallucination * 100}%; background: {hall_color}">
                        {hallucination:.2f}
                    </div>
                </div>
            </div>
            
            <div class="sources">
                <h2>Sources ({len(result.get('sources', []))})</h2>
"""
    
    sources = result.get('sources', [])
    if sources:
        for i, source in enumerate(sources, 1):
            html += f"""
                <div class="source-card">
                    <h3>Source {i}</h3>
                    <div class="detail"><strong>Company:</strong> {source.get('company', 'Unknown')}</div>
                    <div class="detail"><strong>Type:</strong> {source.get('source_type', 'Unknown')}</div>
                    <div class="detail"><strong>Date:</strong> {source.get('date', 'Unknown')}</div>
                    <div class="detail"><strong>Ticker:</strong> {source.get('ticker', 'N/A')}</div>
                </div>
"""
    else:
        html += "<p>No sources available.</p>"
    
    html += f"""
            </div>
        </div>
        
        <div class="footer">
            <p>Powered by 5-Agent LangGraph Architecture | Iterations: {result.get('iteration', 0)}</p>
        </div>
    </div>
</body>
</html>
"""
    
    return html
