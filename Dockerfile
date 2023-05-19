FROM python:3.10-bullseye

# Environment
RUN apt-get update && apt-get install \
  -y --no-install-recommends curl dnsutils vim

ENV APP_ROOT=/opt

# Operator
COPY operator/ ${APP_ROOT}

RUN chmod -R u+x ${APP_ROOT} && \
    chgrp -R 0 ${APP_ROOT} && \
    chmod -R g=u ${APP_ROOT}

# Installation and exection
WORKDIR ${APP_ROOT}
RUN pip install --no-cache-dir -r requirements.txt

# Make OCP friendly
USER 1001

ENTRYPOINT ["./run.sh"]