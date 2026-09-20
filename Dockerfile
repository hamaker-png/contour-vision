FROM python:3.12-slim-bookworm AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends g++ cmake make \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-production.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --only-binary=:all: -r requirements-production.txt
COPY backend/vendor /build/backend/vendor
RUN cmake -S backend/vendor -B /tmp/cimg-build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /tmp/cimg-build --parallel 2

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" CONTOUR_PUBLIC=1 PORT=8000 \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 contour && useradd --uid 10001 --gid contour --no-create-home contour
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY backend ./backend
COPY --from=builder /build/backend/vendor/bin/libcontour_cimg.so ./backend/vendor/bin/libcontour_cimg.so
COPY static ./static
COPY examples ./examples
RUN python -c "import cv2,numpy,zxingcpp; from backend.cimg_native import library; library()"
USER contour
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/api/health',timeout=3).read()"
CMD ["python", "-m", "backend.serve"]
