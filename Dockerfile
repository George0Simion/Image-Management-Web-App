FROM python:3.9-alpine

ENV PYTHONUNBUFFERED=1

WORKDIR /server

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "server.py"]

EXPOSE 5000