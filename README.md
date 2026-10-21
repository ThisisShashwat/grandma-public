# Help Grandma Out

The website for Help Grandma Out, a Hack Club program for teens 13 to 18. A nitpicky Grandma hands you a few annoying build demands, you build any project around them, and you earn cookies for your hours. The site has a hand-drawn MS Paint look.

This repository is a snapshot of the application source.

## What is in here

| Folder | What it is |
|---|---|
| `grandma/` | The Django project: settings, URLs, WSGI and ASGI, the Jinja2 setup |
| `program/` | Pure Python, no Django: the payout maths, constants and the starting content |
| `pages/` | The home page, error pages, middleware, the admin-editable settings reader |
| `accounts/`, `talk/`, `ledger/` | Profiles and sign-in, the dialogue framework, the append-only cookie ledger |
| `projects/`, `submissions/` | The draw and Talk to Grandma, hand-ins and reviews |
| `shop/`, `orders/` | The Pantry and getting a grant |
| `guides/`, `content/guides/` | The public guides, written as Markdown files |
| `showcase/`, `dashboard/` | Public profile and project pages, the signed-in dashboard |
| `audit/`, `metrics/` | The audit log and the admin metrics page |
| `templates/`, `static/` | Jinja2 templates, CSS, ES-module JavaScript and the art |
| `coming-soon/` | A standalone static landing page |

## Run it locally

Python 3.12 or newer.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
python manage.py migrate
python manage.py runserver
```

The site is then at http://localhost:8000. Accounts are made in the admin at http://localhost:8000/admin/ (`python manage.py createsuperuser` first). With no `DATABASE_URL` set it uses a local SQLite file.

All configuration comes from environment variables; `.env.example` lists every name with a placeholder. Integrations (Hack Club sign-in, Hackatime, Slack, screenshot storage) stay off until their variables are set.

## Not in this repository

Tests, internal documentation, raw art sources, deployment configuration and every secret.
