# auth.py (v1.3)
"""
Модуль аутентификации и авторизации пользователей.
Обеспечивает хеширование паролей, генерацию и проверку токенов JWT,
а также содержит зависимости FastAPI для защиты маршрутов по ролям (RBAC).

Настройки берутся из переменных окружения:

* ``SECRET_KEY`` — ключ подписи JWT. Если не задан, ключ генерируется
  один раз и сохраняется в файл ``.secret_key`` рядом с проектом, чтобы
  токены не сбрасывались при каждом перезапуске сервера.
* ``ACCESS_TOKEN_EXPIRE_MINUTES`` — время жизни токена (по умолчанию 480 минут).
"""
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from db import get_db
from models import User
from schemas import Token, TokenData, UserRead

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

# Используем pbkdf2_sha256
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверяет соответствие введенного пароля его хешу.

    Args:
        plain_password (str): Введенный пользователем пароль.
        hashed_password (str): Хеш пароля из базы данных.

    Returns:
        bool: True, если пароль верен, иначе False.
    """
    return pwd_context.verify(plain_password, hashed_password)


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
        return None

    stored_hash: str = user.hashed_password  # type: ignore[assignment]

    if not verify_password(password, stored_hash):
        return None
    return user


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
        HTTPException: Если токен невалиден, истек или пользователь не найден (401).
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
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Проверяет, что текущий пользователь активен (не заблокирован).

    Args:
        current_user (User): Пользователь, полученный из токена.

    Returns:
        User: Активный пользователь.

    Raises:
        HTTPException: Если учетная запись деактивирована (403).
    """
    is_active: bool = bool(current_user.is_active)  # type: ignore[arg-type]
    if not is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Учетная запись заблокирована",
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


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Эндпоинт для входа в систему и генерации токена доступа.

    Args:
        form_data (OAuth2PasswordRequestForm): Данные формы авторизации (логин/пароль).
        db (Session): Сессия базы данных.

    Returns:
        dict: Токен доступа, его тип и время жизни в секундах.
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not bool(user.is_active):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Учетная запись заблокирована",
        )
    access_token = create_access_token(data={"sub": user.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.get("/me", response_model=UserRead)
async def read_current_user(current_user: User = Depends(get_current_active_user)):
    """
    Возвращает данные текущего пользователя (логин, ФИО, роль).
    Используется интерфейсом для отображения пользователя и проверки сессии.

    Args:
        current_user (User): Пользователь из токена.

    Returns:
        User: Текущий пользователь.
    """
    return current_user
