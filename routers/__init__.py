# routers/__init__.py (v1.3)
"""
Инициализационный модуль пакета routers.
Экспортирует все роутеры для удобного подключения в главном файле main.py.
"""
from . import (
    locations,
    statuses,
    extinguishers,
    employees,
    inspections,
    reports,
    import_data,
    users,
    audit_log,
    settings,
    service_records,
    backups,
)
