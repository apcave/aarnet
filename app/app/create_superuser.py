import os
from pathlib import Path

import django
from django.core.management import call_command
from django.db import connection


def load_env(path: Path | None = None) -> None:
    env_path = path or Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def create_superuser() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
    django.setup()

    tables = connection.introspection.table_names()
    if 'core_user' not in tables:
        call_command('migrate', verbosity=0, run_syncdb=True)

    from django.contrib.auth import get_user_model

    User = get_user_model()
    email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
    password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "adminpass123")
    name = os.environ.get("DJANGO_SUPERUSER_NAME", "Admin User")

    user = User.objects.filter(email=email).first()
    if user is None:
        user = User.objects.create_superuser(email=email, password=password)
        print(f"Created superuser {email}")
    else:
        print(f"Superuser {email} already exists")

    if name and user.name != name:
        user.name = name
        user.save(update_fields=["name"])
        print(f"Updated superuser name to {name}")


if __name__ == "__main__":
    load_env()
    create_superuser()
