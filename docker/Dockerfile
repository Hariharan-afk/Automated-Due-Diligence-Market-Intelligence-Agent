FROM apache/airflow:2.10.4-python3.11

USER root
# Install system dependencies
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
         build-essential \
         git \
  && apt-get autoremove -yqq --purge \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

USER airflow

# Copy requirements and install
COPY composer_requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
