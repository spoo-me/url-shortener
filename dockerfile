FROM python:3.11

WORKDIR /app

COPY ./requirements.txt /app/
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "main.py"]