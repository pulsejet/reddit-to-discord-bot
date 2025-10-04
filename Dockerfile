FROM python:latest

RUN pip3 install --upgrade pip && \
    pip install praw python-dotenv && \
    mkdir /app

COPY bot.py /app/

WORKDIR /app
CMD ["python3", "bot.py"]
