FROM python:3.9

WORKDIR /root

COPY requirements.txt .
COPY src ./src

RUN pip install -r requirements.txt

CMD ["bin/bash"]

