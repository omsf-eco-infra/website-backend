FROM public.ecr.aws/docker/library/python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY src /app/src

RUN pip install --no-cache-dir /app

COPY examples/containers/website-backend-example-worker/worker.py /app/worker.py

CMD ["python", "/app/worker.py"]
