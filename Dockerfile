FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV MEMORY_OS_ROOT=/data/memory
EXPOSE 8765
CMD ["uvicorn", "memory_os.server:app", "--host", "0.0.0.0", "--port", "8765"]
