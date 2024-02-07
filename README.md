<image src="https://spoo.me/static/images/banner-rounded.png">

# **Welcome to spoo.me - Shorten Your Url not Your Possibilities** 🚀

Dive into the magic of **spoo.me**, your shortcut to URL wizardry! 🚀 Transform lengthy links into sleek, memorable ones with our free, open-sourced service. 🌟

What sets us apart? High-level URL stats for insight, free API for developers, and killer customization options! 🎨✨ Craft personalized `slugs`, add `password protection`, or control `link lifespans`. ⏳

Simplify your links, amplify your reach – join **spoo.me** and make URLs an art form! 🎨🔗

---

<details>
<summary>📖 Table of Contents</summary>

- [**Welcome to spoo.me - Shorten Your Url not Your Possibilities** 🚀](#welcome-to-spoome---shorten-your-url-not-your-possibilities-)
- [📌 Endpoints](#-endpoints)
    - [🔐 Password Protected URLs](#-password-protected-urls)
    - [📈 Viewing URL Statistics](#-viewing-url-statistics)
- [📊 URL statistics Features](#-url-statistics-features)
- [🛠️ URL Shortener API](#️-url-shortener-api)
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
- [🤝 Contributing](#-contributing)
- [📧 Feedback / Issues / Support](#-feedback--issues--support)
- [👀 Visual Previews](#-visual-previews)

</details>

---

# 📌 Endpoints

**_Basic Structure_**: `https://spoo.me/<short_code>`

**Example**:
- Short URL: `https://spoo.me/ga`
  - Redirects to: `https://google.com`
  - Short code: `ga`

### 🔐 Password Protected URLs

**_Basic Structure_**: `https://spoo.me/<short_code>` (_redirects to password entry page_)

- **Productivity Trick**: Enter the password like this: `https://spoo.me/<short_code>?password=<password>`


### 📈 Viewing URL Statistics

**_Basic Structure_**: `https://spoo.me/stats/<short_code>`

**Example**:
- URL: `https://spoo.me/stats/ga`

_**Note**: You cannot view statistics for a password-protected page without providing its password._

# 📊 URL statistics Features

- `Detailed information` about the URL, including Date of Creation, Original URL, Total Clicks, etc.
- `Graphs` displaying URL `click history` over time, `Browser Data`, `Platforms`, `Referrers`, `Countries` (Tracks Unique Clicks too)
- In-depth `click analysis`
- `QR Code` for the URL

# 🛠️ URL Shortener API

spoo.me has a `free` and `open-sourced` API that allows you to shorten URLs, view URL statistics, and more for your applications, websites, and services.

For detailed API documentation, please visit [https://spoo.me/api](https://spoo.me/api)


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
```

**Note**: With this method, you can either use a cloud service like [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) to store the data remotely or you can use a local MongoDB instance. If you want to use a local MongoDB instance, your MongoDB URI would be `mongodb://localhost:27017/`.

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
```

**Note**: If you installed MongoDB locally, your MongoDB URI would be `mongodb://localhost:27017/` or if you are using MongoDB Atlas, you can find your MongoDB URI in the **Connect** tab of your cluster.


### 🚀 Starting the server

```bash
python main.py
```

# 🤝 Contributing

We welcome contributions to **spoo.me**. Feel free to fork the repository and submit a pull request. For major changes, please open an issue first to discuss what you would like to change.

# 📧 Feedback / Issues / Support

**To give feedback, ask a question or make a feature request, you can either use the [Github Discussions](https://github.com/Zingzy/spoo.me/discussions)**

**Bugs are logged using the github issue system. To report a bug, simply [open a new issue](https://github.com/Zingzy/spoo.me/issues/new).**

**For URL deletion requests / any other issues feel free to [grill us](mailto:support@spoo.me)**

# 👀 Visual Previews

**Main Page**

![spoo me main page](https://raw.githubusercontent.com/spoo-me/url-shortener/main/static/previews/main.png)

**Result Page**

![spoo me result page](https://raw.githubusercontent.com/spoo-me/url-shortener/main/static/previews/result.png)

**Stats Page**

![image](https://raw.githubusercontent.com/spoo-me/url-shortener/main/static/previews/stats.png)

**API Page**

![image](https://raw.githubusercontent.com/spoo-me/url-shortener/main/static/previews/api.png)

---

<h6 align="center">
<img src="https://spoo.me/static/images/favicon.png" height=30 title="Spoo.me Copyright">
<br>
© spoo.me . 2024

All Rights Reserved</h6>

<p align="center">
	<a href="https://github.com/spoo-me/url-shortener/blob/master/LICENSE.txt"><img src="https://img.shields.io/static/v1.svg?style=for-the-badge&label=License&message=APACHE-2.0&logoColor=d9e0ee&colorA=363a4f&colorB=b7bdf8"/></a>
</p>