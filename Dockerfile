FROM python:3.10.13-bullseye

MAINTAINER https://progressify.dev

WORKDIR /app

ADD . /app
RUN pip install --requirement /app/requirements.txt
