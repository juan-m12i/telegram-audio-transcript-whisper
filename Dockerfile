FROM python:3.10-slim

WORKDIR app

RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ARG BOT_SCRIPT=dev_bot.py
ENV BOT_SCRIPT_ENV=${BOT_SCRIPT}
CMD python -u "${BOT_SCRIPT_ENV}"


