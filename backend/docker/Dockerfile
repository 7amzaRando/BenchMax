# BenchMax combined sandbox — all code-execution runtimes in one image
# HumanEval, BigCodeBench, LiveCodeBench, LiveBench (coding), Aider Polyglot (6 langs)
#
# Build: docker build -t benchmax-sandbox backend/docker/
# Run:   docker run --rm -v /path/to/workspace:/workspace benchmax-sandbox python --version

FROM python:3.11-slim

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# ── System deps (shared by multiple runtimes) ──────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # GCC / G++ (C/C++ compilation for Aider Polyglot C++)
    g++ gcc make wget curl ca-certificates gnupg \
    # Java (Aider Polyglot Java)
    default-jdk-headless \
    # Tesseract (BigCodeBench Python packages need it)
    tesseract-ocr tesseract-ocr-eng \
    # OpenCV system deps (BigCodeBench)
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev \
    # Utilities
    git unzip xz-utils \
    && rm -rf /var/lib/apt/lists/*

# ── Node.js 20 (Aider Polyglot JavaScript) ────────────────────────
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g jest @babel/core @babel/preset-env babel-jest

# ── Go 1.22 (Aider Polyglot Go) ──────────────────────────────────
RUN wget -q https://go.dev/dl/go1.22.5.linux-amd64.tar.gz -O /tmp/go.tar.gz \
    && tar -C /usr/local -xzf /tmp/go.tar.gz \
    && rm /tmp/go.tar.gz
ENV PATH="/usr/local/go/bin:${PATH}"

# ── Rust 1.75 (Aider Polyglot Rust) ──────────────────────────────
ENV CARGO_HOME=/opt/cargo
ENV RUSTUP_HOME=/opt/rustup
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain 1.75.0 --no-modify-path \
    && chmod -R a+rx /opt/cargo /opt/rustup
ENV PATH="/opt/cargo/bin:${PATH}"

# ── Python packages (BigCodeBench + LiveCodeBench) ────────────────
RUN pip install --no-cache-dir \
    pandas numpy matplotlib scikit-learn scipy seaborn \
    requests nltk beautifulsoup4 python-dateutil pytz Pillow \
    statsmodels sympy regex lxml psutil cryptography rsa flask \
    openpyxl wordcloud textblob xmltodict geopy faker pyyaml chardet \
    opencv-python django flask-mail folium xlwt mechanize python-docx \
    texttable wikipedia flask-restful flask-login flask-wtf holidays \
    scikit-image geopandas shapely librosa soundfile python-http-client \
    sendgrid blake3 natsort keras prettytable pycryptodome pyquery \
    gensim python-Levenshtein wordninja pytesseract \
    && rm -rf /tmp/*

ENV MPLBACKEND=Agg

# ── Catch2 header (Aider Polyglot C++) ────────────────────────────
RUN mkdir -p /usr/local/include/catch2 \
    && wget -q https://raw.githubusercontent.com/catchorg/Catch2/v2.13.10/single_include/catch2/catch.hpp \
       -O /usr/local/include/catch2/catch.hpp

# ── JUnit + AssertJ JARs (Aider Polyglot Java) ───────────────────
RUN mkdir -p /opt/jars \
    && wget -q https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/1.11.4/junit-platform-console-standalone-1.11.4.jar \
       -O /opt/jars/junit-platform-console-standalone-1.11.4.jar \
    && wget -q https://repo1.maven.org/maven2/org/assertj/assertj-core/3.27.3/assertj-core-3.27.3.jar \
       -O /opt/jars/assertj-core-3.27.3.jar

# ── Copy container runner script ──────────────────────────────────
COPY backend/sandbox/container_runner.py /opt/benchmax/container_runner.py

# ── Non-root user for sandbox isolation ───────────────────────────
RUN mkdir -p /workspace && useradd -m -u 1000 appuser && chown -R appuser:appuser /workspace
WORKDIR /workspace
USER appuser

# Default: show versions of all installed runtimes
CMD ["python", "-c", "import sys; print(f'Python {sys.version}'); \
     import subprocess; \
     r = subprocess.run(['node', '--version'], capture_output=True, text=True); print(f'Node {r.stdout.strip()}'); \
     r = subprocess.run(['go', 'version'], capture_output=True, text=True); print(f'{r.stdout.strip()}'); \
     r = subprocess.run(['rustc', '--version'], capture_output=True, text=True); print(f'{r.stdout.strip()}'); \
     r = subprocess.run(['gcc', '--version'], capture_output=True, text=True); print(f'GCC {r.stdout.splitlines()[0]}'); \
     r = subprocess.run(['java', '--version'], capture_output=True, text=True); print(f'{r.stdout.splitlines()[0]}')"]
