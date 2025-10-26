# 🏢 Company Research Data Pipeline

**MLOps Course Project - Automated Due Diligence Agent**

This is my MLOps data pipeline project that automatically researches companies by pulling data from Wikipedia and news sources, cleaning it up, and checking for quality and bias.

---

## 🎯 What This Does

I built a pipeline that takes a company name (like "Apple") and automatically:

- Grabs their Wikipedia page and full company info
- Fetches 20 recent news articles about them
- Cleans up all the messy data (removes HTML, fixes dates, etc.)
- Checks if the data is good quality (gives it a score out of 100)
- Analyzes if there's any bias in the news sources
- Saves everything to a database

Basically automates the boring research work!

---

## 🏗️ How It Works

```
You type: "Apple"
    ↓
Pipeline finds: Apple Inc. (ticker: AAPL)
    ↓
Downloads Wikipedia article + 20 news articles
    ↓
Cleans everything up
    ↓
Validates quality (scored 100/100 for Apple!)
    ↓
Checks for bias (fairness score 76.5/100)
    ↓
Stores in database
    ↓
Done! 🎉
```

Takes about 30 seconds total.

---

## 📁 Project Files

```
src/                      # Main code
├── data_acquisition.py   # Downloads Wikipedia + news
├── data_preprocessing.py # Cleans the data
├── schema_validator.py   # Quality checks
├── bias_detector.py      # Bias analysis
└── db_manager.py         # Database stuff

dags/                     # Airflow orchestration
└── company_research_dag.py

scripts/                  # Helper scripts
├── run_pipeline.py       # Main runner
└── convert_ticker_format.py

tests/                    # Unit tests
data/                     # Data folder
config/                   # Settings
```

---

## 🚀 How to Run

### Quick Start

```bash
# Install stuff
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Run for any company
python scripts/run_pipeline.py --company "Apple"
```

That's it! Results go into `data/` folder.

### Using Docker (for Airflow UI)

```bash
# Start Airflow
docker-compose -f docker-compose-airflow.yml up -d

# Access at: http://localhost:8080
# Login: saumith / saumith
```

---

## 📊 What I Got

Testing with Apple Inc:
- ✅ Quality Score: 100/100
- ✅ Fairness Score: 76.5/100  
- ✅ 20 news articles from 8 different sources
- ✅ Full Wikipedia article (15,000+ words)
- ✅ Everything stored in SQLite database

---

## 🧪 Testing

```bash
# Run tests
pytest tests/ -v

# Check coverage
pytest --cov=src tests/
```

Got 90%+ test coverage!

---

## 🎓 Course Requirements

This project covers all the MLOps requirements:

- ✅ Data acquisition from APIs
- ✅ Data preprocessing and cleaning
- ✅ Schema validation
- ✅ Anomaly detection  
- ✅ Bias detection with data slicing
- ✅ Pipeline orchestration (Airflow DAG with 9 tasks)
- ✅ Data versioning (DVC)
- ✅ Unit tests
- ✅ Logging and monitoring
- ✅ Docker deployment

---

## 🔧 Tech Stack

- **Python 3.10+** - Main language
- **Apache Airflow** - Pipeline orchestration
- **DVC** - Data version control
- **SQLite** - Database
- **Docker** - Deployment
- **pytest** - Testing
- **pandas** - Data processing
- **Wikipedia-API** - Company info
- **NewsAPI** - News articles

---

## 📝 Notes

- Using NewsAPI free tier (100 requests/day)
- Supports 10,142 US companies
- Sequential executor for simplicity (works with SQLite)
- All bias metrics calculated using standard formulas (HHI, Gini coefficient)

---

## 🐛 Common Issues

**Can't find company?**
- Check `data/company_tickers.json` for ticker
- Try using ticker instead (e.g., "AAPL" instead of "Apple")

**Airflow not starting?**
- Make sure Docker is running
- Wait 60 seconds after starting
- Check logs: `docker-compose -f docker-compose-airflow.yml logs`

---

## 📄 Files Not Included

Some large files aren't uploaded to keep repo small:
- Generated data files (tracked by DVC instead)
- Virtual environment
- Airflow runtime files  
- Log files

If you need the data, use DVC to pull it.

---
