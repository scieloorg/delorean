FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt setup.py setup.cfg README.rst CHANGES.txt MANIFEST.in ./
COPY delorean ./delorean

RUN python -m pip install --upgrade pip wheel \
    && python -m pip install "setuptools<81" \
    && python -m pip install -r requirements.txt \
    && python -m pip install -e ".[test]"

COPY development.ini production.ini runtests.sh ./

EXPOSE 6543

CMD ["pserve", "production.ini", "--reload"]
