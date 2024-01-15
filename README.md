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
    - [📋 Prerequisites](#-prerequisites)
    - [📂 Clone the repository](#-clone-the-repository)
    - [Creating a virtual environment (Optional)](#creating-a-virtual-environment-optional)
    - [Activate the virtual environment (Optional)](#activate-the-virtual-environment-optional)
    - [📦 Install dependencies](#-install-dependencies)
    - [Creating a .env file in the root directory](#creating-a-env-file-in-the-root-directory)
    - [➕ Adding environment variables to .env file](#-adding-environment-variables-to-env-file)
    - [🚀 Starting the server](#-starting-the-server)
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

### 📋 Prerequisites

- [MongoDB](https://www.mongodb.com/try/download/community) 🌿
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

### Creating a .env file in the root directory

```bash
touch .env
```

### ➕ Adding environment variables to .env file

```bash
MONGO_URI=<your_mongo_uri>
```
  To get your free MongoDB Atlas Cluster, visit [https://www.mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas)


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
