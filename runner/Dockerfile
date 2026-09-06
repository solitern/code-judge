FROM python:3.13-slim

# GCC and libc development files.  util-linux provides unshare/setpriv.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libc6-dev \
        util-linux \
        && rm -rf /var/lib/apt/lists/*

# This tiny static PID-1 supervisor enters the per-case root, irreversibly
# drops namespace capabilities, then runs and reaps the student process.
COPY sandbox_launcher.c /tmp/sandbox_launcher.c
RUN gcc -std=c11 -O2 -static -s \
        -o /usr/local/bin/sandbox-launcher /tmp/sandbox_launcher.c \
        && rm /tmp/sandbox_launcher.c

# Create an unprivileged user.  The service runs as this user; student
# programs also run as this user (mapped to root only inside a user
# namespace when unshare is available, but never root on the host).
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin runner

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Writable tmpfs for run data; root filesystem can remain read-only.
RUN mkdir -p /tmp/judge-runner && chown runner:runner /tmp/judge-runner

USER runner
EXPOSE 8100
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/health', timeout=3)" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
