<image src="https://spoo.me/static/images/banner-rounded.png">

<h3 align="center">spoo.me</h3>
<p align="center">Shorten Your Url not Your Possibilities 🚀</p>

<p align="center">
    <a href="#-features"><kbd>🔥 Features</kbd></a>
    <a href="#-endpoints"><kbd>📌 Endpoints</kbd></a>
    <a href="https://spoo.me/api" target="_blank"><kbd>🛠️ API Docs</kbd></a>
    <a href="#-getting-started"><kbd>🚀 Getting Started</kbd></a>
    <a href="#-contributing"><kbd>🤝 Contributing</kbd></a>
</p>

<p align="center">
<a href="https://status.spoo.me"><img src="https://uptime.betterstack.com/status-badges/v1/monitor/qlmf.svg"></a>
<img src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fspoo.me%2Fmetric&query=%24.total-shortlinks&label=Links%20Shortened&color=6a5cf4&cacheSeconds=60" alt="Total URLs Shortened">
<img src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fspoo.me%2Fmetric&query=%24.total-clicks&label=Clicks%20Redirected&color=6a5cf4&cacheSeconds=60" alt="Total Clicks Redirected">
<a href="https://spoo.me/discord"><img src="https://img.shields.io/discord/1192388005206433892?logo=discord" alt="Discord"></a>
<a href="https://twitter.com/spoo_me"><img src="https://img.shields.io/twitter/follow/spoo_me?logo=x&label=%40spoo_me&color=0bf" alt="X (formerly Twitter) Follow"></a>
<a href="https://codecov.io/gh/spoo-me/spoo"><img src="https://codecov.io/gh/spoo-me/spoo/graph/badge.svg?token=4ZHHWVVCLH" alt="codecov"></a>
</p>

# ⚡ Introduction

**spoo.me** is a free, open-source service for shortening URLs. It offers comprehensive URL statistics, a free API, and extensive customization options. You can create and manage your URLs, generate API keys, create custom `slugs`, add `password protection`, and manage `link lifespans`.

# 🔥 Features

- `Custom Slugs` - Create custom slugs for your URLs 🎯
- `Emoji Slugs` - Use emojis as slugs for your URLs 😃
- `Password Protection` - Protect your URLs with a password 🔒
- `Link Max Clicks` - Set a maximum number of clicks for your URLs 📈
- `URL Statistics` - View detailed statistics for your URLs with advanced analytics 📊
- `BOT Tracking` - Track bot clicks on your URLs 🤖
- `API` - A free and open-sourced API for URL shortening and statistics 🛠️
- `Export Click Data` - Export click data as a CSV, JSON, XLSX, or XML file 📤
- `Dashboard` - Manage all your URLs and view analytics in one place 📱
- `API Keys` - Generate API keys for programmatic access with rate limiting 🔑
- `Open Source` - spoo.me is open-sourced and free to use 📖
- `Absolutely Free` - No hidden costs, no premium plans, no limitations 💸
- `No Registration Required` - Create short URLs without an account 📝
- `Self Hosting` - You can host spoo.me on your own server 🏠

# 📌 Endpoints

The basic structure for accessing a shortened URL is: `https://spoo.me/<short_code>`

**Example** - **<https://spoo.me/ga>**

## 🔐 Accessing Password-Protected URLs

For password-protected URLs, **use the same basic structure**. This redirects to a **password entry page**.

**Example** - **<https://spoo.me/exa>** <br/>
**Password** - <kbd>Example@12</kbd>

> [!TIP]
> Bypass the password entry page by appending the password to the URL parameters - `https://spoo.me/<short_code>?password=<password>`

## 📈 Checking URL Statistics

To view the statistics for a URL, use the following structure: `https://spoo.me/stats/<short_code>`

**Example** - **<https://spoo.me/stats/ga>**

> [!NOTE]
> You won't be able to view statistics for a password-protected page unless you provide its password.

# 📊 Analytics Dashboard

Get deep insights into your shortened URLs with our comprehensive analytics platform:

- `Geographic Intelligence` - Interactive world map showing click distribution by country and city 🌍
- `Device Analytics` - Detailed breakdowns of devices, browsers, operating systems, and screen sizes 📱
- `Traffic Patterns` - Time-series charts showing clicks over time with granular date ranges ⏱️
- `Referrer Tracking` - Understand where your traffic comes from with full referrer analysis 🔗
- `Bot Detection` - Separate human traffic from bot clicks for accurate metrics 🤖
- `N-Dimensional Filtering` - Apply multi-layer filters across **browsers**, **platforms**, **referrers**, **short URLs**, and more for granular analysis 🔍
- `Custom Time Ranges` - Filter analytics by specific date ranges, from hours to months, for precise temporal insights 📅
- `Export Capabilities` - Download your data in CSV, JSON, XLSX, or XML formats 📤

Access statistics for any public URL at `https://spoo.me/stats/<short_code>` or manage all your links through the dashboard.

# 🛠️ API Docs

Spoo.me offers a free, open-source API for URL shortening and statistics. Check it out below:

|[spoo.me API](https://spoo.me/api)|
|---|

# 🚀 Getting Started

To self-host spoo.me on your server, follow the this **detailed** guide:

|[Self-Hosting Guide 🏠](https://spoo.me/docs/self-hosting)|
|---|

<details>

<summary>Expand this for a Quick Start</summary>

## Method 1 - Docker (Recommended)

### 📋 Prerequisites

- [Docker](https://docs.docker.com/get-docker/) 🐳

### 📂 Clone the repository (Docker Method)

```bash
git clone https://github.com/spoo-me/url-shortener.git
```

### Rename .env.example to .env

```bash
mv .env.example .env
```

### ➕ Adding environment variables to .env file

```bash
MONGODB_URI=<your_MONGODB_URI>
REDIS_URI=<your_REDIS_URI>

# OAuth Configuration (Optional - for social login features)
GOOGLE_CLIENT_ID=<your_google_client_id>
GOOGLE_CLIENT_SECRET=<your_google_client_secret>

# JWT Secret Keys (Required for authentication)
JWT_ISSUER=
JWT_AUDIENCE=
ACCESS_TOKEN_TTL_SECONDS=3600
REFRESH_TOKEN_TTL_SECONDS=2592000
COOKIE_SECURE="false"    # false: for local dev, true: for production
JWT_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n.....\n-----END PRIVATE KEY-----"
JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\n.....\n-----END PUBLIC KEY-----"
JWT_SECRET=""
```

> [!NOTE]
>
> - The above is a minimal set of environment variables required to run spoo.me using Docker. Please refer to our official [self-hosting guide](https://spoo.me/docs/self-hosting) for a complete list of environment variables and their descriptions.
> - OAuth credentials are optional. Users can still register with email/password if OAuth is not configured.
> - JWT secret keys should be long, random strings. You can generate them using `openssl rand -hex 32`.
> - With this method, you can either use a cloud service like [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) to store the data remotely or you can use a local MongoDB instance.
> - If you want to use a local MongoDB instance, your MongoDB URI would be `mongodb://localhost:27017/`.

### 🚀 Starting the server

```bash
docker-compose up -d
```

## Method 2 - Manual

### 📋 Prerequisites

- [MongoDB](https://www.mongodb.com/try/download/community) 🌿
  - MongoDB is only required if you want to store the **data locally**. You can also use a cloud service like [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) to store the data remotely.
- [Python](https://www.python.org/downloads/) 🐍
- [uv](https://docs.astral.sh/uv/getting-started/installation/) 🛠️

### 📂 Clone the repository

```bash
git clone https://github.com/spoo-me/url-shortener.git
```

### Installing `uv` for tooling

```bash
pip install uv
```

### 📦 Install dependencies & setting virtual env

```bash
uv venv
uv sync
```

### Rename `.env.example` to `.env`

```bash
mv .env.example .env
```

### ➕ Adding environment variables to .env file

Same as in the Docker method above.

> [!NOTE]
>
> - OAuth credentials are optional. Users can still register with email/password if OAuth is not configured.
> - JWT secret keys should be long, random strings. You can generate them using `openssl rand -hex 32`.
> - If you installed MongoDB locally, your MongoDB URI would be `mongodb://localhost:27017/` or if you are using MongoDB Atlas, you can find your MongoDB URI in the **Connect** tab of your cluster.

### 🚀 Starting the server

```bash
uv run main.py
```

### 🌐 Access the server

Open your browser and go to `http://localhost:8000` to access the **spoo.me** URL shortener.

</details>

# 🤝 Contributing

**Contributions are always welcome!** 🎉 Here's how you can contribute:

- Bugs are logged using the github issue system. To report a bug, simply [open a new issue](https://github.com/spoo-me/url-shortener/issues/new).
- Follow the [contribution guidelines](contributing.md) to get started.
- Make a [pull request](https://github.com/spoo-me/url-shortener/pull) for any feature or bug fix.

> [!IMPORTANT]
> For any type of support or queries, feel free to reach out to us at <kbd>[✉️ support@spoo.me](mailto:support@spoo.me)</kbd>

---

<h6 align="center">
<img src="https://spoo.me/static/images/favicon.png" height=30 title="Spoo.me Copyright">
<br>
© spoo.me . 2026

All Rights Reserved</h6>

<p align="center">
 <a href="https://github.com/spoo-me/url-shortener/blob/master/LICENSE.txt"><img src="https://img.shields.io/static/v1.svg?style=for-the-badge&label=License&message=APACHE-2.0&logoColor=d9e0ee&colorA=363a4f&colorB=b7bdf8"/></a>
</p>
