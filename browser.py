import sys
from request import request
from render import show

def load(url):
    headers, body = request(url)
    show(body)


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) >= 2 else "file://test.html"
    load(url)