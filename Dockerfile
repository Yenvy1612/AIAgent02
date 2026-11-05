FROM node:22-alpine@sha256:fe4f6d74e20370acb04ad889077d14d0f64a9c8ea6a42bc60cddf1e844699914 AS frontend-build
WORKDIR /ui
COPY frontend/package.json ./
COPY frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim@sha256:db20d8506e2f15b6db39b40b6015ca46bae855dec6dd326d462cfe79ae972893
ARG INSTALL_RAG_MODELS=0
ARG INSTALL_ML_MODELS=0
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.lock /app/backend/requirements.lock
COPY backend/requirements-model-runtime.txt /app/backend/requirements-model-runtime.txt
COPY backend/requirements-rag.txt /app/backend/requirements-rag.txt
COPY backend/requirements-ml.txt /app/backend/requirements-ml.txt
RUN pip install --no-cache-dir --timeout 300 --retries 8 -r /app/backend/requirements.lock
RUN pip install --no-cache-dir --timeout 300 --retries 8 -r /app/backend/requirements-model-runtime.txt
RUN if [ "$INSTALL_ML_MODELS" = "1" ]; then pip install --no-cache-dir --timeout 300 --retries 8 -r /app/backend/requirements-ml.txt; fi
# The default CPU build avoids several GB of CUDA libraries; docker-compose.gpu.yml machines set a CUDA index.
RUN if [ "$INSTALL_RAG_MODELS" = "1" ]; then pip install --no-cache-dir --timeout 300 --retries 8 --index-url "$TORCH_INDEX_URL" torch==2.15.0 && pip install --no-cache-dir --timeout 300 --retries 8 -r /app/backend/requirements-rag.txt; fi
COPY backend/ /app/backend/
COPY data/ /app/data/
COPY kb_manifest/ /app/kb_manifest/
COPY evaluation/safety/safety_training_data.json /app/evaluation/safety/safety_training_data.json
COPY scripts/ /app/scripts/
COPY models/ /app/models/
COPY --from=frontend-build /ui/dist /app/frontend/dist
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
