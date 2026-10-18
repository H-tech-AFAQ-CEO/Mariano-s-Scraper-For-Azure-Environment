# Browser + OS deps come from Microsoft's official Playwright image (version must match requirements.txt)
FROM mcr.microsoft.com/playwright/python:v1.49.1-noble
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY config ./config
ENV PYTHONPATH=/app/src PYTHONUNBUFFERED=1 MARIANOS_STORAGE=azure
ENTRYPOINT ["python", "-m", "marianos.cli"]
CMD ["run", "--all"]
