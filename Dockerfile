FROM python:3.9


ARG zsh
RUN sh -c "$(wget -O- https://github.com/deluan/zsh-in-docker/releases/download/v1.1.2/zsh-in-docker.sh)" -- \ -a 'CASE_SENSITIVE="true"'


WORKDIR /root

COPY requirements.txt .

RUN ls

COPY src src

RUN ls

RUN pip install -r requirements.txt

CMD ["zsh"]

