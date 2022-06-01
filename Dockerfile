FROM python:3.9

WORKDIR /root

COPY requirements.txt .

RUN ls

COPY src src

RUN ls

RUN pip install -r requirements.txt

CMD ["sh"]

