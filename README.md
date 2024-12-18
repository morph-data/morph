## Features

**Morph** is a python-centric full-stack framework for building and deploying data apps.

- **Fast to start** 🚀 - Allows you to get up and running with just three commands.
- **Deploy and operate 🌐** - Easily deploy your data apps and manage them in production. Managed cloud is available for user authentication and secure data connection.
- **No HTML/CSS knowledge required🔰** - With **Markdown-based syntax** and **pre-made components**, you can create flexible, visually appealing designs without writing a single line of HTML or CSS.
- **Customizable 🛠️** - **Chain Python and SQL** for advanced data workflows. Custom CSS and custom React components are available for building tailored UI.

## Quick start

1. Install morph

```bash
pip install morph-data
```

1. Create a new project

```bash
morph new
```

3. Start dev server

```bash
morph serve
```

4. Visit `http://localhsot:9002` on browser.

## How it works

Understanding the concept of developing a data app in Morph will let you do a flying start.

1. Develop the data processing in Python and give it an alias.
2. Create an .mdx file. Each .mdx file becomes a page of your app.
3. Place the component in the MDX file and specify the alias to connect to.

```
.
├─ pages
│  └─ index.mdx
├─ python
│  └─ closing_deals_vis.py
└─ sql
   └─ closing_deals.sql
```

## Documentation

Visit https://docs.morph-data.io for more documentation.

## Lisence