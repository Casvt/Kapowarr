FROM lsiobase/debian:bookworm

STOPSIGNAL SIGTERM

RUN \
  apt-get update \
  && apt-get install -y --no-install-recommends \
  python3 \
  python3-pip \
  sqlite3 \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --upgrade pip --break-system-packages

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data

EXPOSE 5656

ENV TZ=UTC

RUN \
  mkdir -p /etc/services.d/kapowarr \
  && echo "#!/usr/bin/with-contenv bash\nexec python3 /app/Kapowarr.py --DatabaseFolder /data/db" \
  > /etc/services.d/kapowarr/run \
  && chmod +x /etc/services.d/kapowarr/run
