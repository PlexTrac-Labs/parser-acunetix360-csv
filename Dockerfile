FROM python:3.11-slim

WORKDIR /script

COPY . /script

RUN pip install --no-cache-dir -r requirements.txt
