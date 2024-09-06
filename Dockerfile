# syntax=docker/dockerfile:1

FROM python:3.8-alpine
STOPSIGNAL SIGTERM

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

EXPOSE 5656

CMD [ "python3", "/app/Kapowarr.py" ]
