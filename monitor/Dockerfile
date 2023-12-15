FROM python:3

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

# COPY boutique_training.json /app

# COPY normal_traces_check_payment.json /app

# COPY normal_traces_frontend_cartservice.json /app

CMD ["python", "monitor.py"]