FROM python:3.11-slim
RUN apt-get update && apt-get install -y nano vim && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

CMD ["/bin/bash"]