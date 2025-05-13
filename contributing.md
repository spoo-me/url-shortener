# Contributing Guidelines

First off, thank you for considering contributing to this project! It's people like you that make the open source community such a fantastic place to learn, inspire, and create. Every contribution helps and is greatly appreciated!

In this document, you will find guidelines and directions for contributing to this project. Please respect these guidelines as they are meant to foster a consistent and respectful approach to collaboration.

## 📖 Table of Contents

- [Contributing Guidelines](#contributing-guidelines)
  - [📖 Table of Contents](#-table-of-contents)
  - [📜 Code of Conduct](#-code-of-conduct)
  - [💡 How Can I Contribute?](#-how-can-i-contribute)
  - [🪲 Reporting Bugs](#-reporting-bugs)
  - [✨ Suggesting Enhancements](#-suggesting-enhancements)
  - [📥 Pull Requests Guidelines](#-pull-requests-guidelines)
  - [🏗️ Project Structure](#️-project-structure)
  - [📚 Pre-requisites](#-pre-requisites)
  - [🚀 Getting started](#-getting-started)
  - [🎨 Styleguides](#-styleguides)
    - [💬 Git Commit Messages](#-git-commit-messages)
    - [🐍 Python Styleguide](#-python-styleguide)
    - [🌐 Html, css and Javascript Styleguide](#-html-css-and-javascript-styleguide)
  - [🛠️ Basic Jinja2 Templating Engine introduction](#️-basic-jinja2-templating-engine-introduction)
  - [✍🏻 Writing Blog Posts and Tutorials](#-writing-blog-posts-and-tutorials)
  - [📝 Additional Notes](#-additional-notes)
  - [⚖️ License](#️-license)

## 📜 Code of Conduct

This project and everyone participating in it is governed by the [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to [support@spoo.me](mailto:support@spoo.me).

## 💡 How Can I Contribute?

You can contribute to this project in many ways. Here are a few ideas:

- Reporting bugs and issues on GitHub 🪲
- Suggesting enhancements and new features on GitHub ✨
- Fixing bugs and issues by submitting pull requests 🛠️
- Implementing new features
- Improving the documentation 📝
- Sharing the project with others 📣
- Providing support to other people who are using the project 🤝
- Writing blog posts and tutorials ✍🏻

We are always available to help you with your contribution. If you are unsure about anything, just ping us on [discord](https://spoo.me/discord) or submit the issue or pull request anyway. The worst that can happen is that you'll be asked to change something about your contribution.

## 🪲 Reporting Bugs

Before creating bug reports, please check the existing bug reports as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible.

## ✨ Suggesting Enhancements

Before creating enhancement suggestions, please check the existing suggestions as you might find out that you don't need to create one. When you are creating an enhancement suggestion, please include as many details as possible.

## 📥 Pull Requests Guidelines

The process described here has several goals:

- Maintain the project's quality
- Fix problems that are important to users
- Engage the community in working toward the best possible project
- Enable a sustainable system for the project's maintainers to review contributions

Please follow these steps to have your contribution considered by the maintainers:

1. Follow all instructions in the template
2. Adhering to the project's code of conduct
3. Follow the styleguides
4. After you submit your pull request, verify that all status checks are passing
5. After you create a pull request, maintainers will review your proposal and discuss it with you

## 🏗️ Project Structure

The project is structured as follows:

```plaintext
url-shortener/
│   .env
│   .env.example
│   .gitignore
│   contributing.md
│   docker-compose.yml
│   dockerfile
│   emojies.py
│   LICENSE
│   main.py
│   README.md
│   requirements.txt
│   utils.py
│   vercel.json
├───.github
│   └───workflows
│           api_test.yaml
│           format.yaml
├───misc
├───static
│   ├───css
│   │       api.css
│   │       base.css
│   │       confetti.css
│   │       contacts-modal.css
│   │       error.css
│   │       header.css
│   │       index.css
│   │       mobile-header.css
│   │       password.css
│   │       prism-duotone-dark.css
│   │       result.css
│   │       self-promo.css
│   │       stats-view.css
│   │       stats.css
│   ├───images
│   ├───js
│   │       confetti.js
│   │       contacts-popup.js
│   │       header.js
│   │       index-qrcode.js
│   │       index-script.js
│   │       index-validate.js
│   │       result-script.js
│   │       self-promo.js
│   │       stats-script.js
│   │       stats-view-script.js
│   └───previews
├───templates
│       api.html
│       error.html
│       index.html
│       password.html
│       result.html
│       stats.html
│       stats_view.html
└───tests
        shorten.py
        stats.py
```

## 📚 Pre-requisites

- Python 3.9 or higher
- pip
- virtualenv
- MongoDB
- Basic knowledge of Python, HTML, CSS, and JavaScript
- Basic knowledge of jinja2 templating engine; **more information on this can be found in the** [Basic Jinja2 Templating Engine introduction](#️-basic-jinja2-templating-engine-introduction) **section**
- Basic knowledge of MongoDB

**Note:** If you are just here to contribute to the frontend, having knowledge of Python and MongoDB is not necessary.

You need to have **MongoDB installed on your machine** to run the project. You can download it from [here](https://www.mongodb.com/try/download/community). Or you can also use **Instant MongoDB extension** available for Visual Studio Code.

## 🚀 Getting started

1. Fork the repository on GitHub
2. Clone the project to your own machine

```bash
git clone https://github.com/spoo-me/url-shortener.git
cd url-shortener
```

3. Create a new virtual environment
```bash
python -m venv venv
```

4. Install the project dependencies

```bash
pip install -r requirements.txt
```

5. Create a new branch

```bash
git checkout -b my-new-branch
```

6. Creating .env file

    - Copy and Rename the `.env.example` file to `.env`

7. Starting the development server

    - Activating the virtual environment
      
      MacOS/Linux:

        ```bash
        source venv/bin/activate
        ```
       Windows:
         ```cmd
         # For Command Prompt
         venv\Scripts\activate
         
         # For PowerShell
         venv\Scripts\Activate.ps1
         ```

    - Running the development server

        ```bash
        python main.py
        ```

8. You can access the development server at: http://127.0.0.1:8000/

9. Make your changes

    Note: If you made some changes in the static Files, you need to update the version of the static file in the static file import syntax of the HTML files. For example, if you made some changes in the `style.css` file, you need to update the version of the `style.css` file in the `index.html` file. You can do this by adding a query parameter to the end of the file name.

    **For example:**

    ``` html
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}?v=1"/>
    ```

    If the version of the file is already updated, you can just change the value of the query parameter to the next number. For example,

    ```html
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}?v=2"/>
    ```

    More information on how to do this can be found in the [Basic Jinja2 Templating Engine introduction](#️-basic-jinja2-templating-engine-introduction) section.

10.  Format your code, more information on how to do this can be found in the [Styleguides](#styleguides) section

11. Commit your changes

12. Check if all of the workflow checks are passing

13. Push your branch to your fork

## 🎨 Styleguides

For the sake of consistency and maintainability, we have a few styleguides that we follow. Please adhere to these guidelines when contributing to the project.

### 💬 Git Commit Messages

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters or less
- Reference issues and pull requests liberally after the first line
- Consider starting the commit message with an applicable emoji:

  - :tada: when adding a new feature
  - :art: when improving the format/structure of the code
  - :racehorse: when improving performance
  - :memo: when writing docs
  - :bug: when fixing a bug
  - :fire: when removing code or files
  - :lock: when dealing with security
  - :arrow_up: when upgrading dependencies
  - :arrow_down: when downgrading dependencies

### 🐍 Python Styleguide

All Python code should be formatted using the **black code formatter**. This ensures that all code is formatted consistently and makes it easier to review and maintain. **We have a workflow that automatically checks for code formatting and will fail if the code is not formatted correctly.**

How to Install Black:

```bash
pip install black
```

How to Use Black:

```bash
black *.py
```

### 🌐 Html, css and Javascript Styleguide

All HTML and CSS code should be formatted using the **prettier code formatter**. This ensures that all code is formatted consistently and makes it easier to review and maintain.

## 🛠️ Basic Jinja2 Templating Engine introduction

Jinja2 is a modern and designer-friendly templating language for Python, modelled after Django’s templates. It is fast, widely used and secure with the optional sandboxed template execution environment.

Files are stored in the `templates` directory and the static files are stored in the `static` directory. The `templates` directory contains the HTML files and the `static` directory contains the CSS, JavaScript, and images.

The HTML files are rendered using the Jinja2 templating engine. The Jinja2 templating engine uses the `{{ }}` syntax to render variables and the `{% %}` syntax to render control statements.

For example, the following code will render the `title` variable sent by the server in the HTML file:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta
      name="viewport"
      content="width=device-width, initial-scale=1.0"
    />
    <title>{{ title }}</title>
  </head>
  <body>
    <h1>{{ title }}</h1>
  </body>
</html>
```

**Separating the static files from the HTML files makes the project more organized and easier to maintain. The static files are included in the HTML files using the `url_for` function. The `url_for` function takes the name of the static file as an argument and returns the URL of the static file.**

For example, the following code will include the `style.css` file in the HTML file:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta
      name="viewport"
      content="width=device-width, initial-scale=1.0"
    />
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}"/>
  </head>
  <body>
    <h1>{{ title }}</h1>
  </body>
</html>
```

In the above example, the `url_for` function takes the name of the folder where the static file is stored and the name of the static file as arguments and returns the URL of the static file. In this project the static files are stored in the `static` folder and the `style.css` file is stored in the `css` folder.

The `url_for` function is the only way to include static files in the HTML files. You can also add inline CSS and JavaScript in the HTML files but it is not recommended.

In order to add local images in the HTML files, you can use the `url_for` function. For example, the following code will include the `logo.png` file in the HTML file:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta
      name="viewport"
      content="width=device-width, initial-scale=1.0"
    />
  </head>
  <body>
    <img src="{{ url_for('static', filename='images/logo.png') }}" alt="Logo"/>
  </body>
</html>
```

**IMPORTANT STEP:**

If you made some changes in the static files, you need to update the version of the static file in the static file import syntax of the HTML files. For example, if you made some changes in the `style.css` file, you need to update the version of the `style.css` file in the `index.html` file. You can do this by adding a query parameter to the end of the file name.

**For example:**

```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}?v=1"/>
```

If the version of the file is **already updated**, you can just change the value of the query parameter to the **next number**. For example,

```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}?v=2"/>
```

**DOING THIS IS REALLY IMPORTANT AS VERCEL CACHES THE STATIC FILES AND IF YOU DON'T UPDATE THE VERSION OF THE STATIC FILES, THE CHANGES YOU MADE IN THE STATIC FILES WILL NOT BE REFLECTED IN THE PRODUCTION SERVER.**

**Important Notes:**

- The `url_for` function is a Jinja2 function and can only be used in the HTML files.
- If you added some new static files, you need to add those files in the `static/<file_type>` directory and then include them in the HTML files using the `url_for` function.
- The `{{ }}` syntax is used to render **variables in HTML files only**. These variables are sent by the server. They cannot be accessed in the static files.
- The `{% %}` syntax is used to render **control statements in HTML files only**. These control statements are used to control the flow of the HTML file. They cannot be accessed in the static files.
- If you are here to **contribute to the frontend**, you **don't need to worry about the html variables and control statements**. **You just need to focus on the static files**. Although, it is recommended to have a basic understanding of the Jinja2 templating engine incase you want to change the structure of the HTML files.

Take a look at the [Jinja2 documentation](https://jinja.palletsprojects.com/en/3.0.x/templates/) for more information.

**In case of any confusion, you can ask for help in our** [**Discord Server**](https://spoo.me/discord).

## ✍🏻 Writing Blog Posts and Tutorials

If you are interested in writing blog posts and tutorials, you can talk to us on [Discord](https://spoo.me/discord) or send us an email at [admin@spoo.me](mailto:admin@spoo.me)

## 📝 Additional Notes

This project is a living document and will be updated as the project evolves. Please check back regularly for updates. We also reccomend you to join our [Discord Server](https://spoo.me/discord) to get in touch with the maintainers and other contributors.

## ⚖️ License

This project is licensed under the APACHE 2.0 License - see the [LICENSE](LICENSE) file for details.

<br><br>

![Contribution Charts](https://repobeats.axiom.co/api/embed/48a40934896cbcaff2812e80478ebb701ee49dd4.svg)
