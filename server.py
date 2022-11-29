import socket
import urllib.parse

TOPICS = { "browsers": ["Pavel was here"] }

def do_request(method, url, headers, body):
    if method == "POST" and url == "/add_topic":
        params = form_decode(body)
        return "200 OK", add_topic(params)
    if method == "POST" and "/add" in url:
        topic = url[1:].split("/", 1)[0]
        params = form_decode(body)
        return "200 OK", add_entry(params, topic)
    elif method == "GET" and "/add?" in url:
        query_data = url.split("?", 1)[1]
        query_data = form_decode(query_data)
        return "200 OK", add_entry(query_data)
    if method == "GET" and url == "/":
        return "200 OK", list_topics()
    elif method == "GET" and url == "/comment.js":
        with open("comment.js") as f:
            return "200 OK", f.read()
    elif method == "GET" and url == "/comment.css":
        with open("comment.css") as f:
            return "200 OK", f.read()
    elif method == "GET" and url.startswith("/"):
        topic = url[1:]
        if topic in TOPICS:
            return "200 OK", show_comments(topic)
        else:
            return "404 Not Found", not_found(url, method)
    else:
        return "404 Not Found", not_found(url, method)

def show_comments(topic):
    action = "'/{}/add'".format(topic)
    out = "<!doctype html>"
    out += "<link rel=stylesheet href=/comment.css></link>"
    out += "<h1>Posts about {}</h1>".format(topic)
    for entry in TOPICS[topic]:
        out += "<p>" + entry + "</p>"
    out += "<form action={} method=post>".format(action)
    out +=   "<p><input name=guest></p>"
    # out +=   "<p><input name=text></p>"
    # out +=   "<p><input name=bla value=cheekycheckbox type=checkbox> Checkbox label</p>"
    out +=   "<p><button>Post</button></p>"
    out += "<label></label>"
    out += "</form>"
    out += "<script src=/comment.js></script>"
    out += "<a href='/'>back to topics</a>"
    return out

def list_topics():
    out = "<!doctype html>"
    out += "<h1>List of topics</h1>"
    for topic in TOPICS:
        out += "<p><a href='/{}'>".format(topic) + topic + "</a></p>"
    out += "<form action=add_topic method=post>"
    out +=   "<p><input name=topic></p>"
    out +=   "<p><button>New Topic</button></p>"
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

def add_entry(params, topic):
    if 'guest' in params:
        TOPICS[topic].append(params['guest'])
    return show_comments(topic)

def add_topic(params):
    if 'topic' in params:
        TOPICS[params['topic']] = []
        return show_comments(params['topic'])
    else:
        return list_topics()

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
    # response += "Cache-Control: max-age=10000\r\n"
    response += "\r\n" + body
    conx.send(response.encode('utf8'))
    conx.close()
    print("closed connection {}".format(conx))

while True:
    print("listing for new request")
    conx, addr = s.accept()
    print("got new request")
    handle_connection(conx)