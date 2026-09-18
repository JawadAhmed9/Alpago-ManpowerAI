FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Windows checkouts of this repo can strip start.sh's executable bit (git on
# Windows doesn't track the Unix +x bit) or leave CRLF line endings behind --
# either one makes `./start.sh` fail to exec before it prints a single log
# line, which is exactly the silent "Exited with status 128" symptom. Strip
# CRLFs and force +x here so the image never depends on the checkout being
# clean, and invoke it via `sh` explicitly so a missing +x bit can't matter.
RUN sed -i 's/\r$//' start.sh && chmod +x start.sh

RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /srv
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["/bin/sh", "start.sh"]
