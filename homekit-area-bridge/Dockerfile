ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.21
FROM ${BUILD_FROM}

WORKDIR /

COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

COPY app/ /app/
COPY frontend/ /frontend/
COPY run.sh /

RUN chmod a+x /run.sh

CMD ["/run.sh"]
