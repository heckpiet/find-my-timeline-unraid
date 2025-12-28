FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better caching
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY templates/ ./templates/

RUN pip install --no-cache-dir -e .

# Session cookies and database will be mounted at runtime
VOLUME ["/root/.find-my-timeline", "/app/data"]

EXPOSE 5000

CMD ["find-my-timeline", "start"]
