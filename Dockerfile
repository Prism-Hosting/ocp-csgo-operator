FROM python:3.10-bullseye

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
CMD kopf run main.py --all-namespaces --verbose