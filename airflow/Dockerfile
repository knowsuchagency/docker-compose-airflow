# Python 3.7 produces errors since async becomes a keyword; use 3.6 instead

FROM python:3.6-slim

RUN apt-get update && \
    apt-get install -y \
        build-essential \
        curl \
        less

# SLUGIFY_USES_TEXT_UNIDECODE ensures airflow doesn't install an unnecessary GNU-licensed lib

ENV SLUGIFY_USES_TEXT_UNIDECODE yes

ADD flow_toolz flow_toolz

ADD setup.py .

RUN pip install -U pip setuptools wheel && \
    pip install -e '.[all]'

ADD dags/* /dags/

ADD tasks.py .
ADD invoke.yaml .

ENTRYPOINT [ "invoke" ]

CMD [ "-l" ]