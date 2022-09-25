import socket;
import ssl;
import sys;

url = "http://example.org/index.html"

def build_request(host, path):
  request_headers = {
    "HOST": host,
    "Connection": "close",
    "User-Agent": "Spacetoaster's Toy Browser",
  }
  request = "GET {} HTTP/1.1\r\n".format(path).encode("utf8")
  for header, value in request_headers.items():
    request += "{}: {}\r\n".format(header, value).encode("utf8")
  request += "\r\n".encode("utf8")
  return request

def request_http(scheme, url):
  port = 80 if scheme == "http" else 443
  host, path = url.split("/", 1)
  if ":" in host:
    host, port = host.split(":", 1)
    port = int(port)
  path = "/" + path

  s = socket.socket(
    family=socket.AF_INET,
    type=socket.SOCK_STREAM,
    proto=socket.IPPROTO_TCP,
  )
  if scheme == "https":
    ctx = ssl.create_default_context()
    s = ctx.wrap_socket(s, server_hostname=host)

  s.connect((host, port))
  request = build_request(host, path)
  s.send(request)

  response = s.makefile("r", encoding="utf8", newline="\r\n")
  statusline = response.readline()
  version, status, explanation = statusline.split(" ", 2)
  assert status == "200", "{}: {}".format(status, explanation)
  headers = {}
  while True:
    line = response.readline()
    if line == "\r\n": break
    header, value = line.split(":", 1)
    headers[header.lower()] = value.strip()

  assert "transfer-encoding" not in headers
  assert "content-encoding" not in headers

  body = response.read()
  s.close()

  return headers, body

def request_file(url):
  file = open(url, "r")
  body = file.read()
  return None, body

def request_data(url):
  assert url.startswith("text/html"), "data request not of type text/html"
  media_type, body = url.split(",", 1)
  return None, body


def request(url):
  scheme, rest = url.split(":", 1)
  url = rest[2:] if rest.startswith("//") else rest
  assert scheme in ["http", "https", "file", "data"], "Unknown scheme {}".format(scheme)
  if scheme in ["http", "https"]:
    return request_http(scheme, url)
  elif scheme == "file":
    return request_file(url)
  elif scheme == "data":
    return request_data(url)
    

def show(body):
  in_angle = False
  for c in body:
    if c == "<":
      in_angle = True
    elif c == ">":
      in_angle = False
    elif not in_angle:
      print(c, end="")
  print("")


def load(url):
  headers, body = request(url)
  show(body)

if __name__ == "__main__":
  url = sys.argv[1] if len(sys.argv) >= 2 else "file://test.html"
  load(url)