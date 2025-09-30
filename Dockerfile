# Use linuxserver's base image (alpine + s6 overlay)  
FROM lsiobase/alpine:3.22

# Metadata / labels (optional)  
LABEL maintainer="you@example.com"
ARG VERSION="latest"

# Install build / runtime dependencies  
RUN \
  apk add --no-cache \
    python3 \
    py3-pip \
    git \
    gcompat \
    && pip3 install --break-system-packages --no-cache-dir --upgrade pip

# Set working directory
WORKDIR /app

# Clone Kapowarr repository for remote build
#ARG KAPOWARR_REPO="https://github.com/Casvt/Kapowarr.git"
#ARG KAPOWARR_BRANCH="main"
#RUN git clone --depth 1 --branch "${KAPOWARR_BRANCH}" "${KAPOWARR_REPO}" .

# Clone local files for local build
COPY requirements.txt requirements.txt
COPY . .

# Install Python dependencies
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt

# Ensure proper permissions for the abc user (linuxserver standard)
RUN \
  chown -R abc:abc /app \
  && chmod -R 755 /app

# Expose the web port (Kapowarr default is 5656)  
EXPOSE 5656

# Environment variables (PUID / PGID pattern used by linuxserver)  
ENV PUID=1000 \
    PGID=1000 \
    TZ=UTC

# Switch to non-root user (lsio pattern)
# (the baseimage-alpine provides an 'abc' user/group)
USER abc

# Entry point / command
CMD ["python3", "Kapowarr.py"]
