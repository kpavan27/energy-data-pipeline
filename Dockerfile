FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e .
COPY configs ./configs
COPY dbt ./dbt
CMD ["energy-pipeline", "run"]
