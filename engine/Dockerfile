FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip uninstall -y psycopg2-binary==2.9.9
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
EXPOSE 5000
CMD ["python", "app.py"]
