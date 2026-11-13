FROM python:3.12-slim

# g++ is only needed to compile the C++ engine
RUN apt-get update && apt-get install -y --no-install-recommends g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) Python packages first. This layer is only rebuilt when requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) Compile the C++ engine for THIS image's Python.
COPY cpp_core cpp_core
RUN cd cpp_core && g++ -O3 -shared -std=c++17 -fPIC \
    -I"$(python -c 'import sysconfig; print(sysconfig.get_paths()["include"])')" \
    -I"$(python -c 'import pybind11; print(pybind11.get_include())')" \
    bindings.cpp matcher.cpp \
    -o "matcher_module$(python -c 'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))')"

# 3) The app itself. It changes most often, so it goes last.
COPY backend backend
COPY frontend frontend

# Hosts like Render tell the app which port to use through $PORT.
ENV PORT=10000
EXPOSE 10000
  CMD ["sh", "-c", "exec gunicorn --chdir backend -b 0.0.0.0:${PORT} --workers 2 --timeout 30 app:app"]