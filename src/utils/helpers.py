import json
import re

def extract_json(text: str):
    """
    Robustly extract JSON object or array from text.
    Handles markdown code blocks and conversational filler.
    """
    text = text.strip()
    
    # Try to find JSON block within markdown
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1)
    
    # Find first opening brace/bracket
    start_brace = text.find('{')
    start_bracket = text.find('[')
    
    if start_brace == -1 and start_bracket == -1:
        raise ValueError("No JSON found in response")
        
    # Determine which comes first
    if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
        # It's an object
        start = start_brace
        end_char = '}'
    else:
        # It's an array
        start = start_bracket
        end_char = ']'
        
    # Find corresponding closing brace/bracket
    # We need to balance them or just find the last one
    # Simple approach: find the last occurrence of the closing char
    end = text.rfind(end_char)
    
    if end == -1 or end < start:
        raise ValueError("Malformed JSON: No closing brace/bracket found")
        
    json_str = text[start:end+1]
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # Try to fix common issues like trailing commas? 
        # For now just re-raise
        raise e
