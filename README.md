![Header](https://data.morphdb.io/assets/header.png)

## Features

[Morph](https://www.morph-data.io/) is a python-centric full-stack framework for building and deploying AI apps.

- **Fast to start** 🚀 - Allows you to get up and running with just three commands.
- **Deploy and operate 🌐** - Easily deploy your AI apps and manage them in production. Managed cloud is available for user authentication and secure data connection.
- **No HTML/CSS knowledge required🔰** - With **Markdown-based syntax** and **pre-made components**, you can create flexible, visually appealing designs without writing a single line of HTML or CSS.
- **Customizable 🛠️** - **Chain Python and SQL** for advanced AI workflows. Custom CSS and custom React components are available for building tailored UI.

## Quick start

1. Install morph

```bash
pip install morph-data
```

2. Create a new project

```bash
morph new
```

3. Start dev server

```bash
morph serve
```

4. Visit `http://localhsot:8080` on browser.

## How it works

Understanding the concept of developing an AI app in Morph will let you do a flying start.

1. Develop the AI workflow in Python and give it an alias.
2. Create an .mdx file. Each .mdx file becomes a page of your app.
3. Place the component in the MDX file and specify the alias to connect to.

```
.
├─ pages
│  └─ index.mdx
└─ python
   └─ chat.py
```

## Building AI Apps

### A little example

1. Create each files in `python` and `pages` directories.

Python: Using Langchain to create a AI workflow.

```python
import morph
from morph import MorphGlobalContext
from morph_lib.stream import stream_chat
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

@morph.func
def langchain_chat(context: MorphGlobalContext):
    llm = ChatOpenAI(model="gpt-4o")
    messages = [HumanMessage(context.vars["prompt"])]
    for token in llm.stream(messages):
        yield stream_chat(token.content)
```

MDX: Define the page and connect the data.

```typescript
# 🦜🔗 Langchain Chat

<Chat postData="langchain_chat" height={300} />
```

2. Run `morph serve` to open the app!

![AI App](https://data.morphdb.io/assets/gif/langchain-demo.gif)

## Documentation

Visit https://docs.morph-data.io for more documentation.

## Contributing

Thanks for your interest in helping improve Morph ❤️

- Before contributing, please read the [CONTRIBUTING.md](CONTRIBUTING.md).
- If you find any issues, please let us know and open [an issue](https://github.com/morph-data/morph/issues/new/choose).

## Lisence

Morph is [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0) licensed.
