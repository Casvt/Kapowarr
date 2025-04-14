# syntax=docker/dockerfile:1

FROM python:3.8-slim-buster
STOPSIGNAL SIGTERM

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod -R 755 /app

EXPOSE 5656

CMD [ "python3", "/app/Kapowarr.py" ]
