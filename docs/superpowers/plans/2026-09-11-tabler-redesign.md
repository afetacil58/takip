# is_takip Tabler Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace is_takip's hand-rolled CSS UI with Tabler admin-dashboard components (navbar, cards, tables, forms, badges, ApexCharts) across all 13 templates, with no backend/behavior changes.

**Architecture:** Vendor pre-built Tabler CSS/JS/ApexCharts locally into `static/vendor/tabler/` (no live Node build in Flask). Rewrite `templates/base.html` as the Tabler navbar shell, add a shared `templates/_macros.html` for status/priority badge and progress-bar rendering, then migrate each page template to Tabler markup one at a time, preserving every existing Jinja variable name and route.

**Tech Stack:** Flask/Jinja2 (unchanged), Tabler `@tabler/core` 1.5.1 (vendored, built from `C:\AP\tabler`), ApexCharts (vendored from the same build), vanilla `<script>` blocks (no new JS framework/build step in is_takip itself).

**Spec:** `docs/superpowers/specs/2026-09-11-tabler-redesign-design.md`

## Global Constraints

- Backend (`app.py`, DB schema, routes, auth, file uploads, email reminders) does not change. Only files under `templates/`, `static/style.css`, and new files under `static/vendor/tabler/` are touched.
- Every Jinja variable/route name used below is copied verbatim from the current templates and `app.py` (confirmed by reading both before writing this plan) — do not invent new context variables.
- No CDN: all Tabler/ApexCharts assets are local files under `static/vendor/tabler/`.
- Primary brand color: override `--tblr-primary` / `--tblr-primary-rgb` to AFAD's `#c8102e` on top of Tabler's `orange` preset (`data-bs-theme-primary="orange"`).
- No automated test suite exists in this project (confirmed in the spec) and none is introduced here. Each task's verification is: (a) an automated Jinja2 syntax parse check (fast, catches template tag errors), and (b) a manual browser walkthrough with an explicit checklist — this matches the spec's approved "Test / doğrulama" section. Do not skip the manual walkthrough even though step (a) passes.
- Git repo: `C:\AP\is_takip` was just initialized (`git init`, baseline commit `9e86af8`). Commit after every task.
- Run the app for manual checks with: `cd C:\AP\is_takip && python app.py` (Flask dev server, default `http://127.0.0.1:5000`). Log in with an existing admin and an existing manager account from `gorev_takip.db` (ask the user for test credentials if none are known — do not create new users via direct DB edits).

---

## Task 1: Vendor Tabler assets into `static/vendor/tabler`

**Files:**
- Create: `static/vendor/tabler/css/tabler.min.css` (+ `.css.map`)
- Create: `static/vendor/tabler/css/tabler-themes.min.css` (+ `.css.map`)
- Create: `static/vendor/tabler/js/tabler.min.js` (+ `.js.map`)
- Create: `static/vendor/tabler/js/apexcharts.min.js`

**Interfaces:**
- Produces: the four static asset paths above, which every later task's `base.html`/`{% block scripts %}` links against by exact path `vendor/tabler/css/tabler.min.css`, `vendor/tabler/css/tabler-themes.min.css`, `vendor/tabler/js/tabler.min.js`, `vendor/tabler/js/apexcharts.min.js` (all resolved via `url_for('static', filename=...)`).

- [ ] **Step 1: Build `@tabler/core` in the vendored Tabler clone**

Run (already verified working in this session, safe to re-run — it's idempotent):

```bash
cd /c/AP/tabler
pnpm --filter @tabler/core build
```

Expected: build completes, `core/dist/css/tabler.min.css`, `core/dist/css/tabler-themes.min.css`, `core/dist/js/tabler.min.js`, `core/dist/libs/apexcharts/dist/apexcharts.min.js` all exist.

- [ ] **Step 2: Verify the four source files exist**

```bash
ls -la /c/AP/tabler/core/dist/css/tabler.min.css \
       /c/AP/tabler/core/dist/css/tabler-themes.min.css \
       /c/AP/tabler/core/dist/js/tabler.min.js \
       /c/AP/tabler/core/dist/libs/apexcharts/dist/apexcharts.min.js
```

Expected: all four paths listed, no "No such file" errors.

- [ ] **Step 3: Copy the files into is_takip's static folder**

```bash
mkdir -p /c/AP/is_takip/static/vendor/tabler/css
mkdir -p /c/AP/is_takip/static/vendor/tabler/js

cp /c/AP/tabler/core/dist/css/tabler.min.css* /c/AP/is_takip/static/vendor/tabler/css/
cp /c/AP/tabler/core/dist/css/tabler-themes.min.css* /c/AP/is_takip/static/vendor/tabler/css/
cp /c/AP/tabler/core/dist/js/tabler.min.js* /c/AP/is_takip/static/vendor/tabler/js/
cp /c/AP/tabler/core/dist/libs/apexcharts/dist/apexcharts.min.js /c/AP/is_takip/static/vendor/tabler/js/
```

- [ ] **Step 4: Verify the copy**

```bash
ls -la /c/AP/is_takip/static/vendor/tabler/css /c/AP/is_takip/static/vendor/tabler/js
```

Expected: `tabler.min.css`, `tabler.min.css.map`, `tabler-themes.min.css`, `tabler-themes.min.css.map` in `css/`; `tabler.min.js`, `tabler.min.js.map`, `apexcharts.min.js` in `js/`.

- [ ] **Step 5: Commit**

```bash
cd /c/AP/is_takip
git add static/vendor/tabler
git commit -m "$(cat <<'EOF'
chore: vendor Tabler core CSS/JS and ApexCharts

Built @tabler/core from the local tabler clone (C:\AP\tabler) and
copied the production CSS/JS output into static/vendor/tabler so the
Flask app can serve it without any Node build step at runtime.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RxQXtwis8wHHAeq5r3kHQP
EOF
)"
```

---

## Task 2: Rebuild `base.html` shell + shared macros + trimmed `style.css`

**Files:**
- Modify: `templates/base.html` (full rewrite)
- Create: `templates/_macros.html`
- Modify: `static/style.css` (full rewrite — trimmed to AFAD-only overrides)

**Interfaces:**
- Consumes: `static/vendor/tabler/css/tabler.min.css`, `static/vendor/tabler/css/tabler-themes.min.css`, `static/vendor/tabler/js/tabler.min.js` (Task 1). Routes: `dashboard`, `users`, `admins`, `reports`, `statistics`, `personnel`, `new_task`, `change_password`, `logout` (all exist in `app.py`, unchanged). Session keys: `session['user_id']`, `session['role']`, `session['full_name']` (used identically to the old `base.html`).
- Produces (for every later task to consume):
  - `templates/_macros.html` exports Jinja macros, imported elsewhere as `{% import "_macros.html" as m %}`:
    - `m.status_color(status)` → returns one of `secondary|blue|green|dark` for `status in STATUSES`
    - `m.priority_color(priority)` → returns one of `secondary|blue|yellow|red` for `priority in PRIORITIES`
    - `m.status_badge(status)` → renders `<span class="badge bg-{color}-lt">{status}</span>`
    - `m.priority_badge(priority)` → renders `<span class="badge bg-{color}-lt">{priority}</span>`
    - `m.progress_bar(progress)` → renders a Tabler `.progress` bar + `%N` label for an integer `progress` (0-100)
  - `templates/base.html` blocks available to children: `{% block title %}`, `{% block content %}`, `{% block scripts %}` (new — for page-specific `<script>`, e.g. ApexCharts init)
  - Page body wrapper classes every child template's content sits inside: `container-xl` (so child templates should use Tabler's `row`/`col-*` grid or `card` directly, not re-wrap in another container)

- [ ] **Step 1: Create `templates/_macros.html`**

```jinja
{% macro status_color(status) -%}
{{ {'Bekliyor': 'secondary', 'Devam Ediyor': 'blue', 'Tamamlandı': 'green', 'İptal': 'dark'}.get(status, 'secondary') }}
{%- endmacro %}

{% macro priority_color(priority) -%}
{{ {'Düşük': 'secondary', 'Orta': 'blue', 'Yüksek': 'yellow', 'Acil': 'red'}.get(priority, 'secondary') }}
{%- endmacro %}

{% macro status_badge(status) -%}
<span class="badge bg-{{ status_color(status) }}-lt">{{ status }}</span>
{%- endmacro %}

{% macro priority_badge(priority) -%}
<span class="badge bg-{{ priority_color(priority) }}-lt">{{ priority }}</span>
{%- endmacro %}

{% macro progress_bar(progress) -%}
<div class="progress progress-sm" role="progressbar" aria-valuenow="{{ progress }}" aria-valuemin="0" aria-valuemax="100">
  <div class="progress-bar" style="width: {{ progress }}%"></div>
</div>
<div class="text-secondary small mt-1">%{{ progress }}</div>
{%- endmacro %}
```

- [ ] **Step 2: Rewrite `templates/base.html`**

```jinja
<!doctype html>
<html lang="tr" data-bs-theme-primary="orange">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{% block title %}Görev Takip{% endblock %} — AFAD</title>
<link rel="stylesheet" href="{{ url_for('static', filename='vendor/tabler/css/tabler.min.css') }}">
<link rel="stylesheet" href="{{ url_for('static', filename='vendor/tabler/css/tabler-themes.min.css') }}">
<link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
{% if session.get('user_id') %}
<header class="navbar navbar-expand-md navbar-dark bg-primary d-print-none">
  <div class="container-xl">
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbar-menu" aria-controls="navbar-menu" aria-expanded="false" aria-label="Menüyü aç/kapat">
      <span class="navbar-toggler-icon"></span>
    </button>
    <a href="{{ url_for('dashboard') }}" class="navbar-brand d-flex align-items-center pe-0 pe-md-3">
      <span class="bg-white rounded d-inline-flex align-items-center p-1 me-2">
        <img src="{{ url_for('static', filename='img/afad-logo.png') }}" alt="AFAD" style="height: 24px; width: auto;">
      </span>
      Görev Takip Sistemi
    </a>
    <div class="navbar-nav flex-row order-md-last align-items-center">
      <a href="{{ url_for('new_task') }}" class="btn btn-light btn-sm d-none d-sm-inline-block me-3">+ Yeni İşlem</a>
      <div class="nav-item dropdown">
        <a href="#" class="nav-link d-flex lh-1 text-reset p-0" data-bs-toggle="dropdown" aria-expanded="false">
          <span class="avatar avatar-sm bg-white-lt">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M8 7a4 4 0 1 0 8 0a4 4 0 0 0 -8 0" /><path d="M6 21v-2a4 4 0 0 1 4 -4h4a4 4 0 0 1 4 4v2" /></svg>
          </span>
          <div class="d-none d-xl-block ps-2">
            <div>{{ session.get('full_name') }}</div>
          </div>
        </a>
        <div class="dropdown-menu dropdown-menu-end dropdown-menu-arrow">
          <a href="{{ url_for('change_password') }}" class="dropdown-item">Şifremi Değiştir</a>
          <a href="{{ url_for('static', filename='rehber/kullanim-rehberi.pdf') }}" target="_blank" class="dropdown-item">Kullanım Rehberi</a>
          <div class="dropdown-divider"></div>
          <a href="{{ url_for('logout') }}" class="dropdown-item">Çıkış</a>
        </div>
      </div>
    </div>
  </div>
</header>
<div class="navbar-expand-md d-print-none">
  <div class="collapse navbar-collapse" id="navbar-menu">
    <div class="navbar navbar-light">
      <div class="container-xl">
        <ul class="navbar-nav">
          <li class="nav-item"><a class="nav-link" href="{{ url_for('dashboard') }}">Panel</a></li>
          {% if session.get('role') == 'admin' %}
          <li class="nav-item"><a class="nav-link" href="{{ url_for('users') }}">Şube Müdürleri</a></li>
          <li class="nav-item"><a class="nav-link" href="{{ url_for('admins') }}">Yöneticiler</a></li>
          <li class="nav-item"><a class="nav-link" href="{{ url_for('reports') }}">Raporlar</a></li>
          <li class="nav-item"><a class="nav-link" href="{{ url_for('statistics') }}">İstatistikler</a></li>
          {% else %}
          <li class="nav-item"><a class="nav-link" href="{{ url_for('personnel') }}">Personelim</a></li>
          {% endif %}
          <li class="nav-item d-sm-none"><a class="nav-link" href="{{ url_for('new_task') }}">+ Yeni İşlem</a></li>
        </ul>
      </div>
    </div>
  </div>
</div>
{% endif %}

<div class="page-wrapper">
  <div class="page-body">
    <div class="container-xl">
      {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
          {% for category, message in messages %}
          <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible" role="alert">
            {{ message }}
            <a href="#" class="btn-close" data-bs-dismiss="alert" aria-label="Kapat"></a>
          </div>
          {% endfor %}
        {% endif %}
      {% endwith %}
      {% block content %}{% endblock %}
    </div>
  </div>
</div>
<script src="{{ url_for('static', filename='vendor/tabler/js/tabler.min.js') }}"></script>
{% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 3: Rewrite `static/style.css`**

```css
/* AFAD kurumsal renk override'ı — Tabler'ın hazır "orange" temasının üzerine
   tam AFAD turuncu-kırmızısını (#c8102e) uygular. Bileşenlerin geri kalanı
   (kartlar, tablolar, formlar, rozetler) doğrudan Tabler'dan gelir. */
[data-bs-theme-primary="orange"] {
  --tblr-primary: #c8102e;
  --tblr-primary-rgb: 200, 16, 46;
}
```

- [ ] **Step 4: Automated syntax check**

```bash
cd /c/AP/is_takip
python -c "import jinja2; jinja2.Environment().parse(open('templates/base.html', encoding='utf-8').read()); jinja2.Environment().parse(open('templates/_macros.html', encoding='utf-8').read()); print('OK: base.html and _macros.html parse')"
```

Expected: `OK: base.html and _macros.html parse`

- [ ] **Step 5: Manual browser check**

Every other template still has its old (now Tabler-CSS-free) markup at this point, so full pages will look broken — that's expected until later tasks. For this step, only confirm the shell itself works:

1. `cd C:\AP\is_takip && python app.py`
2. Open `http://127.0.0.1:5000/` in a browser, log in.
3. Confirm: the top bar is solid AFAD red/orange (`#c8102e`) with the AFAD logo on a white badge and "Görev Takip Sistemi" text: PASS/FAIL.
4. Confirm: below it, a white sub-bar shows the role-appropriate nav links (Panel + admin links, or Panel + Personelim for a manager account): PASS/FAIL.
5. Narrow the browser to ~400px width and confirm the hamburger button appears and toggles the nav links: PASS/FAIL.
6. Trigger a flash message (e.g. submit wrong password on `/login` first, before logging in) and confirm it renders as a dismissible Tabler alert, not the old plain-colored `<div class="flash">`: PASS/FAIL.

- [ ] **Step 6: Commit**

```bash
cd /c/AP/is_takip
git add templates/base.html templates/_macros.html static/style.css
git commit -m "$(cat <<'EOF'
feat: rebuild base.html as a Tabler navbar shell

Replaces the hand-rolled topbar/CSS shell with Tabler's horizontal
navbar pattern, AFAD-red themed via a two-line CSS variable override.
Adds templates/_macros.html with shared status/priority badge and
progress-bar macros for later page migrations to reuse.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RxQXtwis8wHHAeq5r3kHQP
EOF
)"
```

---

## Task 3: Redesign `login.html`

**Files:**
- Modify: `templates/login.html` (full rewrite)

**Interfaces:**
- Consumes: `templates/base.html` (Task 2), form posts to the same implicit URL (`method="post"` on the current page, unchanged — the `login` view in `app.py` is untouched), field names `username`/`password` (unchanged).

- [ ] **Step 1: Rewrite `templates/login.html`**

```jinja
{% extends "base.html" %}
{% block title %}Giriş{% endblock %}
{% block content %}
<div class="row justify-content-center">
  <div class="col-12 col-sm-8 col-md-6 col-lg-4">
    <div class="text-center mb-4">
      <img src="{{ url_for('static', filename='img/afad-logo.png') }}" alt="AFAD" style="height: 56px; width: auto;">
    </div>
    <div class="card card-md">
      <div class="card-body">
        <h2 class="h2 text-center mb-1">Görev Takip Sistemi</h2>
        <div class="text-secondary text-center mb-4">AFAD — Şube Müdürlüğü İşlem Takibi</div>
        <form method="post" autocomplete="off">
          <div class="mb-3">
            <label class="form-label">Kullanıcı Adı</label>
            <input type="text" name="username" class="form-control" required autofocus>
          </div>
          <div class="mb-3">
            <label class="form-label">Şifre</label>
            <input type="password" name="password" class="form-control" required>
          </div>
          <div class="form-footer">
            <button type="submit" class="btn btn-primary w-100">Giriş Yap</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Automated syntax check**

```bash
cd /c/AP/is_takip
python -c "import jinja2; jinja2.Environment().parse(open('templates/login.html', encoding='utf-8').read()); print('OK: login.html parses')"
```

Expected: `OK: login.html parses`

- [ ] **Step 3: Manual browser check**

1. `cd C:\AP\is_takip && python app.py`, open `http://127.0.0.1:5000/login` (log out first if needed).
2. Confirm: centered card, AFAD logo above it, "Görev Takip Sistemi" title, subtitle, username/password fields, full-width red "Giriş Yap" button: PASS/FAIL.
3. Submit an intentionally wrong password and confirm the flash error renders as a red Tabler alert above the form (base.html's alert block, still working): PASS/FAIL.
4. Log in with valid credentials and confirm redirect to the dashboard succeeds (no behavior change): PASS/FAIL.

- [ ] **Step 4: Commit**

```bash
cd /c/AP/is_takip
git add templates/login.html
git commit -m "$(cat <<'EOF'
feat: redesign login page with Tabler auth card

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RxQXtwis8wHHAeq5r3kHQP
EOF
)"
```

---

## Task 4: Redesign `dashboard.html` (cards, table, ApexCharts donut)

**Files:**
- Modify: `templates/dashboard.html` (full rewrite)

**Interfaces:**
- Consumes: `templates/_macros.html` macros `m.status_badge`, `m.priority_badge`, `m.progress_bar`, `m.status_color` (Task 2). Context variables from `app.py`'s `dashboard()` view (all unchanged): `tasks`, `user`, `departments`, `managers`, `summary`, `overall_counts`, `overall_total`, `overdue_count`, `stale_count`, `dept_filter`, `status_filter`, `user_filter`, `q`, `sort`, `sort_dir`; globals `STATUSES`, `is_overdue(t)`, `is_stale(t)`, `days_since_update(t)`. Routes: `dashboard`, `task_detail`. Vendor script: `static/vendor/tabler/js/apexcharts.min.js` (Task 1).
- Produces: nothing consumed by later tasks (dashboard is a leaf page), but the ApexCharts-in-`{% block scripts %}` pattern used here (data arrays built with a Jinja `for` loop instead of Python-style comprehensions, since Jinja2 has no list comprehensions) is the pattern Task 6 (`statistics.html`) repeats — keep it consistent.

- [ ] **Step 1: Rewrite `templates/dashboard.html`**

```jinja
{% extends "base.html" %}
{% import "_macros.html" as m %}
{% block title %}Panel{% endblock %}
{% block content %}

<div class="page-header d-print-none">
  <div class="row align-items-center">
    <div class="col">
      <h2 class="page-title">{% if user.role == 'admin' %}Genel Görünüm{% else %}İşlemlerim{% endif %}</h2>
    </div>
    <div class="col-auto">
      {% if overdue_count > 0 %}<span class="badge bg-red-lt me-1">{{ overdue_count }} gecikmiş işlem</span>{% endif %}
      {% if stale_count > 0 %}<span class="badge bg-yellow-lt">{{ stale_count }} durağan işlem</span>{% endif %}
    </div>
  </div>
</div>

{% if overall_total > 0 %}
<div class="card mb-3">
  <div class="card-body">
    <h3 class="card-title">Genel Durum Dağılımı <span class="text-secondary fw-normal">({{ overall_total }} işlem)</span></h3>
    <div id="chart-status-overall" style="min-height: 220px;"></div>
  </div>
</div>
{% endif %}

{% if user.role == 'admin' and summary %}
<div class="row row-cards mb-3">
  {% for dept, counts in summary.items() %}
  {% set dept_total = counts.values()|sum %}
  <div class="col-sm-6 col-lg-4">
    <div class="card card-sm">
      <div class="card-body">
        <div class="d-flex align-items-center justify-content-between mb-2">
          <div class="fw-medium">{{ dept or "Atanmamış" }}</div>
          <div class="text-secondary small">{{ dept_total }} işlem</div>
        </div>
        <div class="progress progress-sm mb-2">
          {% for s in STATUSES %}
          {% set pct = (counts[s] / dept_total * 100) if dept_total else 0 %}
          {% if pct > 0 %}
          <div class="progress-bar bg-{{ m.status_color(s) }}" style="width: {{ pct }}%" title="{{ s }}: {{ counts[s] }}"></div>
          {% endif %}
          {% endfor %}
        </div>
        <div class="d-flex flex-wrap gap-2 small text-secondary">
          <span>Bekliyor <b class="text-body">{{ counts.get('Bekliyor', 0) }}</b></span>
          <span>Devam Ediyor <b class="text-body">{{ counts.get('Devam Ediyor', 0) }}</b></span>
          <span>Tamamlandı <b class="text-green">{{ counts.get('Tamamlandı', 0) }}</b></span>
          <span>İptal <b class="text-body">{{ counts.get('İptal', 0) }}</b></span>
        </div>
      </div>
    </div>
  </div>
  {% endfor %}
</div>
{% endif %}

<div class="card mb-3">
  <div class="card-body">
    {% if user.role == 'admin' %}
    <form method="get" class="row g-2 align-items-center">
      <div class="col-12 col-md-3">
        <input type="text" name="q" value="{{ q }}" placeholder="İşlem ara..." class="form-control">
      </div>
      <div class="col-6 col-md-3">
        <select name="department" class="form-select" onchange="this.form.submit()">
          <option value="">Tüm Şubeler</option>
          {% for d in departments %}
          <option value="{{ d }}" {% if d == dept_filter %}selected{% endif %}>{{ d }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="col-6 col-md-3">
        <select name="assigned_to" class="form-select" onchange="this.form.submit()">
          <option value="">Tüm Şube Müdürleri</option>
          {% for mgr in managers %}
          <option value="{{ mgr.id }}" {% if user_filter == mgr.id|string %}selected{% endif %}>{{ mgr.full_name }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="col-6 col-md-2">
        <select name="status" class="form-select" onchange="this.form.submit()">
          <option value="">Tüm Durumlar</option>
          {% for s in STATUSES %}
          <option value="{{ s }}" {% if s == status_filter %}selected{% endif %}>{{ s }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="col-auto">
        <button type="submit" class="btn btn-primary">Ara</button>
      </div>
      {% if dept_filter or status_filter or user_filter or q %}
      <div class="col-auto">
        <a href="{{ url_for('dashboard') }}" class="btn btn-link">Filtreleri Temizle</a>
      </div>
      {% endif %}
    </form>
    {% else %}
    <form method="get" class="row g-2 align-items-center">
      <div class="col-12 col-md-4">
        <input type="text" name="q" value="{{ q }}" placeholder="İşlem ara..." class="form-control">
      </div>
      <div class="col-auto">
        <button type="submit" class="btn btn-primary">Ara</button>
      </div>
      {% if q %}
      <div class="col-auto">
        <a href="{{ url_for('dashboard') }}" class="btn btn-link">Temizle</a>
      </div>
      {% endif %}
    </form>
    {% endif %}
  </div>

  {% macro sort_link(key, label) %}
  {% set new_dir = 'desc' if sort == key and sort_dir == 'asc' else 'asc' %}
  <a class="text-reset" href="{{ url_for('dashboard', sort=key, dir=new_dir, department=dept_filter, assigned_to=user_filter, status=status_filter, q=q) }}">{{ label }}{% if sort == key %} <span class="text-primary">{{ '▲' if sort_dir == 'asc' else '▼' }}</span>{% endif %}</a>
  {% endmacro %}
  <div class="table-responsive">
    <table class="table table-vcenter card-table">
      <thead>
        <tr>
          <th>Sıra No</th>
          <th>{{ sort_link('title', 'İşlem') }}</th>
          {% if user.role == 'admin' %}<th>Şube</th><th>Sorumlu</th>{% endif %}
          <th>{{ sort_link('priority', 'Öncelik') }}</th>
          <th>{{ sort_link('status', 'Durum') }}</th>
          <th>{{ sort_link('progress', 'İlerleme') }}</th>
          <th>{{ sort_link('due_date', 'Termin') }}</th>
        </tr>
      </thead>
      <tbody>
        {% for t in tasks %}
        <tr style="cursor: pointer;" class="{% if is_overdue(t) %}table-danger{% elif is_stale(t) %}table-warning{% endif %}" onclick="window.location='{{ url_for('task_detail', task_id=t.id) }}'">
          <td>{{ loop.index }}</td>
          <td class="fw-medium">{{ t.title }}</td>
          {% if user.role == 'admin' %}
          <td>{{ t.department or "-" }}</td>
          <td>{{ t.assigned_name }}</td>
          {% endif %}
          <td>{{ m.priority_badge(t.priority) }}</td>
          <td>
            {{ m.status_badge(t.status) }}
            {% if is_stale(t) and not is_overdue(t) %}<div class="text-yellow small mt-1">{{ days_since_update(t) }} gündür güncellenmedi</div>{% endif %}
          </td>
          <td style="min-width: 100px;">{{ m.progress_bar(t.progress) }}</td>
          <td>{% if t.due_date %}{{ t.due_date }}{% if is_overdue(t) %} <span class="text-red fw-bold small">gecikti</span>{% endif %}{% else %}-{% endif %}</td>
        </tr>
        {% else %}
        <tr><td colspan="8" class="text-center text-secondary py-4">Henüz işlem yok. "+ Yeni İşlem" ile ekleyebilirsiniz.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>

<div class="text-secondary small d-print-none">
  Sistemi nasıl kullanacağınızı mı unuttunuz?
  <a href="{{ url_for('static', filename='rehber/kullanim-rehberi.pdf') }}" target="_blank">Kullanım Rehberini (PDF) açın</a>
</div>
{% endblock %}

{% block scripts %}
{% if overall_total > 0 %}
<script src="{{ url_for('static', filename='vendor/tabler/js/apexcharts.min.js') }}"></script>
<script>
new ApexCharts(document.getElementById('chart-status-overall'), {
  chart: { type: 'donut', height: 220 },
  series: [{% for s in STATUSES %}{{ overall_counts[s] }}{% if not loop.last %},{% endif %}{% endfor %}],
  labels: [{% for s in STATUSES %}{{ s|tojson }}{% if not loop.last %},{% endif %}{% endfor %}],
  colors: ['#adb5bd', '#4299e1', '#2fb344', '#495057'],
  legend: { position: 'bottom' },
  dataLabels: { enabled: false },
}).render();
</script>
{% endif %}
{% endblock %}
```

- [ ] **Step 2: Automated syntax check**

```bash
cd /c/AP/is_takip
python -c "import jinja2; jinja2.Environment().parse(open('templates/dashboard.html', encoding='utf-8').read()); print('OK: dashboard.html parses')"
```

Expected: `OK: dashboard.html parses`

- [ ] **Step 3: Manual browser check**

1. `cd C:\AP\is_takip && python app.py`, log in as an **admin** account, open `http://127.0.0.1:5000/`.
2. Confirm: page title "Genel Görünüm", red/yellow badge chips for overdue/durağan counts (if any exist), a donut chart under "Genel Durum Dağılımı" rendering slices with a bottom legend: PASS/FAIL.
3. Confirm: per-department cards render below with a thin stacked progress bar and status counts: PASS/FAIL.
4. Confirm: the filter row (search/şube/şube müdürü/durum selects) and "Ara" button work — pick a department filter and confirm the URL updates and the table filters: PASS/FAIL.
5. Confirm: clicking a column header (e.g. "İşlem") still sorts (arrow indicator appears): PASS/FAIL.
6. Confirm: clicking a table row navigates to that task's detail page: PASS/FAIL.
7. Log out, log in as a **manager** account, open `http://127.0.0.1:5000/` and confirm the manager-only layout (title "İşlemlerim", no Şube/Sorumlu columns, simpler search-only filter row, no per-department cards): PASS/FAIL.

- [ ] **Step 4: Commit**

```bash
cd /c/AP/is_takip
git add templates/dashboard.html
git commit -m "$(cat <<'EOF'
feat: redesign dashboard with Tabler cards/table and ApexCharts donut

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RxQXtwis8wHHAeq5r3kHQP
EOF
)"
```

---

## Task 5: Redesign `task_form.html` + `task_detail.html`

**Files:**
- Modify: `templates/task_form.html` (full rewrite)
- Modify: `templates/task_detail.html` (full rewrite)

**Interfaces:**
- Consumes: `templates/_macros.html` (Task 2). `task_form.html` context (from `new_task()`, unchanged): `user`, `managers`, `personnel_options`, `PRIORITIES` (global). `task_detail.html` context (from `task_detail()`, unchanged): `task`, `user`, `assigned_personnel`, `assigned_personnel_ids`, `personnel_options`, `attachments`, `notes`, `STATUSES` (global), `is_overdue`, `is_stale`, `days_since_update` (globals). Routes: `delete_task`, `upload_attachment`, `download_attachment`, `delete_note`, `dashboard`.

- [ ] **Step 1: Rewrite `templates/task_form.html`**

```jinja
{% extends "base.html" %}
{% block title %}Yeni İşlem{% endblock %}
{% block content %}
<div class="row justify-content-center">
  <div class="col-12 col-lg-8">
    <div class="card">
      <div class="card-header"><h2 class="card-title">Yeni İşlem Ekle</h2></div>
      <div class="card-body">
        <form method="post">
          <div class="mb-3">
            <label class="form-label">İşlem Başlığı</label>
            <input type="text" name="title" class="form-control" required placeholder="Örn: Deprem tatbikatı raporu hazırlanması">
          </div>
          <div class="mb-3">
            <label class="form-label">Açıklama</label>
            <textarea name="description" class="form-control" rows="3" placeholder="Detaylar, ilgili yazışma no vb."></textarea>
          </div>

          {% if user.role == 'admin' %}
          <div class="mb-3">
            <label class="form-label">Sorumlu Şube Müdürü</label>
            <select name="assigned_to" class="form-select" required>
              <option value="">Seçiniz</option>
              {% for mgr in managers %}
              <option value="{{ mgr.id }}">{{ mgr.full_name }} ({{ mgr.department }})</option>
              {% endfor %}
            </select>
          </div>
          {% else %}
          <input type="hidden" name="assigned_to" value="{{ managers[0].id }}">
          {% if personnel_options %}
          <div class="mb-3">
            <label class="form-label">Sorumlu Personel (opsiyonel, birden fazla seçilebilir)</label>
            <div class="divide-y">
              {% for p in personnel_options %}
              <label class="form-check my-1">
                <input class="form-check-input" type="checkbox" name="personnel_ids" value="{{ p.id }}">
                <span class="form-check-label">{{ p.full_name }}</span>
              </label>
              {% endfor %}
            </div>
          </div>
          {% endif %}
          {% endif %}

          <div class="row">
            <div class="col-6">
              <div class="mb-3">
                <label class="form-label">Öncelik</label>
                <select name="priority" class="form-select">
                  {% for p in PRIORITIES %}
                  <option value="{{ p }}" {% if p == 'Orta' %}selected{% endif %}>{{ p }}</option>
                  {% endfor %}
                </select>
              </div>
            </div>
            <div class="col-6">
              <div class="mb-3">
                <label class="form-label">Termin Tarihi</label>
                <input type="date" name="due_date" class="form-control">
              </div>
            </div>
          </div>

          <div class="form-footer">
            <button type="submit" class="btn btn-primary">İşlemi Oluştur</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Rewrite `templates/task_detail.html`**

```jinja
{% extends "base.html" %}
{% import "_macros.html" as m %}
{% block title %}{{ task.title }}{% endblock %}
{% block content %}
<a href="{{ url_for('dashboard') }}" class="text-secondary d-print-none">← Panele dön</a>

<div class="page-header d-print-none">
  <div class="row align-items-center">
    <div class="col"><h2 class="page-title">{{ task.title }}</h2></div>
    {% if user.role == 'admin' %}
    <div class="col-auto">
      <form method="post" action="{{ url_for('delete_task', task_id=task.id) }}"
            onsubmit="return confirm('Bu işlemi kalıcı olarak silmek istediğinize emin misiniz? Ekli dosyalar ve notlar da silinecek.');">
        <button type="submit" class="btn btn-outline-danger">İşlemi Sil</button>
      </form>
    </div>
    {% endif %}
  </div>
</div>

<div class="card mb-3">
  <div class="card-body">
    <div class="d-flex flex-wrap gap-3 mb-3 small text-secondary">
      <span><b class="text-body">Şube:</b> {{ task.department or "-" }}</span>
      <span><b class="text-body">Sorumlu:</b> {{ task.assigned_name }}</span>
      {% if assigned_personnel %}<span><b class="text-body">Sorumlu Personel:</b> {{ assigned_personnel|map(attribute='full_name')|join(', ') }}</span>{% endif %}
      <span><b class="text-body">Öncelik:</b> {{ m.priority_badge(task.priority) }}</span>
      <span><b class="text-body">Oluşturulma:</b> {{ task.created_at }}</span>
      {% if task.due_date %}<span><b class="text-body">Termin:</b> {{ task.due_date }}{% if is_overdue(task) %} <span class="text-red fw-bold">gecikti</span>{% endif %}</span>{% endif %}
    </div>
    {% if is_stale(task) and not is_overdue(task) %}
    <div class="alert alert-warning">Bu işlem {{ days_since_update(task) }} gündür güncellenmedi. Güncel durumu teyit edin.</div>
    {% endif %}
    {% if task.description %}
    <p class="bg-secondary-lt p-3 rounded">{{ task.description }}</p>
    {% endif %}

    <form method="post" class="border-top pt-3 mt-3">
      <div class="row">
        <div class="col-md-6">
          <div class="mb-3">
            <label class="form-label">Durum</label>
            <select name="status" class="form-select">
              {% for s in STATUSES %}
              <option value="{{ s }}" {% if s == task.status %}selected{% endif %}>{{ s }}</option>
              {% endfor %}
            </select>
          </div>
        </div>
        <div class="col-md-6">
          <div class="mb-3">
            <label class="form-label">İlerleme (%)</label>
            <input type="number" name="progress" class="form-control" min="0" max="100" step="5" value="{{ task.progress }}">
          </div>
        </div>
      </div>
      {% if user.role == 'manager' %}
      <div class="mb-3">
        <label class="form-label">Sorumlu Personel (opsiyonel, birden fazla seçilebilir)</label>
        <div class="divide-y">
          {% for p in personnel_options %}
          <label class="form-check my-1">
            <input class="form-check-input" type="checkbox" name="personnel_ids" value="{{ p.id }}" {% if p.id in assigned_personnel_ids %}checked{% endif %}>
            <span class="form-check-label">{{ p.full_name }}{% if not p.is_active %} (pasif){% endif %}</span>
          </label>
          {% endfor %}
        </div>
      </div>
      {% endif %}
      <div class="mb-3">
        <label class="form-label">Not ekle (opsiyonel)</label>
        <textarea name="note" class="form-control" rows="2" placeholder="Yapılan işlem, gecikme sebebi vb."></textarea>
      </div>
      <button type="submit" class="btn btn-primary">Güncelle</button>
    </form>
  </div>
</div>

<div class="card mb-3 d-print-none">
  <div class="card-header"><h3 class="card-title">Ekli Dosyalar</h3></div>
  <div class="card-body">
    <form method="post" action="{{ url_for('upload_attachment', task_id=task.id) }}" enctype="multipart/form-data" class="row g-2 align-items-center mb-3">
      <div class="col-auto flex-fill"><input type="file" name="file" class="form-control" required></div>
      <div class="col-auto"><button type="submit" class="btn btn-primary">Dosya Ekle</button></div>
    </form>
    {% if attachments %}
    <div class="list-group list-group-flush">
      {% for a in attachments %}
      <div class="list-group-item d-flex justify-content-between align-items-center">
        <div>
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon me-1"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M15 7l-6.5 6.5a1.5 1.5 0 0 0 3 3l6.5 -6.5a3 3 0 0 0 -6 -6l-6.5 6.5a4.5 4.5 0 0 0 9 9l6.5 -6.5" /></svg>
          <a href="{{ url_for('download_attachment', task_id=task.id, attachment_id=a.id) }}">{{ a.original_name }}</a>
        </div>
        <span class="text-secondary small">{{ a.full_name }} — {{ a.uploaded_at }}</span>
      </div>
      {% endfor %}
    </div>
    {% else %}
    <p class="text-secondary">Henüz dosya eklenmemiş.</p>
    {% endif %}
  </div>
</div>

<div class="card">
  <div class="card-header"><h3 class="card-title">Geçmiş Notlar</h3></div>
  <div class="card-body">
    {% if notes %}
    <div class="list-group list-group-flush">
      {% for n in notes %}
      <div class="list-group-item d-flex justify-content-between align-items-start">
        <div><b>{{ n.full_name }}</b> — <span class="text-secondary small">{{ n.created_at }}</span><br>{{ n.note }}</div>
        {% if user.role == 'admin' %}
        <form method="post" action="{{ url_for('delete_note', task_id=task.id, note_id=n.id) }}" class="d-print-none"
              onsubmit="return confirm('Bu notu silmek istediğinize emin misiniz?');">
          <button type="submit" class="btn btn-link text-danger btn-sm p-0">Sil</button>
        </form>
        {% endif %}
      </div>
      {% endfor %}
    </div>
    {% else %}
    <p class="text-secondary">Henüz not eklenmemiş.</p>
    {% endif %}
  </div>
</div>
{% endblock %}
```

- [ ] **Step 3: Automated syntax check**

```bash
cd /c/AP/is_takip
python -c "
import jinja2
for f in ['templates/task_form.html', 'templates/task_detail.html']:
    jinja2.Environment().parse(open(f, encoding='utf-8').read())
    print('OK:', f)
"
```

Expected: `OK: templates/task_form.html` and `OK: templates/task_detail.html`.

- [ ] **Step 4: Manual browser check**

1. `cd C:\AP\is_takip && python app.py`, log in as **admin**, click "+ Yeni İşlem".
2. Confirm: card-framed form, "Sorumlu Şube Müdürü" select shown (admin path), priority/termin side-by-side, submit creates a task and redirects as before: PASS/FAIL.
3. Log in as **manager**, click "+ Yeni İşlem"; confirm the "Sorumlu Personel" checkbox list (if any personnel exist) renders with Tabler `form-check` styling and multiple boxes can be checked: PASS/FAIL.
4. Open any task's detail page. Confirm: meta row, priority badge, description block, status/progress form, notes list, attachment upload/list all render and the AFAD-red "İşlemi Sil" outline button (admin only) shows a confirm dialog on click: PASS/FAIL.
5. As manager on a task assigned to them, confirm the personnel checkboxes on the detail page pre-check the currently assigned personnel (`assigned_personnel_ids`): PASS/FAIL.
6. Submit the status/progress/note form and confirm the update persists (no behavior change): PASS/FAIL.
7. Upload a file and confirm it appears in the attachment list with a paperclip icon and can be downloaded: PASS/FAIL.

- [ ] **Step 5: Commit**

```bash
cd /c/AP/is_takip
git add templates/task_form.html templates/task_detail.html
git commit -m "$(cat <<'EOF'
feat: redesign task creation and task detail pages with Tabler forms

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RxQXtwis8wHHAeq5r3kHQP
EOF
)"
```

---

## Task 6: Redesign `reports.html` + `statistics.html` (remaining ApexCharts)

**Files:**
- Modify: `templates/reports.html` (full rewrite)
- Modify: `templates/statistics.html` (full rewrite)

**Interfaces:**
- Consumes: `templates/_macros.html` (Task 2), `static/vendor/tabler/js/apexcharts.min.js` (Task 1), the dashboard's Jinja-array-building script pattern (Task 4). `reports.html` context (from `reports()`, unchanged): `department`, `start_date`, `end_date`, `status`, `departments`, `STATUSES` (global), `total_tasks`, `report` (dict of `dept -> {overdue, stale, tasks, counts, avg_days}`), `is_overdue`. Routes: `export_report`, `reports`. `statistics.html` context (from `statistics()`, unchanged): `PRIORITIES`, `STATUSES` (globals), `priority_counts`, `priority_total`, `dept_compare` (list of `{name, total, completed, overdue}`), `dept_max`, `weeks` (list of `{label, created, completed}`), `week_max`, `manager_perf`, `manager_overdue`.

- [ ] **Step 1: Rewrite `templates/reports.html`**

```jinja
{% extends "base.html" %}
{% import "_macros.html" as m %}
{% block title %}Raporlar{% endblock %}
{% block content %}
<div class="page-header d-print-none">
  <div class="row align-items-center">
    <div class="col"><h2 class="page-title">Şube Bazlı Rapor</h2></div>
    <div class="col-auto">
      <a href="{{ url_for('export_report', department=department, start_date=start_date, end_date=end_date, status=status) }}" class="btn btn-outline-primary">Excel'e Aktar</a>
    </div>
  </div>
</div>

<div class="card mb-3 d-print-none">
  <div class="card-body">
    <form method="get" class="row g-2 align-items-center">
      <div class="col-auto">
        <select name="department" class="form-select" onchange="this.form.submit()">
          <option value="">Tüm Şubeler</option>
          {% for d in departments %}
          <option value="{{ d }}" {% if d == department %}selected{% endif %}>{{ d }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="col-auto">
        <select name="status" class="form-select" onchange="this.form.submit()">
          <option value="">Tüm Durumlar</option>
          {% for s in STATUSES %}
          <option value="{{ s }}" {% if s == status %}selected{% endif %}>{{ s }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="col-auto">
        <label class="input-group input-group-flat" style="width: auto;">
          <span class="input-group-text">Başlangıç</span>
          <input type="date" name="start_date" value="{{ start_date }}" class="form-control" onchange="this.form.submit()">
        </label>
      </div>
      <div class="col-auto">
        <label class="input-group input-group-flat" style="width: auto;">
          <span class="input-group-text">Bitiş</span>
          <input type="date" name="end_date" value="{{ end_date }}" class="form-control" onchange="this.form.submit()">
        </label>
      </div>
      {% if department or status or start_date or end_date %}
      <div class="col-auto"><a href="{{ url_for('reports') }}" class="btn btn-link">Filtreleri Temizle</a></div>
      {% endif %}
      <div class="col-auto"><button type="button" onclick="window.print()" class="btn btn-outline-secondary">Yazdır</button></div>
    </form>
  </div>
</div>

<p class="text-secondary d-print-none">Toplam {{ total_tasks }} işlem, {{ report|length }} şube.</p>

{% for dept, data in report.items()|sort %}
<div class="card mb-3">
  <div class="card-header">
    <h3 class="card-title">{{ dept }}</h3>
    <div class="card-actions">
      {% if data.overdue > 0 %}<span class="badge bg-red-lt me-1">{{ data.overdue }} gecikmiş</span>{% endif %}
      {% if data.stale > 0 %}<span class="badge bg-yellow-lt">{{ data.stale }} durağan</span>{% endif %}
    </div>
  </div>
  <div class="card-body border-bottom">
    <div class="row row-cards">
      <div class="col-auto"><div class="text-secondary small">Toplam</div><div class="h3 m-0">{{ data.tasks|length }}</div></div>
      <div class="col-auto"><div class="text-secondary small">Bekliyor</div><div class="h3 m-0">{{ data.counts['Bekliyor'] }}</div></div>
      <div class="col-auto"><div class="text-secondary small">Devam Ediyor</div><div class="h3 m-0">{{ data.counts['Devam Ediyor'] }}</div></div>
      <div class="col-auto"><div class="text-secondary small">Tamamlandı</div><div class="h3 m-0 text-green">{{ data.counts['Tamamlandı'] }}</div></div>
      <div class="col-auto"><div class="text-secondary small">İptal</div><div class="h3 m-0">{{ data.counts['İptal'] }}</div></div>
      <div class="col-auto"><div class="text-secondary small">Ort. Tamamlama</div><div class="h3 m-0">{% if data.avg_days is not none %}{{ data.avg_days }} gün{% else %}-{% endif %}</div></div>
    </div>
  </div>
  <div class="table-responsive">
    <table class="table table-vcenter card-table">
      <thead>
        <tr><th>Sıra No</th><th>İşlem</th><th>Sorumlu</th><th>Öncelik</th><th>Durum</th><th>İlerleme</th><th>Oluşturulma</th><th>Termin</th></tr>
      </thead>
      <tbody>
        {% for t in data.tasks %}
        <tr class="{% if is_overdue(t) %}table-danger{% endif %}">
          <td>{{ loop.index }}</td>
          <td>{{ t.title }}</td>
          <td>{{ t.assigned_name }}</td>
          <td>{{ m.priority_badge(t.priority) }}</td>
          <td>{{ m.status_badge(t.status) }}</td>
          <td style="min-width: 100px;">{{ m.progress_bar(t.progress) }}</td>
          <td>{{ t.created_at[:10] }}</td>
          <td>{% if t.due_date %}{{ t.due_date }}{% if is_overdue(t) %} <span class="text-red fw-bold small">gecikti</span>{% endif %}{% else %}-{% endif %}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% else %}
<p class="text-secondary">Seçilen filtrelere uygun işlem bulunamadı.</p>
{% endfor %}
{% endblock %}
```

- [ ] **Step 2: Rewrite `templates/statistics.html`**

```jinja
{% extends "base.html" %}
{% block title %}İstatistikler{% endblock %}
{% block content %}
<div class="page-header"><h2 class="page-title">İstatistikler</h2></div>

<div class="row row-cards mb-3">
  <div class="col-12 col-lg-6">
    <div class="card h-100">
      <div class="card-body">
        <h3 class="card-title">Öncelik Dağılımı <span class="text-secondary fw-normal">({{ priority_total }} işlem)</span></h3>
        {% if priority_total > 0 %}
        <div id="chart-priority" style="min-height: 240px;"></div>
        {% else %}
        <p class="text-secondary">Henüz işlem yok.</p>
        {% endif %}
      </div>
    </div>
  </div>
  <div class="col-12 col-lg-6">
    <div class="card h-100">
      <div class="card-body">
        <h3 class="card-title">Haftalık Eğilim <span class="text-secondary fw-normal">(son 8 hafta)</span></h3>
        <div id="chart-weekly" style="min-height: 240px;"></div>
      </div>
    </div>
  </div>
</div>

<div class="card mb-3">
  <div class="card-body">
    <h3 class="card-title">Şube Karşılaştırması <span class="text-secondary fw-normal">(toplam / tamamlanan / geciken)</span></h3>
    {% if dept_compare %}
    <div id="chart-dept-compare" style="min-height: {{ (dept_compare|length * 70) + 40 }}px;"></div>
    {% else %}
    <p class="text-secondary">Henüz veri yok.</p>
    {% endif %}
  </div>
</div>

<h2 class="mb-3">Sorumlu Bazında Performans</h2>
<div class="row row-cards">
  {% for name, counts in manager_perf.items()|sort %}
  {% set total = counts.values()|sum %}
  <div class="col-sm-6 col-lg-4">
    <div class="card card-sm">
      <div class="card-body">
        <div class="fw-medium mb-2">{{ name }}</div>
        <div class="progress progress-sm mb-2">
          {% for s in STATUSES %}
          {% set pct = (counts[s] / total * 100) if total else 0 %}
          {% if pct > 0 %}
          <div class="progress-bar bg-{{ {'Bekliyor': 'secondary', 'Devam Ediyor': 'blue', 'Tamamlandı': 'green', 'İptal': 'dark'}[s] }}" style="width: {{ pct }}%" title="{{ s }}: {{ counts[s] }}"></div>
          {% endif %}
          {% endfor %}
        </div>
        <div class="d-flex flex-wrap gap-2 small text-secondary">
          <span>Bekliyor <b class="text-body">{{ counts.get('Bekliyor', 0) }}</b></span>
          <span>Devam Ediyor <b class="text-body">{{ counts.get('Devam Ediyor', 0) }}</b></span>
          <span>Tamamlandı <b class="text-green">{{ counts.get('Tamamlandı', 0) }}</b></span>
          <span>Geciken <b class="text-red">{{ manager_overdue.get(name, 0) }}</b></span>
        </div>
      </div>
    </div>
  </div>
  {% else %}
  <p class="text-secondary">Henüz veri yok.</p>
  {% endfor %}
</div>
{% endblock %}

{% block scripts %}
<script src="{{ url_for('static', filename='vendor/tabler/js/apexcharts.min.js') }}"></script>
{% if priority_total > 0 %}
<script>
new ApexCharts(document.getElementById('chart-priority'), {
  chart: { type: 'donut', height: 240 },
  series: [{% for p in PRIORITIES %}{{ priority_counts[p] }}{% if not loop.last %},{% endif %}{% endfor %}],
  labels: [{% for p in PRIORITIES %}{{ p|tojson }}{% if not loop.last %},{% endif %}{% endfor %}],
  colors: ['#adb5bd', '#4299e1', '#f59f00', '#d63939'],
  legend: { position: 'bottom' },
  dataLabels: { enabled: false },
}).render();
</script>
{% endif %}

<script>
new ApexCharts(document.getElementById('chart-weekly'), {
  chart: { type: 'bar', height: 240, toolbar: { show: false } },
  series: [
    { name: 'Oluşturulan', data: [{% for w in weeks %}{{ w.created }}{% if not loop.last %},{% endif %}{% endfor %}] },
    { name: 'Tamamlanan', data: [{% for w in weeks %}{{ w.completed }}{% if not loop.last %},{% endif %}{% endfor %}] },
  ],
  xaxis: { categories: [{% for w in weeks %}{{ w.label|tojson }}{% if not loop.last %},{% endif %}{% endfor %}] },
  colors: ['#4299e1', '#2fb344'],
  plotOptions: { bar: { columnWidth: '55%' } },
  legend: { position: 'bottom' },
}).render();
</script>

{% if dept_compare %}
<script>
new ApexCharts(document.getElementById('chart-dept-compare'), {
  chart: { type: 'bar', height: {{ (dept_compare|length * 70) + 40 }}, toolbar: { show: false } },
  series: [
    { name: 'Toplam', data: [{% for d in dept_compare %}{{ d.total }}{% if not loop.last %},{% endif %}{% endfor %}] },
    { name: 'Tamamlanan', data: [{% for d in dept_compare %}{{ d.completed }}{% if not loop.last %},{% endif %}{% endfor %}] },
    { name: 'Geciken', data: [{% for d in dept_compare %}{{ d.overdue }}{% if not loop.last %},{% endif %}{% endfor %}] },
  ],
  xaxis: { categories: [{% for d in dept_compare %}{{ d.name|tojson }}{% if not loop.last %},{% endif %}{% endfor %}] },
  colors: ['#adb5bd', '#2fb344', '#d63939'],
  plotOptions: { bar: { horizontal: true } },
  legend: { position: 'bottom' },
}).render();
</script>
{% endif %}
{% endblock %}
```

- [ ] **Step 3: Automated syntax check**

```bash
cd /c/AP/is_takip
python -c "
import jinja2
for f in ['templates/reports.html', 'templates/statistics.html']:
    jinja2.Environment().parse(open(f, encoding='utf-8').read())
    print('OK:', f)
"
```

Expected: `OK: templates/reports.html` and `OK: templates/statistics.html`.

- [ ] **Step 4: Manual browser check**

1. `cd C:\AP\is_takip && python app.py`, log in as **admin**, open `http://127.0.0.1:5000/reports`.
2. Confirm: filter row, "Excel'e Aktar"/"Yazdır" buttons, per-department cards with stat numbers and a Tabler table, all render: PASS/FAIL.
3. Click "Yazdır" (or use the browser's print preview) and confirm the navbar and filter row are hidden in the print view (`d-print-none` still works — this is a Bootstrap utility already bundled in `tabler.min.css`, not custom CSS): PASS/FAIL.
4. Click "Excel'e Aktar" and confirm the `.xlsx` download still works unchanged: PASS/FAIL.
5. Open `http://127.0.0.1:5000/statistics`. Confirm: a priority donut chart, a weekly bar chart (oluşturulan vs tamamlanan), a horizontal department-comparison bar chart, and per-manager performance cards all render with real data (hover a chart bar/slice and confirm a tooltip with the value appears): PASS/FAIL.
6. Resize to mobile width (~400px) and confirm the two top charts stack to one column and remain readable: PASS/FAIL.

- [ ] **Step 5: Commit**

```bash
cd /c/AP/is_takip
git add templates/reports.html templates/statistics.html
git commit -m "$(cat <<'EOF'
feat: redesign reports and statistics pages with Tabler + ApexCharts

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RxQXtwis8wHHAeq5r3kHQP
EOF
)"
```

---

## Task 7: Redesign `users.html` + `edit_user.html`

**Files:**
- Modify: `templates/users.html` (full rewrite)
- Modify: `templates/edit_user.html` (full rewrite)

**Interfaces:**
- Consumes: `users.html` context (from `users()`, unchanged): `managers`. `edit_user.html` context (from `edit_user()`, unchanged): `manager`. Routes: `edit_user`, `toggle_user`.

- [ ] **Step 1: Rewrite `templates/users.html`**

```jinja
{% extends "base.html" %}
{% block title %}Şube Müdürleri{% endblock %}
{% block content %}
<div class="page-header"><h2 class="page-title">Şube Müdürleri</h2></div>

<div class="row row-cards">
  <div class="col-12 col-lg-4">
    <div class="card">
      <div class="card-header"><h3 class="card-title">Yeni Şube Müdürü Ekle</h3></div>
      <div class="card-body">
        <form method="post">
          <div class="mb-3"><label class="form-label">Ad Soyad</label><input type="text" name="full_name" class="form-control" required></div>
          <div class="mb-3"><label class="form-label">Şube</label><input type="text" name="department" class="form-control" required placeholder="Örn: Planlama ve Zarar Azaltma Şube Müdürlüğü"></div>
          <div class="mb-3"><label class="form-label">Kullanıcı Adı</label><input type="text" name="username" class="form-control" required></div>
          <div class="mb-3"><label class="form-label">E-posta (bildirim için)</label><input type="email" name="email" class="form-control" placeholder="ornek@afad.gov.tr"></div>
          <div class="mb-3"><label class="form-label">Geçici Şifre</label><input type="text" name="password" class="form-control" required placeholder="İlk girişte değiştirmesini isteyin"></div>
          <button type="submit" class="btn btn-primary w-100">Ekle</button>
        </form>
      </div>
    </div>
  </div>

  <div class="col-12 col-lg-8">
    <div class="card">
      <div class="table-responsive">
        <table class="table table-vcenter card-table">
          <thead><tr><th>Ad Soyad</th><th>Şube</th><th>Kullanıcı Adı</th><th>E-posta</th><th>Durum</th><th colspan="2"></th></tr></thead>
          <tbody>
            {% for mgr in managers %}
            <tr>
              <td>{{ mgr.full_name }}</td>
              <td>{{ mgr.department }}</td>
              <td>{{ mgr.username }}</td>
              <td>{{ mgr.email or "-" }}</td>
              <td>{% if mgr.is_active %}<span class="badge bg-green-lt">Aktif</span>{% else %}<span class="badge bg-secondary-lt">Pasif</span>{% endif %}</td>
              <td><a href="{{ url_for('edit_user', user_id=mgr.id) }}" class="btn btn-sm btn-outline-primary">Düzenle</a></td>
              <td>
                <form method="post" action="{{ url_for('toggle_user', user_id=mgr.id) }}">
                  <button type="submit" class="btn btn-sm btn-outline-secondary">{% if mgr.is_active %}Pasifleştir{% else %}Aktifleştir{% endif %}</button>
                </form>
              </td>
            </tr>
            {% else %}
            <tr><td colspan="7" class="text-center text-secondary py-4">Henüz şube müdürü eklenmedi.</td></tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Rewrite `templates/edit_user.html`**

```jinja
{% extends "base.html" %}
{% block title %}Düzenle — {{ manager.full_name }}{% endblock %}
{% block content %}
<a href="{{ url_for('users') }}" class="text-secondary">← Şube müdürlerine dön</a>
<div class="row justify-content-center mt-2">
  <div class="col-12 col-lg-6">
    <div class="card">
      <div class="card-header"><h2 class="card-title">Şube Müdürünü Düzenle</h2></div>
      <div class="card-body">
        <form method="post">
          <div class="mb-3"><label class="form-label">Ad Soyad</label><input type="text" name="full_name" class="form-control" required value="{{ manager.full_name }}"></div>
          <div class="mb-3"><label class="form-label">Şube</label><input type="text" name="department" class="form-control" required value="{{ manager.department or '' }}"></div>
          <div class="mb-3"><label class="form-label">Kullanıcı Adı</label><input type="text" name="username" class="form-control" required value="{{ manager.username }}"></div>
          <div class="mb-3"><label class="form-label">E-posta (bildirim için)</label><input type="email" name="email" class="form-control" value="{{ manager.email or '' }}" placeholder="ornek@afad.gov.tr"></div>
          <div class="mb-3"><label class="form-label">Yeni Şifre (opsiyonel)</label><input type="text" name="password" class="form-control" placeholder="Boş bırakırsan şifre değişmez"></div>
          <button type="submit" class="btn btn-primary">Kaydet</button>
        </form>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 3: Automated syntax check**

```bash
cd /c/AP/is_takip
python -c "
import jinja2
for f in ['templates/users.html', 'templates/edit_user.html']:
    jinja2.Environment().parse(open(f, encoding='utf-8').read())
    print('OK:', f)
"
```

Expected: `OK: templates/users.html` and `OK: templates/edit_user.html`.

- [ ] **Step 4: Manual browser check**

1. `cd C:\AP\is_takip && python app.py`, log in as **admin**, open `http://127.0.0.1:5000/users`.
2. Confirm: left card has the "add manager" form, right card has the manager table with status badges and Düzenle/Pasifleştir buttons, layout stacks to one column on mobile width: PASS/FAIL.
3. Click "Düzenle" on any manager, confirm the edit card pre-fills existing values, save and confirm redirect back to the list with updated data: PASS/FAIL.
4. Click "Pasifleştir"/"Aktifleştir" on a manager and confirm the status badge flips (no behavior change): PASS/FAIL.

- [ ] **Step 5: Commit**

```bash
cd /c/AP/is_takip
git add templates/users.html templates/edit_user.html
git commit -m "$(cat <<'EOF'
feat: redesign branch manager list/edit pages with Tabler cards

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RxQXtwis8wHHAeq5r3kHQP
EOF
)"
```

---

## Task 8: Redesign `admins.html` + `edit_admin.html`

**Files:**
- Modify: `templates/admins.html` (full rewrite)
- Modify: `templates/edit_admin.html` (full rewrite)

**Interfaces:**
- Consumes: `admins.html` context (from `admins()`, unchanged): `admin_list`, `current_user_id`. `edit_admin.html` context (from `edit_admin()`, unchanged): `admin_user`. Routes: `edit_admin`, `toggle_admin`.

- [ ] **Step 1: Rewrite `templates/admins.html`**

```jinja
{% extends "base.html" %}
{% block title %}Yöneticiler{% endblock %}
{% block content %}
<div class="page-header"><h2 class="page-title">Yöneticiler</h2></div>
<p class="text-secondary">Bu sayfadan sistemi tüm şubeler genelinde görebilecek başka yönetici hesapları (örn. Müdür) ekleyebilirsiniz.</p>

<div class="row row-cards">
  <div class="col-12 col-lg-4">
    <div class="card">
      <div class="card-header"><h3 class="card-title">Yeni Yönetici Ekle</h3></div>
      <div class="card-body">
        <form method="post">
          <div class="mb-3"><label class="form-label">Ad Soyad</label><input type="text" name="full_name" class="form-control" required placeholder="Örn: Ahmet Kaya (Müdür)"></div>
          <div class="mb-3"><label class="form-label">Kullanıcı Adı</label><input type="text" name="username" class="form-control" required></div>
          <div class="mb-3"><label class="form-label">Geçici Şifre</label><input type="text" name="password" class="form-control" required placeholder="İlk girişte değiştirmesini isteyin"></div>
          <button type="submit" class="btn btn-primary w-100">Ekle</button>
        </form>
      </div>
    </div>
  </div>

  <div class="col-12 col-lg-8">
    <div class="card">
      <div class="table-responsive">
        <table class="table table-vcenter card-table">
          <thead><tr><th>Ad Soyad</th><th>Kullanıcı Adı</th><th>Durum</th><th colspan="2"></th></tr></thead>
          <tbody>
            {% for a in admin_list %}
            <tr>
              <td>{{ a.full_name }}{% if a.id == current_user_id %} <span class="text-secondary small">(siz)</span>{% endif %}</td>
              <td>{{ a.username }}</td>
              <td>{% if a.is_active %}<span class="badge bg-green-lt">Aktif</span>{% else %}<span class="badge bg-secondary-lt">Pasif</span>{% endif %}</td>
              <td><a href="{{ url_for('edit_admin', user_id=a.id) }}" class="btn btn-sm btn-outline-primary">Düzenle</a></td>
              <td>
                <form method="post" action="{{ url_for('toggle_admin', user_id=a.id) }}">
                  <button type="submit" class="btn btn-sm btn-outline-secondary">{% if a.is_active %}Pasifleştir{% else %}Aktifleştir{% endif %}</button>
                </form>
              </td>
            </tr>
            {% else %}
            <tr><td colspan="5" class="text-center text-secondary py-4">Henüz başka yönetici eklenmedi.</td></tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Rewrite `templates/edit_admin.html`**

```jinja
{% extends "base.html" %}
{% block title %}Düzenle — {{ admin_user.full_name }}{% endblock %}
{% block content %}
<a href="{{ url_for('admins') }}" class="text-secondary">← Yöneticilere dön</a>
<div class="row justify-content-center mt-2">
  <div class="col-12 col-lg-6">
    <div class="card">
      <div class="card-header"><h2 class="card-title">Yöneticiyi Düzenle</h2></div>
      <div class="card-body">
        <form method="post">
          <div class="mb-3"><label class="form-label">Ad Soyad</label><input type="text" name="full_name" class="form-control" required value="{{ admin_user.full_name }}"></div>
          <div class="mb-3"><label class="form-label">Kullanıcı Adı</label><input type="text" name="username" class="form-control" required value="{{ admin_user.username }}"></div>
          <div class="mb-3"><label class="form-label">Yeni Şifre (opsiyonel)</label><input type="text" name="password" class="form-control" placeholder="Boş bırakırsan şifre değişmez"></div>
          <button type="submit" class="btn btn-primary">Kaydet</button>
        </form>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 3: Automated syntax check**

```bash
cd /c/AP/is_takip
python -c "
import jinja2
for f in ['templates/admins.html', 'templates/edit_admin.html']:
    jinja2.Environment().parse(open(f, encoding='utf-8').read())
    print('OK:', f)
"
```

Expected: `OK: templates/admins.html` and `OK: templates/edit_admin.html`.

- [ ] **Step 4: Manual browser check**

1. `cd C:\AP\is_takip && python app.py`, log in as **admin**, open `http://127.0.0.1:5000/admins`.
2. Confirm: layout mirrors the Şube Müdürleri page (add-form card + table card), the current logged-in admin shows a "(siz)" tag: PASS/FAIL.
3. Edit an admin, save, confirm redirect + updated row: PASS/FAIL.
4. Toggle Pasifleştir/Aktifleştir and confirm badge flips: PASS/FAIL.

- [ ] **Step 5: Commit**

```bash
cd /c/AP/is_takip
git add templates/admins.html templates/edit_admin.html
git commit -m "$(cat <<'EOF'
feat: redesign admin list/edit pages with Tabler cards

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RxQXtwis8wHHAeq5r3kHQP
EOF
)"
```

---

## Task 9: Redesign `personnel.html` + `change_password.html`

**Files:**
- Modify: `templates/personnel.html` (full rewrite)
- Modify: `templates/change_password.html` (full rewrite)

**Interfaces:**
- Consumes: `personnel.html` context (from `personnel()`, unchanged): `personnel_list`. Route: `toggle_personnel`. `change_password.html`: no context variables (form posts to the current URL, unchanged).

- [ ] **Step 1: Rewrite `templates/personnel.html`**

```jinja
{% extends "base.html" %}
{% block title %}Personelim{% endblock %}
{% block content %}
<div class="page-header"><h2 class="page-title">Personelim</h2></div>
<p class="text-secondary">Kendi ekibinizdeki personeli buradan ekleyin — sisteme giriş yapamazlar, sadece "Yeni İşlem" oluştururken sorumlu personel olarak seçilebilirler.</p>

<div class="row row-cards">
  <div class="col-12 col-lg-4">
    <div class="card">
      <div class="card-header"><h3 class="card-title">Yeni Personel Ekle</h3></div>
      <div class="card-body">
        <form method="post">
          <div class="mb-3"><label class="form-label">Ad Soyad</label><input type="text" name="full_name" class="form-control" required placeholder="Örn: Ahmet Yılmaz"></div>
          <button type="submit" class="btn btn-primary w-100">Ekle</button>
        </form>
      </div>
    </div>
  </div>

  <div class="col-12 col-lg-8">
    <div class="card">
      <div class="table-responsive">
        <table class="table table-vcenter card-table">
          <thead><tr><th>Ad Soyad</th><th>Durum</th><th></th></tr></thead>
          <tbody>
            {% for p in personnel_list %}
            <tr>
              <td>{{ p.full_name }}</td>
              <td>{% if p.is_active %}<span class="badge bg-green-lt">Aktif</span>{% else %}<span class="badge bg-secondary-lt">Pasif</span>{% endif %}</td>
              <td>
                <form method="post" action="{{ url_for('toggle_personnel', personnel_id=p.id) }}">
                  <button type="submit" class="btn btn-sm btn-outline-secondary">{% if p.is_active %}Pasifleştir{% else %}Aktifleştir{% endif %}</button>
                </form>
              </td>
            </tr>
            {% else %}
            <tr><td colspan="3" class="text-center text-secondary py-4">Henüz personel eklenmedi.</td></tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Rewrite `templates/change_password.html`**

```jinja
{% extends "base.html" %}
{% block title %}Şifremi Değiştir{% endblock %}
{% block content %}
<div class="row justify-content-center">
  <div class="col-12 col-lg-5">
    <div class="card">
      <div class="card-header"><h2 class="card-title">Şifremi Değiştir</h2></div>
      <div class="card-body">
        <form method="post">
          <div class="mb-3"><label class="form-label">Mevcut Şifre</label><input type="password" name="current_password" class="form-control" required autofocus></div>
          <div class="mb-3"><label class="form-label">Yeni Şifre</label><input type="password" name="new_password" class="form-control" required></div>
          <div class="mb-3"><label class="form-label">Yeni Şifre (Tekrar)</label><input type="password" name="confirm_password" class="form-control" required></div>
          <button type="submit" class="btn btn-primary w-100">Şifreyi Güncelle</button>
        </form>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 3: Automated syntax check**

```bash
cd /c/AP/is_takip
python -c "
import jinja2
for f in ['templates/personnel.html', 'templates/change_password.html']:
    jinja2.Environment().parse(open(f, encoding='utf-8').read())
    print('OK:', f)
"
```

Expected: `OK: templates/personnel.html` and `OK: templates/change_password.html`.

- [ ] **Step 4: Manual browser check**

1. `cd C:\AP\is_takip && python app.py`, log in as **manager**, open `http://127.0.0.1:5000/personnel`.
2. Confirm: add-form card + personnel table card render, add a test personnel entry and confirm it appears in the list: PASS/FAIL.
3. Toggle Pasifleştir/Aktifleştir and confirm badge flips: PASS/FAIL.
4. Open the account dropdown → "Şifremi Değiştir", confirm the centered card form renders, submit with a deliberately wrong current password and confirm the red alert (from `base.html`) shows the existing error message: PASS/FAIL.

- [ ] **Step 5: Commit**

```bash
cd /c/AP/is_takip
git add templates/personnel.html templates/change_password.html
git commit -m "$(cat <<'EOF'
feat: redesign personnel list and change-password pages with Tabler

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RxQXtwis8wHHAeq5r3kHQP
EOF
)"
```

---

## Task 10: Full regression walkthrough

**Files:** none (verification-only task; may produce small follow-up fixes to any file touched in Tasks 2-9 if the walkthrough finds a regression).

**Interfaces:**
- Consumes: every template and vendor asset from Tasks 1-9.

- [ ] **Step 1: Automated syntax check across all templates**

```bash
cd /c/AP/is_takip
python -c "
import jinja2, glob
env = jinja2.Environment()
for f in sorted(glob.glob('templates/*.html')):
    env.parse(open(f, encoding='utf-8').read())
    print('OK:', f)
"
```

Expected: `OK:` printed for all 14 files (13 pages + `_macros.html`) with no traceback.

- [ ] **Step 2: Full manual walkthrough as admin**

`cd C:\AP\is_takip && python app.py`, log in as **admin**, and walk every nav link: Panel, Şube Müdürleri, Yöneticiler, Raporlar, İstatistikler, "+ Yeni İşlem", a task detail page, "Şifremi Değiştir", "Yardım" (PDF opens), "Çıkış". Confirm no page throws a 500 error (check the terminal running `python app.py` for tracebacks) and every page visually matches its task's checklist above: PASS/FAIL per page.

- [ ] **Step 3: Full manual walkthrough as manager**

Log in as **manager**, walk: Panel, Personelim, "+ Yeni İşlem" (with personnel checkboxes), a task detail page (status update + personnel checkboxes + note + attachment), "Şifremi Değiştir", "Çıkış". Confirm no 500 errors and pages match their task's checklist: PASS/FAIL per page.

- [ ] **Step 4: Mobile-width pass**

At ~400px width, revisit Panel, a task detail page, and Raporlar as admin. Confirm the navbar collapses behind the hamburger, cards/tables/charts stack to one column without horizontal overflow, and the reports page still has a working "Yazdır" flow: PASS/FAIL.

- [ ] **Step 5: Fix any regressions found**

If any PASS/FAIL above is FAIL, fix it in the relevant already-committed template file, re-run that file's Jinja syntax check, re-verify in the browser, then commit as a `fix:` commit referencing the task it belongs to. Repeat until all checks in Steps 2-4 pass.

- [ ] **Step 6: Final commit (only if Step 5 produced changes)**

```bash
cd /c/AP/is_takip
git add -A
git status
```

If there are staged changes from Step 5 fixes not yet committed, commit them:

```bash
git commit -m "$(cat <<'EOF'
fix: address regressions found in full Tabler redesign walkthrough

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01RxQXtwis8wHHAeq5r3kHQP
EOF
)"
```

If `git status` shows a clean tree, no commit is needed — the redesign is complete.
