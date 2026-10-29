FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY leadfinder ./leadfinder
RUN pip install --no-cache-dir ".[all]"
COPY app.py ./

ENV LEADFINDER_CACHE_DIR=/app/.cache
EXPOSE 8501
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
