ARG PYTHON_VERSION=3.12

FROM python:$PYTHON_VERSION-slim AS build

ENV PYTHONUNBUFFERED=1

WORKDIR /code

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl unzip gcc libpq-dev

# Separate layer so xray is cached independently of apt
RUN curl --retry 5 --retry-delay 3 -L \
    https://github.com/Gozargah/Marzban-scripts/raw/master/install_latest_xray.sh | bash

COPY ./requirements.txt /code/
ENV PIP_DEFAULT_TIMEOUT=300
RUN /usr/local/bin/pip install --no-cache-dir setuptools && \
    /usr/local/bin/pip install --no-cache-dir -r /code/requirements.txt

FROM python:$PYTHON_VERSION-slim

ENV PYTHON_LIB_PATH=/usr/local/lib/python${PYTHON_VERSION%.*}/site-packages
WORKDIR /code

COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
COPY --from=build /usr/local/share/xray /usr/local/share/xray

RUN --mount=type=cache,target=/root/.cache/pip pip install "setuptools<78"

COPY . /code

RUN ln -s /code/marzban-cli.py /usr/bin/marzban-cli \
    && chmod +x /usr/bin/marzban-cli \
    && marzban-cli completion install --shell bash

CMD ["bash", "-c", "alembic upgrade head && python main.py"]
