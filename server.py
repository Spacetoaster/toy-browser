import socket
import urllib.parse

ENTRIES = ['Pavel was here']

def do_request(method, url, headers, body):
    if method == "GET" and url == "/":
        return "200 OK", show_comments()
    elif method == "POST" and url == "/add":
        params = form_decode(body)
        return "200 OK", add_entry(params)
    elif method == "GET" and "/add?" in url:
        query_data = url.split("?", 1)[1]
        query_data = form_decode(query_data)
        return "200 OK", add_entry(query_data)
    else:
        return "404 Not Found", not_found(url, method)

def show_comments():
    out = "<!doctype html>"
    for entry in ENTRIES:
        out += "<p>" + entry + "</p>"
    out += "<form action=add method=get>"
    out +=   "<p><input name=guest></p>"
    out +=   "<p><input name=text></p>"
    out +=   "<p><button>Sign the book!</button></p>"
    out += "</form>"
    return out

def form_decode(body):
    params = {}
    for field in body.split("&"):
        name, value = field.split("=", 1)
        name = urllib.parse.unquote_plus(name)
        value = urllib.parse.unquote_plus(value)
        params[name] = value
    return params

def add_entry(params):
    if 'guest' in params:
        ENTRIES.append(params['guest'])
    return show_comments()

def not_found(url, method):
    out = "<!doctyle html>"
    out += "<h1>{} {} not found!</h1>".format(method, url)
    return out

s = socket.socket(
    family=socket.AF_INET,
    type=socket.SOCK_STREAM,
    proto=socket.IPPROTO_TCP,
)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

s.bind(('', 8000))
s.listen()

def handle_connection(conx):
    req = conx.makefile("b")
    reqline = req.readline().decode('utf8')
    method, url, version = reqline.split(" ", 2)
    print("handling request {} {} {}".format(method, url, version))
    assert method in ["GET", "POST"]
    headers = {}
    while True:
        line = req.readline().decode('utf8')
        if line == '\r\n': break
        header, value = line.split(":", 1)
        headers[header.lower()] = value.strip()
    if 'content-length' in headers:
        length = int(headers['content-length'])
        body = req.read(length).decode('utf8')
    else:
        body = None
    status, body = do_request(method, url, headers, body)
    response = "HTTP/1.0 {}\r\n".format(status)
    response += "Content-Length: {}\r\n".format(len(body.encode("utf8")))
    response += "\r\n" + body
    conx.send(response.encode('utf8'))
    conx.close()
    print("closed connection {}".format(conx))

while True:
    print("listing for new request")
    conx, addr = s.accept()
    print("got new request")
    handle_connection(conx)