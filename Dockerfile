# Buster slim python 3.7 base image.
FROM python:3.7-slim-buster as base

RUN groupadd -r geoadmin && useradd -r -s /bin/false -g geoadmin geoadmin


# HERE : install relevant packages
# NOTE: curl is required for vhost health check, could be removed when moving to k8s
RUN apt-get update \
    && apt-get install -y gcc python3-dev libpq-dev curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install pipenv \
    && pipenv --version

COPY Pipfile* /tmp/
RUN cd /tmp && \
    pipenv install --system --deploy --ignore-pipfile

WORKDIR /service-wmts
COPY --chown=geoadmin:geoadmin ./app               /service-wmts/app/
COPY --chown=geoadmin:geoadmin ./config/           /service-wmts/config/
COPY --chown=geoadmin:geoadmin openapi.yml wsgi.py /service-wmts/

ARG GIT_HASH=unknown
ARG GIT_BRANCH=unknown
ARG GIT_DIRTY=""
ARG VERSION=unknown
ARG AUTHOR=unknown
ARG WMTS_PORT=9000

LABEL git.hash=$GIT_HASH
LABEL git.branch=$GIT_BRANCH
LABEL git.dirty="$GIT_DIRTY"
LABEL version=$VERSION
LABEL author=$AUTHOR

# Overwrite the version.py from source with the actual version
RUN echo "APP_VERSION = '$VERSION'" > /service-wmts/app/version.py

# ##################################################
# Testing target
FROM base as unittest

LABEL target=unittest

COPY --chown=geoadmin:geoadmin ./scripts /scripts/
COPY --chown=geoadmin:geoadmin ./tests   /service-wmts/tests/

RUN cd /tmp && \
    pipenv install --system --deploy --ignore-pipfile --dev

USER geoadmin

EXPOSE $WMTS_PORT

# Use a real WSGI server
ENTRYPOINT ["python3", "wsgi.py"]

# ##################################################
# Production target
FROM base as production

LABEL target=production

USER geoadmin

EXPOSE $WMTS_PORT

# Use a real WSGI server
ENTRYPOINT ["python3", "wsgi.py"]