FROM python:3.10-slim
WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    jinja2 \
    python-multipart \
    "passlib[bcrypt]" \
    "bcrypt==4.0.1" \
    "itsdangerous"

COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]