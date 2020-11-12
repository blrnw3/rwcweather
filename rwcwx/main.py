import os

from flask import Flask

from rwcwx import logger


app = Flask(__name__)
app.config.from_mapping(
    SECRET_KEY=os.getenv("FLASK_SECRET", "_rwcwx_"),
)


@app.route('/')
def hello_world():
    return 'Hello, World!'


@app.route('/lol')
def lol():
    return {"lol": 1000}


def main():
    logger.info("Starting rwcwx")


if __name__ == '__main__':
    main()
