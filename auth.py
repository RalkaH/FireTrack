# auth.py (v1.5)
"""
Модуль аутентификации и авторизации пользователей.
Обеспечивает хеширование паролей, генерацию и проверку токенов JWT,
а также содержит зависимости FastAPI для защиты маршрутов по ролям (RBAC).

Настройки берутся из переменных окружения:

* ``SECRET_KEY`` — ключ подписи JWT. Если не задан, ключ генерируется
  один раз и сохраняется в файл ``.secret_key`` рядом с проектом, чтобы
  токены не сбрасывались при каждом перезапуске сервера.
* ``ACCESS_TOKEN_EXPIRE_MINUTES`` — время жизни токена (по умолчанию 480 минут).
* ``LOGIN_MAX_FAILURES`` и ``LOGIN_LOCK_MINUTES`` — после стольких неудачных
  попыток входа подряд (по паре «логин + IP») вход блокируется на столько
  минут (по умолчанию 5 попыток и 10 минут).

Безопасность сессий:

* В токен записывается ``ver`` — версия токенов пользователя. Смена и сброс
  пароля, блокировка и смена роли увеличивают ее, и все выданные ранее
  токены этого пользователя сразу перестают приниматься.
* Пока у пользователя стоит флаг ``must_change_password``, сервер отвечает
  403 на все запросы, кроме ``/auth/me`` и ``/auth/change-password``.
  В ответе есть заголовок ``X-Password-Change-Required: 1``, по нему
  интерфейс открывает форму смены пароля.
"""
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Deque, Dict, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

import audit
from db import get_db
from models import User
from schemas import PasswordChange, Token, TokenData, UserRead, validate_password_strength

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)

BASE_DIR = Path(__file__).resolve().parent
SECRET_KEY_FILE = BASE_DIR / ".secret_key"

# Роли пользователей
ROLE_ADMIN = "admin"
ROLE_ENGINEER = "engineer"
ROLE_VIEWER = "viewer"
EDITOR_ROLES = [ROLE_ADMIN, ROLE_ENGINEER]

DEFAULT_ADMIN_PASSWORD = "admin123"
PASSWORD_CHANGE_HEADER = "X-Password-Change-Required"


def _load_secret_key() -> str:
    """
    Возвращает ключ подписи JWT.

    Порядок поиска: переменная окружения ``SECRET_KEY``, затем файл
    ``.secret_key``. Если ни то ни другое не найдено, генерирует новый
    случайный ключ и сохраняет его в файл.

    Returns:
        str: Секретный ключ.
    """
    env_key = os.getenv("SECRET_KEY")
    if env_key:
        return env_key

    if SECRET_KEY_FILE.exists():
        stored = SECRET_KEY_FILE.read_text(encoding="utf-8").strip()
        if stored:
            return stored

    new_key = secrets.token_urlsafe(48)
    try:
        SECRET_KEY_FILE.write_text(new_key, encoding="utf-8")
    except OSError:
        # Нет прав на запись: ключ будет жить до перезапуска процесса
        pass
    return new_key


# Настройки
SECRET_KEY = _load_secret_key()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
LOGIN_MAX_FAILURES = int(os.getenv("LOGIN_MAX_FAILURES", "5"))
LOGIN_LOCK_MINUTES = int(os.getenv("LOGIN_LOCK_MINUTES", "10"))

# Используем pbkdf2_sha256
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


# ---------- Ограничение попыток входа ----------

class LoginThrottle:
    """
    Простое ограничение перебора паролей в памяти процесса.

    Считает неудачные попытки по паре (логин, IP) в скользящем окне.
    После ``max_failures`` попыток вход для этой пары запрещен до тех пор,
    пока самая старая попытка не выйдет из окна. Успешный вход сбрасывает
    счетчик.
    """

    def __init__(self, max_failures: int, window_seconds: int):
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _trim(self, key: Tuple[str, str], now: float) -> Deque[float]:
        attempts = self._failures[key]
        while attempts and now - attempts[0] > self.window:
            attempts.popleft()
        return attempts

    def retry_after(self, username: str, ip: str) -> int:
        """Сколько секунд осталось до разблокировки (0, если вход разрешен)."""
        key = (username.lower(), ip)
        now = time.monotonic()
        with self._lock:
            if key not in self._failures:
                return 0
            attempts = self._trim(key, now)
            if not attempts:
                # Старые попытки вышли из окна: не копим в памяти произвольные логины
                del self._failures[key]
                return 0
            if len(attempts) < self.max_failures:
                return 0
            return max(1, int(self.window - (now - attempts[0])))

    def failure(self, username: str, ip: str) -> None:
        """Запоминает неудачную попытку."""
        key = (username.lower(), ip)
        now = time.monotonic()
        with self._lock:
            self._trim(key, now).append(now)

    def success(self, username: str, ip: str) -> None:
        """Сбрасывает счетчик после успешного входа."""
        with self._lock:
            self._failures.pop((username.lower(), ip), None)

    def reset(self) -> None:
        """Полностью очищает счетчики (для тестов)."""
        with self._lock:
            self._failures.clear()


login_throttle = LoginThrottle(LOGIN_MAX_FAILURES, LOGIN_LOCK_MINUTES * 60)


# ---------- Пароли и токены ----------

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверяет соответствие введенного пароля его хешу.

    Args:
        plain_password (str): Введенный пользователем пароль.
        hashed_password (str): Хеш пароля из базы данных.

    Returns:
        bool: True, если пароль верен, иначе False.
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        # Неизвестный или испорченный формат хеша
        return False


def get_password_hash(password: str) -> str:
    """
    Генерирует криптографический хеш для заданного пароля.

    Args:
        password (str): Исходный пароль в открытом виде.

    Returns:
        str: Захешированная строка.
    """
    return pwd_context.hash(password)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Создает JWT токен доступа для пользователя.

    Args:
        data (dict): Полезная нагрузка (payload) токена.
        expires_delta (Optional[timedelta]): Время жизни токена.

    Returns:
        str: Закодированный JWT токен.
    """
    to_encode = data.copy()
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def token_for(user: User) -> dict:
    """
    Выдает новый токен пользователю.

    Args:
        user (User): Пользователь.

    Returns:
        dict: Ответ в формате схемы ``Token``.
    """
    token = create_access_token({"sub": user.username, "ver": int(user.token_version or 0)})
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "must_change_password": bool(user.must_change_password),
    }


def revoke_tokens(user: User) -> None:
    """Делает недействительными все выданные пользователю токены (без commit)."""
    user.token_version = int(user.token_version or 0) + 1


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Аутентифицирует пользователя по логину и паролю.

    Args:
        db (Session): Сессия базы данных.
        username (str): Имя пользователя.
        password (str): Пароль.

    Returns:
        Optional[User]: Объект пользователя при успешной проверке, иначе None.
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        # Тратим время на хеширование, чтобы по скорости ответа нельзя было
        # понять, существует ли логин
        pwd_context.dummy_verify()
        return None

    stored_hash: str = user.hashed_password  # type: ignore[assignment]

    if not verify_password(password, stored_hash):
        return None
    return user


# ---------- Зависимости FastAPI ----------

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Извлекает текущего пользователя из переданного JWT токена.

    Args:
        token (str): JWT токен из заголовка Authorization.
        db (Session): Сессия базы данных.

    Returns:
        User: Объект пользователя.

    Raises:
        HTTPException: Если токен невалиден, истек, отозван или пользователь
            не найден (401).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Сессия истекла или токен недействителен. Войдите заново.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username_value = payload.get("sub")
        if not isinstance(username_value, str):
            raise credentials_exception
        token_data = TokenData(username=username_value)
        token_version = int(payload.get("ver", 0))
    except (JWTError, TypeError, ValueError):
        raise credentials_exception

    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None or token_version != int(user.token_version or 0):
        raise credentials_exception
    return user


async def get_current_user_pending_password(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Активный пользователь, даже если ему нужно сменить пароль.
    Используется только для ``/auth/me`` и ``/auth/change-password``.

    Raises:
        HTTPException: Если учетная запись заблокирована (403).
    """
    if not bool(current_user.is_active):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Учетная запись заблокирована",
        )
    return current_user


async def get_current_active_user(
    current_user: User = Depends(get_current_user_pending_password),
) -> User:
    """
    Проверяет, что текущий пользователь активен и не обязан сменить пароль.

    Args:
        current_user (User): Пользователь, полученный из токена.

    Returns:
        User: Активный пользователь.

    Raises:
        HTTPException: Если учетная запись деактивирована или требуется
            сменить пароль (403).
    """
    if bool(current_user.must_change_password):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуется сменить пароль",
            headers={PASSWORD_CHANGE_HEADER: "1"},
        )
    return current_user


def require_role(allowed_roles: list):
    """
    Создает зависимость FastAPI для проверки роли пользователя (RBAC).

    Args:
        allowed_roles (list): Список допустимых ролей (например, ["admin", "engineer"]).

    Returns:
        Callable: Функция-проверщик для использования в Depends().
    """
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        """Внутренняя логика проверки роли."""
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для этого действия",
            )
        return current_user

    return role_checker


# ---------- Эндпоинты ----------

@router.post("/token", response_model=Token)
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Эндпоинт для входа в систему и генерации токена доступа.

    Каждая попытка (успешная и неудачная) попадает в журнал действий.
    После нескольких неудачных попыток подряд вход временно блокируется (429).

    Args:
        request (Request): Запрос (IP для журнала и ограничения попыток).
        form_data (OAuth2PasswordRequestForm): Данные формы авторизации (логин/пароль).
        db (Session): Сессия базы данных.

    Returns:
        dict: Токен доступа, его тип, время жизни в секундах и флаг
        обязательной смены пароля.
    """
    # Логин приходит от кого угодно: длину в журнале и счетчике попыток ограничиваем
    username = form_data.username.strip()[:150]
    ip = request.client.host if request.client else "unknown"

    wait = login_throttle.retry_after(username, ip)
    if wait:
        audit.log(db, request, None, audit.ACTION_LOGIN_FAILED,
                  f"Вход отклонен: слишком много попыток для «{username}»",
                  entity_type="user", username=username, commit=True)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Слишком много неудачных попыток. Повторите через {max(1, wait // 60)} мин.",
            headers={"Retry-After": str(wait)},
        )

    user = authenticate_user(db, username, form_data.password)
    if not user:
        login_throttle.failure(username, ip)
        audit.log(db, request, None, audit.ACTION_LOGIN_FAILED,
                  f"Неверный логин или пароль для «{username}»",
                  entity_type="user", username=username, commit=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not bool(user.is_active):
        audit.log(db, request, user, audit.ACTION_LOGIN_FAILED,
                  f"Попытка входа в заблокированную учетную запись «{user.username}»",
                  entity_type="user", entity_id=user.id, commit=True)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Учетная запись заблокирована",
        )

    login_throttle.success(username, ip)
    user.last_login_at = datetime.now(timezone.utc)
    audit.log(db, request, user, audit.ACTION_LOGIN_SUCCESS,
              f"Вход пользователя «{user.username}»",
              entity_type="user", entity_id=user.id)
    db.commit()
    return token_for(user)


@router.get("/me", response_model=UserRead)
async def read_current_user(current_user: User = Depends(get_current_user_pending_password)):
    """
    Возвращает данные текущего пользователя (логин, ФИО, роль, флаг смены пароля).
    Используется интерфейсом для отображения пользователя и проверки сессии.

    Args:
        current_user (User): Пользователь из токена.

    Returns:
        User: Текущий пользователь.
    """
    return current_user


@router.post("/change-password", response_model=Token)
async def change_password(
    data: PasswordChange,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_pending_password),
):
    """
    Смена собственного пароля.

    Старые токены пользователя (в том числе на других устройствах) перестают
    работать, в ответе приходит новый токен для текущей сессии.

    Args:
        data (PasswordChange): Старый и новый пароль.
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Текущий пользователь.

    Returns:
        dict: Новый токен.

    Raises:
        HTTPException: Если старый пароль неверен (400) или новый пароль
            слишком простой или совпадает со старым (422).
    """
    if not verify_password(data.old_password, current_user.hashed_password):
        audit.log(db, request, current_user, audit.ACTION_PASSWORD_CHANGE,
                  "Неудачная смена пароля: неверный текущий пароль",
                  entity_type="user", entity_id=current_user.id, commit=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Текущий пароль указан неверно")
    if data.old_password == data.new_password:
        raise HTTPException(status_code=422,
                            detail="Новый пароль должен отличаться от текущего")
    try:
        validate_password_strength(data.new_password, current_user.username)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    current_user.hashed_password = get_password_hash(data.new_password)
    current_user.must_change_password = False
    revoke_tokens(current_user)
    audit.log(db, request, current_user, audit.ACTION_PASSWORD_CHANGE,
              f"Пользователь «{current_user.username}» сменил пароль",
              entity_type="user", entity_id=current_user.id)
    db.commit()
    return token_for(current_user)
