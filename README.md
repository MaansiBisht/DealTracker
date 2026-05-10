<div align="center">

```
██████╗ ███████╗ █████╗ ██╗     ████████╗██████╗  █████╗  ██████╗██╗  ██╗███████╗██████╗
██╔══██╗██╔════╝██╔══██╗██║     ╚══██╔══╝██╔══██╗██╔══██╗██╔════╝██║ ██╔╝██╔════╝██╔══██╗
██║  ██║█████╗  ███████║██║        ██║   ██████╔╝███████║██║     █████╔╝ █████╗  ██████╔╝
██║  ██║██╔══╝  ██╔══██║██║        ██║   ██╔══██╗██╔══██║██║     ██╔═██╗ ██╔══╝  ██╔══██╗
██████╔╝███████╗██║  ██║███████╗   ██║   ██║  ██║██║  ██║╚██████╗██║  ██╗███████╗██║  ██║
╚═════╝ ╚══════╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
```

### **An ops console for the deals you're too lazy to refresh**

📦 **products** · 🏨 **hotels** · 💌 **email alerts** · 🤖 **headless Chromium** · 📡 **live ticks via SSE**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![Tailwind](https://img.shields.io/badge/Tailwind-v4-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white)](#-quickstart)
[![Selenium](https://img.shields.io/badge/Selenium-4.43-43B02A?style=flat-square&logo=selenium&logoColor=white)](https://www.selenium.dev)
[![Tests](https://img.shields.io/badge/tests-57%20passing-brightgreen?style=flat-square)](#-tests)

<br/>

<img src="screencast/dealtracker-console.gif" alt="DealTracker ops console — submit a watch, watch the live tick log" width="900">

<sub>↑ submit a URL · scraper fires within 2 seconds · alert lines flash amber when a threshold hits</sub>

</div>

---

## ✨ What it does

You drop in a URL and an email. DealTracker keeps refreshing the page on
your behalf — every 30 seconds for products, every 3 hours for hotels —
and hits your inbox the moment something good happens.

<table>
<tr>
<td width="33%" valign="top">

### 📦 Stock alerts

Notifies you the **second** an out-of-stock product comes back. No more
hitting refresh on Amul Lassi at 9 AM.

</td>
<td width="33%" valign="top">

### 💸 Price drops

Set a target. We mail you when the price falls below it — across
Amazon, Flipkart, Myntra, Amul, Amazfit.

</td>
<td width="33%" valign="top">

### 🏨 Hotel deals

Scans the **next 30 days** every cycle. Find the cheapest night for
your trip without manually checking each date.

</td>
</tr>
<tr>
<td valign="top">

### 📡 Live tick stream

A terminal-style pane in the UI streams every scrape attempt, every
result, every alert. Server-Sent Events under the hood.

</td>
<td valign="top">

### 🐳 Single-image deploy

`docker compose up -d` and you're done. Nginx in front for TLS, that's
the whole infra story.

</td>
<td valign="top">

### 🛡️ Yours, not ours

Self-hosted. Your URLs and email never leave your VPS. SQLite file
on disk you can `cp` and back up.

</td>
</tr>
</table>

---

## 🌐 Supported platforms

<table>
<tr><th align="left">Products</th><th align="left">Hotels</th></tr>
<tr><td>

🛒 Amazon  ·  🛍️ Flipkart  ·  👕 Myntra  ·  🥛 Amul  ·  ⌚ Amazfit

</td><td>

🛏️ Booking.com  ·  ✈️ MakeMyTrip  ·  🏖️ Goibibo  ·  🌏 Agoda

</td></tr>
</table>

The UI hits `GET /api/platforms` on every page load — that endpoint reads
straight from the `SCRAPERS` dict so the strip is always honest.

---

## 🏗️ How it works

```mermaid
flowchart LR
    You["👤 You"] -->|"paste URL + email"| UI["🖥️ Ops Console<br/>(React)"]
    UI -->|REST| API["⚡ FastAPI"]
    API <-->|SSE stream| UI
    API --> Sched["⏱️ APScheduler<br/>(every 30s / 3h)"]
    Sched --> Runner["🤖 Selenium<br/>+ Chromium"]
    Runner -->|"price · stock"| API
    API -->|"threshold hit"| SMTP["💌 Gmail SMTP"]
    SMTP --> You
    API <--> DB[("🗃️ SQLite<br/>jobs + events")]
```

One Docker image. One process. One SQLite file. No Redis, no Celery, no
message broker. The persistence is a 36 KB file you can scp.

---

## 🎬 Screenshots

> Drop your captures into `docs/screenshots/` to fill these in.

<table>
<tr>
<td align="center" width="50%">
   <img src="docs/screenshots/console-products.png" alt="Products view" width="100%"/><br/>
   <sub><b>Products tab</b> — submit form, live job rows</sub>
</td>
<td align="center" width="50%">
   <img src="docs/screenshots/console-hotels.png" alt="Hotels view" width="100%"/><br/>
   <sub><b>Hotels tab</b> — same shell, 30-day scan vibe</sub>
</td>
</tr>
<tr>
<td align="center" width="50%">
   <img src="docs/screenshots/terminal-stream.png" alt="Live tick log" width="100%"/><br/>
   <sub><b>Live tick log</b> — alert lines flash amber</sub>
</td>
<td align="center" width="50%">
   <img src="docs/screenshots/email-alert.png" alt="Email alert" width="100%"/><br/>
   <sub><b>The payoff</b> — Gmail shows up at threshold</sub>
</td>
</tr>
</table>

---

## 🚀 Quickstart

### 🐳 Docker — recommended

The whole stack is one image: Node builds the UI, Python serves the
API, headless Chromium does the scraping.

```bash
git clone https://github.com/MaansiBisht/DealTracker.git
cd DealTracker
cp .env.example .env       # fill in real values, see Configuration ↓
docker compose up -d --build
docker compose logs -f app
```

Open `http://<host>:8000`. Behind nginx/Caddy, reverse-proxy `/` and
`/api/*` to port 8000 and you've got TLS + a domain.

Update later:
```bash
git pull && docker compose up -d --build
```

### ⚡ Local dev

Two processes — `uvicorn` (API on :8000) and `vite` (HMR UI on :5173).

```bash
# 1. Python backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn src.server.main:app --reload --port 8000

# 2. React frontend (separate terminal)
cd ui && npm ci && npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` and `/events` to uvicorn.

### 🖥️ CLI

Interactive prompt-driven flow — same scrapers as the web app, no
server, no scheduler. Good for one-off checks from a laptop.

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py        # interactive prompts
```

<details>
<summary>CLI demo</summary>

<img src="screencast/productAlerts.gif" alt="CLI demo" width="640">

</details>

---

## 🎛️ Configuration

Every knob is an env var. Real defaults live in `.env.example`.

| Variable                   | Required | What it does                                              |
| -------------------------- | :------: | --------------------------------------------------------- |
| `EMAIL_ADDRESS`            |    ✅    | Gmail account that sends the alerts                       |
| `EMAIL_PASSWORD`           |    ✅    | **Gmail App Password** ([generate here][app-pw])           |
| `PINCODE`                  |    ✅    | Used by Amul scraper before reading stock/price           |
| `WEB_USER` · `WEB_PASS`    |   prod   | HTTP Basic auth for the ops console                       |
| `FALLBACK_EMAIL`           |    ⏤    | Retried when delivery to the watch's email fails          |
| `TICK_INTERVAL_PRODUCT_SEC`|    ⏤    | Default `30` (dev). Use `3600` in prod.                   |
| `TICK_INTERVAL_HOTEL_SEC`  |    ⏤    | Default `60` (dev). Use `10800` in prod.                  |
| `DATABASE_URL`             |    ⏤    | Default `sqlite:////app/data/dealtracker.db`              |
| `LOG_LEVEL`                |    ⏤    | `DEBUG` / `INFO` / `WARNING` for the operator log         |
| `CHROME_BIN`               |    ⏤    | Chromium path. The Docker image sets this for you.        |
| `CHROMEDRIVER_PATH`        |    ⏤    | chromedriver path. Same — Docker handles it.              |

[app-pw]: https://myaccount.google.com/apppasswords

> 🔐 **Why an App Password?** Google blocks plain SMTP login from your
> account password since 2022. Two-factor authentication + an App
> Password is the official path. It's also revocable from one screen.

---

## 🧱 Project structure

```
DealTracker/
├── 🐍 main.py                  # CLI entry
├── src/
│   ├── cli.py                 # CLI prompts
│   ├── config.py              # env loader
│   ├── 🕸️  scrapers/           # one file per site + 30-day hotel scanner
│   ├── 🛠️  utils/              # Selenium driver, Gmail SMTP
│   └── 🚀 server/              # FastAPI ops console
│       ├── main.py            # uvicorn entrypoint, lifespan
│       ├── routes.py          # /api/jobs · /api/events/* · /api/platforms
│       ├── runner.py          # one-shot scrape, called per tick
│       ├── scheduler.py       # APScheduler — single-thread, Selenium-safe
│       ├── events.py          # in-process pub/sub for SSE
│       ├── auth.py            # HTTP Basic dependency
│       └── db.py · models.py · schemas.py
├── 🎨 ui/                      # React 19 + Vite + Tailwind v4 + Framer Motion
├── 🧪 tests/                   # pytest — pure unit + TestClient (57 tests, <1s)
├── 💾 data/                    # SQLite, mounted as Docker volume
├── 🐳 Dockerfile               # multi-stage: node builds UI, python serves
├── docker-compose.yml
└── .env.example
```

---

## 🛠️ Add a new scraper

It's three steps. The codebase already has 9 examples to copy from.

<details>
<summary><b>📦 Product scraper</b></summary>

1. Create `src/scrapers/newsite.py`:
   ```python
   def scrape_newsite(driver, url):
       driver.get(url)
       # ...your parsing logic...
       return {
           "title": "Optional product name",
           "price": "1234.56",
           "stock_status": "in stock",   # or "out of stock"
       }
   ```

2. Wire it in `src/scrapers/__init__.py`:
   ```python
   from .newsite import scrape_newsite
   SCRAPERS = {..., "newsite": scrape_newsite}
   PLATFORM_PATTERNS = {..., "newsite.com": "newsite"}
   ```

3. Lock the routing in `tests/test_routing.py` so a typo doesn't unship it later.

</details>

<details>
<summary><b>🏨 Hotel scraper</b></summary>

Same shape, plus append `"newhotel"` to `HOTEL_PLATFORMS`. The runner
will pick `scan_hotel_prices_monthly` instead of single-shot scraping.
Returned dict adds `"type": "hotel"` and may include `"rating"`.

</details>

---

## 🧪 Tests

Fast feedback loop — no Selenium, no real network, all under a second:

```bash
pytest -q
```

```
.........................................................                [100%]
57 passed in 0.40s
```

The suite covers:

- 🎯 URL → platform routing (parametrized over every supported site)
- 🔢 price parsing (`₹156.00`, `Rs. 1,299`, bare numbers, junk)
- 📜 Pydantic validation (URL shape, email, alert type, threshold rules)
- 🔌 FastAPI happy paths via `TestClient` (CRUD + recent events JOIN)
- 📡 the SSE event bus (publish, subscribe, drop-oldest backpressure)

Browser-driven scrapes are excluded on purpose — they need a live page.
For end-to-end against a real site, run the `docker compose` stack and
submit a job through the UI.

---

## 🧰 Tech stack

<div>

| Layer       | Choices                                                         |
| ----------- | --------------------------------------------------------------- |
| 🐍 Backend  | Python 3.11 · FastAPI · SQLAlchemy 2.x · Pydantic v2 · APScheduler |
| 🤖 Scrape   | Selenium 4 · BeautifulSoup4 · headless Chromium                 |
| 🎨 Frontend | React 19 · Vite · Tailwind v4 (`@theme`) · Framer Motion        |
| 🔤 Type     | JetBrains Mono Variable · Geist Variable (self-hosted)          |
| 💾 Data     | SQLite (one file)                                               |
| 📡 Realtime | Server-Sent Events (`text/event-stream`)                        |
| 📦 Deploy   | Docker · docker-compose · Nginx/Caddy reverse proxy             |

</div>

---

## 🤝 Contributing

PRs welcome. The fast loop:

```bash
pytest -q && cd ui && npm run build
```

If you change the JSON contract, update both `src/server/schemas.py`
and `ui/src/types/job.ts` so TypeScript catches drift.

---

## 📜 License

Personal / educational use. Respect each site's terms of service —
hammer responsibly.

<div align="center">

<sub>built with ❤️ + a lot of refresh-key fatigue</sub>

</div>
