FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir "."

ENV CLASSYDL_DATA_DIR=/data
VOLUME ["/data"]
EXPOSE 8420

CMD ["classydl", "web", "--host", "0.0.0.0", "--port", "8420", "--output", "/data/downloads"]
