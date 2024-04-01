<image src="https://spoo.me/static/images/banner-rounded.png">

# **Welcome to spoo.me - Shorten Your Url not Your Possibilities** 🚀

**spoo.me** is a free, open-source service for shortening URLs. It offers URL statistics, a free API, and customization options. You can create custom `slugs`, add `password protection`, and manage `link lifespans`. Join **spoo.me** to simplify your URLs.

---

<details>
<summary>📖 Table of Contents</summary>

- [**Welcome to spoo.me - Shorten Your Url not Your Possibilities** 🚀](#welcome-to-spoome---shorten-your-url-not-your-possibilities-)
- [✨ Features](#-features)
- [📌 Endpoints](#-endpoints)
  - [🔐 Accessing Password-Protected URLs](#-accessing-password-protected-urls)
  - [📈 Checking URL Statistics](#-checking-url-statistics)
- [🛠️ API Docs](#️-api-docs)
- [🚀 Getting Started](#-getting-started)
  - [Method 1 - Docker (Recommended)](#method-1---docker-recommended)
    - [📋 Prerequisites](#-prerequisites)
    - [📂 Clone the repository](#-clone-the-repository)
    - [Rename .env.example to .env](#rename-envexample-to-env)
    - [➕ Adding environment variables to .env file](#-adding-environment-variables-to-env-file)
    - [🚀 Starting the server](#-starting-the-server)
  - [Method 2 - Manual](#method-2---manual)
    - [📋 Prerequisites](#-prerequisites-1)
    - [📂 Clone the repository](#-clone-the-repository-1)
    - [Creating a virtual environment (Optional)](#creating-a-virtual-environment-optional)
    - [Activate the virtual environment (Optional)](#activate-the-virtual-environment-optional)
    - [📦 Install dependencies](#-install-dependencies)
    - [Rename .env.example to .env](#rename-envexample-to-env-1)
    - [➕ Adding environment variables to .env file](#-adding-environment-variables-to-env-file-1)
    - [🚀 Starting the server](#-starting-the-server-1)
    - [🌐 Access the server](#-access-the-server)
- [🤝 Contributing](#-contributing)
- [📧 Feedback / Issues / Support](#-feedback--issues--support)
- [👀 Visual Previews](#-visual-previews)

</details>

---

# ✨ Features

- `Custom Slugs`: Create custom slugs for your URLs 🎯
- `Emoji Slugs`: Use emojis as slugs for your URLs 😃
- `Password Protection`: Protect your URLs with a password 🔒
- `Link Max Clicks`: Set a maximum number of clicks for your URLs 📈
- `URL Statistics`: View detailed statistics for your URLs 📊
- `API`: A free and open-sourced API for URL shortening and statistics 🛠️
- `QR Code`: Generate a QR code for your URLs 📱
- `Export Click Data`: Export click data as a CSV, JSON, XLSX, or XML file 📤
- `Open Source`: spoo.me is open-sourced and free to use 📖
- `No Ads`: No ads, no tracking, no nonsense 🚫
- `Absolutely Free`: No hidden costs, no premium plans, no limitations 💸
- `No Registration`: No need to register an account to use spoo.me 📝
- `Self Hosting`: You can host spoo.me on your own server 🏠


# 📌 Endpoints

The basic structure for accessing a shortened URL is: `https://spoo.me/<short_code>`

**Example**: **https://spoo.me/ga**

- This redirects to: `https://google.com`
- The short code used is: `ga`

## 🔐 Accessing Password-Protected URLs

To access a password-protected URL, use the same basic structure: `https://spoo.me/<short_code>`. This will redirect you to a password entry page.

> You can bypass the password entry page by appending the password to the URL like this: `https://spoo.me/<short_code>?password=<password>`

## 📈 Checking URL Statistics

To view the statistics for a URL, use the following structure: `https://spoo.me/stats/<short_code>`

**Example**: **https://spoo.me/stats/ga**

> _**Note:** You won't be able to view statistics for a password-protected page unless you provide its password._


# 🛠️ API Docs

Spoo.me offers a free, open-source API for URL shortening and statistics.
**For detailed API documentation, please visit [https://spoo.me/api](https://spoo.me/api)**


# 🚀 Getting Started

## Method 1 - Docker (Recommended)

### 📋 Prerequisites

- [Docker](https://docs.docker.com/get-docker/) 🐳

### 📂 Clone the repository

```bash
git clone https://github.com/zingzy/spoo.me.git
```

### Rename .env.example to .env

```bash
mv .env.example .env
```

### ➕ Adding environment variables to .env file

```bash
MONGO_URI=<your_mongo_uri>
CONTACT_WEBHOOK=<valid_webhook_URI>
URL_REPORT_WEBHOOK=<valid_webhook_URI>
```

> **Note**: With this method, you can either use a cloud service like [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) to store the data remotely or you can use a local MongoDB instance. If you want to use a local MongoDB instance, your MongoDB URI would be `mongodb://localhost:27017/`.

### 🚀 Starting the server

```bash
docker-compose up
```

## Method 2 - Manual

### 📋 Prerequisites

- [MongoDB](https://www.mongodb.com/try/download/community) 🌿
  - MongoDB is only required if you want to store the **data locally**. You can also use a cloud service like [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) to store the data remotely.
- [Python](https://www.python.org/downloads/) 🐍
- [PIP](https://pip.pypa.io/en/stable/installing/) 📦
- [Virtualenv](https://pypi.org/project/virtualenv/) (Optional) 🌐

### 📂 Clone the repository

```bash
git clone https://github.com/zingzy/spoo.me.git
```

### Creating a virtual environment (Optional)

```bash
python3 -m venv venv
```

### Activate the virtual environment (Optional)

```bash
source venv/bin/activate
```

### 📦 Install dependencies

```bash
pip install -r requirements.txt
```

### Rename .env.example to .env

```bash
mv .env.example .env
```

### ➕ Adding environment variables to .env file

```bash
MONGO_URI=<your_mongo_uri>
CONTACT_WEBHOOK=<valid_webhook_URI>
URL_REPORT_WEBHOOK=<valid_webhook_URI>
```

> **Note**: If you installed MongoDB locally, your MongoDB URI would be `mongodb://localhost:27017/` or if you are using MongoDB Atlas, you can find your MongoDB URI in the **Connect** tab of your cluster.


### 🚀 Starting the server

```bash
python main.py
```

### 🌐 Access the server

Open your browser and go to `http://localhost:8000` to access the **spoo.me** URL shortener.

# 🤝 Contributing

**Contributions are always welcome!** 🎉
Please check out the [contributing guidelines](contributing.md) to get started.


# 📧 Feedback / Issues / Support

**To give feedback, ask a question or make a feature request, you can either use the [Github Discussions](https://github.com/spoo-me/url-shortener/discussions)**

**Bugs are logged using the github issue system. To report a bug, simply [open a new issue](https://github.com/spoo-me/url-shortener/issues/new).**

**For URL deletion requests / any other issues feel free to [grill us](mailto:support@spoo.me)**


# 👀 Visual Previews

**Main Page**

[![spoo me main page](https://raw.githubusercontent.com/spoo-me/url-shortener/main/static/previews/main.png)](https://spoo.me)

**Result Page**

[![spoo me result page](https://raw.githubusercontent.com/spoo-me/url-shortener/main/static/previews/result.png)](https://spoo.me/result/ga)

**Stats Page**

[![image](https://raw.githubusercontent.com/spoo-me/url-shortener/main/static/previews/stats.png)](https://spoo.me/stats/ga)

**API Page**

[![image](https://raw.githubusercontent.com/spoo-me/url-shortener/main/static/previews/api.png)](https://spoo.me/api)

<br><br>

![Contribution Charts](https://repobeats.axiom.co/api/embed/48a40934896cbcaff2812e80478ebb701ee49dd4.svg)

<br><br>


<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=spoo-me/url-shortener&type=Date&theme=dark" />
  <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=spoo-me/url-shortener&type=Date" />
</picture>

---

<h6 align="center">
<img src="https://spoo.me/static/images/favicon.png" height=30 title="Spoo.me Copyright">
<br>
© spoo.me . 2024

All Rights Reserved</h6>

<p align="center">
	<a href="https://github.com/spoo-me/url-shortener/blob/master/LICENSE.txt"><img src="https://img.shields.io/static/v1.svg?style=for-the-badge&label=License&message=APACHE-2.0&logoColor=d9e0ee&colorA=363a4f&colorB=b7bdf8"/></a>
</p>