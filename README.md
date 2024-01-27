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
  - [Method 1 - Direct Deployment](#method-1---direct-deployment)
  - [Method 2 - Docker (Recommended)](#method-2---docker-recommended)
    - [📋 Prerequisites](#-prerequisites)
    - [📂 Clone the repository](#-clone-the-repository)
    - [Rename .env.example to .env](#rename-envexample-to-env)
    - [➕ Adding environment variables to .env file](#-adding-environment-variables-to-env-file)
    - [🚀 Starting the server](#-starting-the-server)
  - [Method 3 - Manual](#method-3---manual)
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

## Method 1 - Direct Deployment

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fspoo-me%2Furl-shortener&env=MONGODB_URI&envDescription=This%20is%20the%20URI%20of%20your%20MongoDB%20cluster%20which%20would%20be%20used%20to%20store%20the%20data%20of%20this%20URL%20Shortener%20API) &nbsp;
<a href="https://render.com/deploy?repo=https://github.com/spoo-me/url-shortener"></a><img src="https://render.com/images/deploy-to-render-button.svg" alt="Deploy to Render" height="30px"/></a> &nbsp;
<a href="https://render.com/deploy?repo=https://github.com/spoo-me/url-shortener"><img src="https://img.shields.io/website?color=cyan&down_message=Deploy%20to%20Replit&label=%20&logo=replit&up_message=Deploy&url=https%3A%2F%2Freplit.com" height="30px" alt="Deploy to Replit Button"></a> &nbsp;

**Note**: You need to set the `MONGODB_URI` environment variable to the URI of your MongoDB cluster.

## Method 2 - Docker (Recommended)

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

## Method 3 - Manual

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
![spoo me main page](https://github.com/spoo-me/url-shortener/assets/90309290/7ddf6b48-a952-4b5f-a64d-26e4ece3c972)

![spoo me result page](https://github.com/spoo-me/url-shortener/assets/90309290/5e930dff-f922-418b-95df-dc47894d4db1)

**Example Stats Page**

![image](https://github.com/Zingzy/spoo.me/assets/90309290/3eb2b44d-f8aa-490e-a11a-700845165e3b)
