FROM ubuntu:23.04

# Environment
RUN apt-get update && apt-get install \
  -y --no-install-recommends curl dnsutils iputils-ping python3 python3-virtualenv vim

ENV APP_ROOT=/opt
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m virtualenv --python=/usr/bin/python3 $VIRTUAL_ENV
ENV PATH=$VIRTUAL_ENV/bin:${APP_ROOT}/.local/bin:${APP_ROOT}:${PATH} HOME=${APP_ROOT}

# Operator
COPY operator/ ${APP_ROOT}

RUN chmod -R u+x ${APP_ROOT} && \
    chgrp -R 0 ${APP_ROOT} && \
    chmod -R g=u ${APP_ROOT}

# OCP friendly
USER 1001

# Installation and exection
WORKDIR ${APP_ROOT}
RUN pip install --no-cache-dir -r requirements.txt
CMD kopf run main.py --verbose