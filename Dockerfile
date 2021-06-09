# Buster slim python 3.7 base image.
FROM python:3.7-slim-buster as base

RUN groupadd -r geoadmin && useradd -r -s /bin/false -g geoadmin geoadmin


# HERE : install relevant packages
RUN apt-get update \
    && apt-get install -y gcc python3-dev libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install pipenv \
    && pipenv --version

COPY Pipfile* /tmp/
RUN cd /tmp && \
    pipenv install --system --deploy --ignore-pipfile

WORKDIR /service-wmts
COPY --chown=geoadmin:geoadmin ./ /service-wmts/

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

RUN cd /tmp && \
    pipenv install --system --deploy --ignore-pipfile --dev

USER geoadmin

ENV WMTS_PORT $WMTS_PORT
EXPOSE $WMTS_PORT

# Use a real WSGI server
ENTRYPOINT ["python3", "wsgi.py"]

# ##################################################
# Production target
FROM base as production

LABEL target=production

USER geoadmin

ENV WMTS_PORT $WMTS_PORT
EXPOSE $WMTS_PORT

# Use a real WSGI server
ENTRYPOINT ["python3", "wsgi.py"]