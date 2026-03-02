FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir telethon python-dotenv aiohttp

CMD ["python", "main.py"]
