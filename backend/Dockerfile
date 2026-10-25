FROM python:3.11-slim
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY pyproject.toml ./
COPY requirements-ml.lock ./
ARG INSTALL_ML=false
RUN if [ "$INSTALL_ML" = "true" ]; then pip install --no-cache-dir -r requirements-ml.lock && python -m spacy download en_core_web_sm; fi
COPY app ./app
RUN pip install --no-cache-dir --no-deps . && useradd -m app && mkdir -p /app/data /home/app/.cache/huggingface && chown -R app:app /app /home/app/.cache
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
