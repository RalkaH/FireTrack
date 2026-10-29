# Dockerfile (v1.1)
FROM python:3.13-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код проекта и статику
COPY . .

# Открываем порт для приложения
EXPOSE 8000

# Команда для запуска приложения с использованием uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
