-- database/init_db.sql
-- PostgreSQL schema for Researcher Agent metadata

-- NOTE: Do not include \c command here - connection is handled by Python code
-- The Python script already connects to researcher_db before executing this

-- Company metadata table
CREATE TABLE IF NOT EXISTS company_metadata (
    company_ticker VARCHAR(10) PRIMARY KEY,
    company_cik VARCHAR(10) NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Filings table
CREATE TABLE IF NOT EXISTS filings (
    id SERIAL PRIMARY KEY,
    company_ticker VARCHAR(10) NOT NULL REFERENCES company_metadata(company_ticker),
    filing_type VARCHAR(10) NOT NULL,
    filing_date DATE NOT NULL,
    fiscal_period_end DATE,
    accession_number VARCHAR(50) UNIQUE NOT NULL,
    sections_extracted TEXT[],
    last_fetched TIMESTAMP NOT NULL,
    chunk_count INTEGER DEFAULT 0,
    indexed_in_vector_db BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_filings_ticker ON filings(company_ticker);
CREATE INDEX IF NOT EXISTS idx_filings_type_date ON filings(filing_type, filing_date DESC);
CREATE INDEX IF NOT EXISTS idx_filings_accession ON filings(accession_number);
CREATE INDEX IF NOT EXISTS idx_filings_indexed ON filings(indexed_in_vector_db);

-- Update trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_company_metadata_updated_at BEFORE UPDATE ON company_metadata
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_filings_updated_at BEFORE UPDATE ON filings
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Comments
COMMENT ON TABLE company_metadata IS 'Stores basic metadata about tracked companies';
COMMENT ON TABLE filings IS 'Stores metadata about processed SEC filings';
COMMENT ON COLUMN filings.sections_extracted IS 'Array of section codes that were extracted (e.g., {1, 1A, 7, 8})';
COMMENT ON COLUMN filings.chunk_count IS 'Total number of chunks created from this filing';
COMMENT ON COLUMN filings.indexed_in_vector_db IS 'Whether chunks have been indexed in Qdrant';
