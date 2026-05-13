# Система отметки проверки средств пожаротушения

## Требования

- Astra Linux (любой выпуск с поддержкой Python 3)
- Пакеты:
  - python3
  - python3-venv
  - python3-pip

Устанавливаются командой:

sudo apt update
sudo apt install python3 python3-venv python3-pip

sudo apt update
sudo apt install python3 python3-venv python3-pip

sudo mkdir -p /opt/fire-check
sudo chown $USER:$USER /opt/fire-check
cd /opt/fire-check

сюда распаковать архив проекта


2. Создать виртуальное окружение и установить зависимости:

cd /opt/fire-check
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt


3. (Опционально) Инициализировать пустую базу данных, если в архиве нет файла `fire_extinguishers.db`
   или есть отдельный скрипт миграций.

## Запуск сервера

Из каталога проекта:

cd /opt/fire-check
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000


После запуска веб-интерфейс доступен по адресу:

- на той же машине: `http://localhost:8000/static/index.html`
- с другой машины локальной сети: `http://IP_сервера:8000/static/index.html`

## Автоматический запуск (по желанию)

1. Создать файл `/etc/systemd/system/fire-check.service`:

[Unit]
Description=Fire Extinguisher Check System
After=network.target

[Service]
User=astrauser
Group=astrauser
WorkingDirectory=/opt/fire-check
Environment="PATH=/opt/fire-check/venv/bin"
ExecStart=/opt/fire-check/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target

`astrauser` заменить на имя пользователя.

2. Включить сервис:

sudo systemctl daemon-reload
sudo systemctl enable fire-check.service
sudo systemctl start fire-check.service


После этого сервер стартует сам при загрузке системы, пользователям достаточно открыть
`http://IP_сервера:8000/static/index.html` в браузере.
