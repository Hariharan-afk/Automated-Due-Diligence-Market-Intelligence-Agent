-- filings metadata
CREATE TABLE IF NOT EXISTS filings (
  cik            VARCHAR(10) NOT NULL,
  accession      VARCHAR(32) NOT NULL,
  form           VARCHAR(16) NOT NULL,
  filing_date    DATE NOT NULL,
  report_date    DATE,
  primary_doc_url TEXT,
  PRIMARY KEY (cik, accession)
);

-- narrative sections (optional to store in DB; files live on disk)
CREATE TABLE IF NOT EXISTS sections (
  cik           VARCHAR(10) NOT NULL,
  accession     VARCHAR(32) NOT NULL,
  section_name  TEXT NOT NULL,
  chunk_id      INTEGER NOT NULL,
  start_char    INTEGER,
  end_char      INTEGER,
  text_path     TEXT,
  PRIMARY KEY (cik, accession, section_name, chunk_id)
);

-- XBRL facts (deterministic numbers)
CREATE TABLE IF NOT EXISTS facts (
  cik           VARCHAR(10) NOT NULL,
  accession     VARCHAR(32) NOT NULL,
  concept       TEXT NOT NULL,
  period_start  DATE,
  period_end    DATE,
  value         NUMERIC,
  unit          TEXT,
  decimals      INTEGER,
  dims          JSONB,
  PRIMARY KEY (cik, accession, concept, period_start, period_end)
);
