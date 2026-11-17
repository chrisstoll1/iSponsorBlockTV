# syntax=docker/dockerfile:1
FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src iSPBTV_docker=True iSPBTV_data_dir=/app/data \
    HOME=/tmp TERM=xterm-256color COLORTERM=truecolor
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY src /app/src
COPY LICENSE.md /app/LICENSE.md
RUN mkdir -p /app/data && chown 568:568 /app/data
USER 568:568
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os,time; assert time.time()-os.stat('/tmp/isponsorblocktv-health').st_mtime < 30"
ENTRYPOINT ["python", "-u", "/app/src/main.py"]
