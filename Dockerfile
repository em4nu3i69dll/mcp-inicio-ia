FROM python:3.13-slim-bookworm@sha256:281d39ff02e3b389401586134ff9e6572954687822a58055ec07a60ded4e0b7f
WORKDIR /app
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt
COPY mcp_inicio ./mcp_inicio
RUN pip install --no-cache-dir --no-deps . && mkdir /espacio && chown 1000:1000 /espacio
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
USER 1000:1000
ENTRYPOINT ["python", "-m", "mcp_inicio", "--base", "/espacio"]
CMD ["servidor"]
