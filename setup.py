# setup.py (v1.3)
"""
Конфигурационный файл системы сборки (Setuptools).
Позволяет упаковать проект FireTrack как стандартный Python-пакет,
устанавливать зависимости и регистрировать консольные команды (entry_points).

Вызов ``setup()`` спрятан под ``if __name__ == "__main__"``, чтобы модуль
можно было импортировать (например, Sphinx при сборке документации).
"""
from setuptools import setup, find_packages

PACKAGE_INFO = dict(
    name="firetrack",
    version="1.5.0",
    packages=find_packages(exclude=["tests", "tests.*", "docs", "migrations"]),
    include_package_data=True,
    install_requires=[
        "fastapi",
        "uvicorn",
        "sqlalchemy>=2.0",
        "pydantic>=2",
        "python-multipart",
        "python-jose[cryptography]>=3.4.0",
        "passlib[bcrypt]",
        "alembic>=1.13",
        "openpyxl>=3.1",
    ],
    entry_points={
        "console_scripts": [
            "firetrack-run=main:app",
        ],
    },
    author="FireTrack Team",
    description="Система контроля противопожарного оборудования",
    python_requires=">=3.11",
)

if __name__ == "__main__":
    setup(**PACKAGE_INFO)
