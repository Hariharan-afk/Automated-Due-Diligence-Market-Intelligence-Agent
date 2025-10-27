"""
Utility to convert between ticker file formats (JSON <-> CSV) - FINAL VERSION
"""

import json
import pandas as pd
import argparse
import os
import sys


def json_to_csv(json_file: str, csv_file: str):
    """Convert JSON ticker file to CSV format"""
    print(f"📥 Reading JSON file: {json_file}")
    
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Convert to list of records
    records = []
    for key, value in data.items():
        records.append({
            'ticker': value.get('ticker', ''),
            'title': value.get('title', ''),
            'cik_str': value.get('cik_str', ''),
            'index': key
        })
    
    # Create DataFrame
    df = pd.DataFrame(records)
    
    # Clean up - remove empty tickers
    df = df[df['ticker'].notna() & (df['ticker'] != '')]
    
    # Sort by ticker
    df = df.sort_values('ticker')
    
    # Save to CSV
    df.to_csv(csv_file, index=False)
    
    print(f"✅ Converted {len(df)} companies to CSV: {csv_file}")
    print(f"\nSample data:")
    print(df.head(10)[['ticker', 'title']].to_string(index=False))


def csv_to_json(csv_file: str, json_file: str):
    """Convert CSV ticker file to JSON format"""
    print(f"📥 Reading CSV file: {csv_file}")
    
    df = pd.read_csv(csv_file)
    
    # Convert to JSON format
    json_data = {}
    for idx, row in df.iterrows():
        json_data[str(idx)] = {
            'cik_str': int(row['cik_str']) if 'cik_str' in row and pd.notna(row['cik_str']) else 0,
            'ticker': str(row['ticker']) if pd.notna(row['ticker']) else '',
            'title': str(row['title']) if pd.notna(row['title']) else ''
        }
    
    # Save to JSON
    with open(json_file, 'w') as f:
        json.dump(json_data, f, indent=2)
    
    print(f"✅ Converted {len(json_data)} companies to JSON: {json_file}")


def analyze_ticker_file(file_path: str):
    """Analyze ticker file and show statistics"""
    print(f"\n{'='*60}")
    print(f"ANALYZING: {file_path}")
    print(f"{'='*60}\n")
    
    # Determine file type
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.json':
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        records = [value for key, value in data.items()]
        df = pd.DataFrame(records)
        
    elif ext == '.csv':
        df = pd.read_csv(file_path)
    else:
        print(f"❌ Unsupported file format: {ext}")
        return
    
    # Statistics
    print(f"📊 Total Companies: {len(df)}")
    
    if 'ticker' in df.columns:
        valid_tickers = df[df['ticker'].notna() & (df['ticker'] != '')]
        print(f"📊 Valid Tickers: {len(valid_tickers)}")
        print(f"📊 Missing Tickers: {len(df) - len(valid_tickers)}")
    
    if 'title' in df.columns:
        print(f"\n📋 Sample Companies:")
        sample = df[['ticker', 'title']].head(10) if 'ticker' in df.columns else df[['title']].head(10)
        print(sample.to_string(index=False))
    
    # Top tickers by letter
    if 'ticker' in df.columns:
        df_valid = df[df['ticker'].notna() & (df['ticker'] != '')]
        if not df_valid.empty:
            df_valid['first_letter'] = df_valid['ticker'].str[0]
            letter_counts = df_valid['first_letter'].value_counts().head(10)
            print(f"\n📊 Top Starting Letters:")
            for letter, count in letter_counts.items():
                print(f"  {letter}: {count} companies")
    
    print(f"\n{'='*60}\n")


def download_sec_tickers(output_file: str = "data/company_tickers.json"):
    """Download latest company tickers from SEC"""
    import requests
    
    print("🌐 Downloading company tickers from SEC.gov...")
    
    url = "https://www.sec.gov/files/company_tickers.json"
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; CompanyResearchPipeline/1.0)'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Save to file
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✅ Downloaded {len(data)} companies to: {output_file}")
        
        # Show sample
        sample_keys = list(data.keys())[:5]
        print("\nSample data:")
        for key in sample_keys:
            company = data[key]
            print(f"  {company['ticker']}: {company['title']}")
        
    except Exception as e:
        print(f"❌ Error downloading: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert and manage company ticker files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert JSON to CSV
  python convert_ticker_format.py --json2csv data/company_tickers.json data/company_tickers.csv
  
  # Convert CSV to JSON
  python convert_ticker_format.py --csv2json data/company_tickers.csv data/company_tickers.json
  
  # Analyze a ticker file
  python convert_ticker_format.py --analyze data/company_tickers.json
  
  # Download latest from SEC
  python convert_ticker_format.py --download
        """
    )
    
    parser.add_argument('--json2csv', nargs=2, metavar=('INPUT_JSON', 'OUTPUT_CSV'),
                       help='Convert JSON to CSV')
    parser.add_argument('--csv2json', nargs=2, metavar=('INPUT_CSV', 'OUTPUT_JSON'),
                       help='Convert CSV to JSON')
    parser.add_argument('--analyze', metavar='FILE',
                       help='Analyze ticker file')
    parser.add_argument('--download', action='store_true',
                       help='Download latest tickers from SEC.gov')
    
    args = parser.parse_args()
    
    if args.json2csv:
        json_file, csv_file = args.json2csv
        if not os.path.exists(json_file):
            print(f"❌ File not found: {json_file}")
            sys.exit(1)
        json_to_csv(json_file, csv_file)
    
    elif args.csv2json:
        csv_file, json_file = args.csv2json
        if not os.path.exists(csv_file):
            print(f"❌ File not found: {csv_file}")
            sys.exit(1)
        csv_to_json(csv_file, json_file)
    
    elif args.analyze:
        if not os.path.exists(args.analyze):
            print(f"❌ File not found: {args.analyze}")
            sys.exit(1)
        analyze_ticker_file(args.analyze)
    
    elif args.download:
        download_sec_tickers()
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()