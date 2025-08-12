Backend for Open AI Hay
=======================

Local PostgreSQL + SQLModel setup for conversations, articles, and daily suggestions.

Quick start
-----------

1) Start PostgreSQL and create a database `aihay`.

2) Install deps (Python 3.13+):

```bash
cd backend
uv pip install -e .  # or: pip install -e .
```

3) Create schema and seed presets:

```bash
python -m db_init
```

By default it uses `DATABASE_URL` env var. Example:

```bash
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/aihay
python -m db_init
```

Files
-----

- `db_schema.sql` – raw SQL DDL and indexes
- `models.py` – SQLModel models
- `db_init.py` – create_all and seed presets


