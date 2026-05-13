# setup.py (v1.0)
from setuptools import setup, find_packages

setup(
    name="firetrack",
    version="1.0.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "pydantic",
        "python-multipart",
        "python-jose[cryptography]",
        "passlib[bcrypt]",
    ],
    entry_points={
        "console_scripts": [
            "firetrack-run=main:app",
        ],
    },
    author="FireTrack Team",
    description="Система контроля противопожарного оборудования",
    python_requires=">=3.9",
)
