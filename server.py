import socket
import urllib.parse
import random
import html
from datetime import datetime, timedelta, timezone
from helpers import datetime_to_http_date, is_cookie_expired

TOPICS = { "browsers": [
    ("Pavel was here", "cerealkiller"),
    ("HACK THE PLANET!!!", "crashoverride"),
] }
LOGINS = {
    "crashoverride": "0cool",
    "cerealkiller": "emmanuel",
    "": "",
}

def do_request(session, method, url, headers, body):
    if method == "POST" and url == "/add_topic":
        params = form_decode(body)
        return "200 OK", add_topic(session, params)
    elif method == "POST" and "/add" in url:
        topic = url[1:].split("/", 1)[0]
        params = form_decode(body)
        return "200 OK", add_entry(session, params, topic)
    elif method == "POST" and url == "/":
        params = form_decode(body)
        return do_login(session, params)
    elif method == "GET" and "/add?" in url:
        query_data = url.split("?", 1)[1]
        query_data = form_decode(query_data)
        return "200 OK", add_entry(session, query_data)
    if method == "GET" and url == "/":
        return "200 OK", list_topics(session)
    elif method == "GET" and url == "/comment.js":
        with open("comment.js") as f:
            return "200 OK", f.read()
    elif method == "GET" and url == "/cookie.js":
        with open("cookie.js") as f:
            return "200 OK", f.read()
    elif method == "GET" and url == "/comment.css":
        with open("comment.css") as f:
            return "200 OK", f.read()
    elif method == "GET" and url == "/login":
        return "200 OK", login_form(session)
    elif method == "GET" and url == "/test-cookie":
        return "200 OK", test_cookie(session)
    elif method == "GET" and url.startswith("/"):
        topic = url[1:]
        if topic in TOPICS:
            return "200 OK", show_comments(session, topic)
        else:
            return "404 Not Found", not_found(url, method)
    else:
        return "404 Not Found", not_found(url, method)

def test_cookie(session):
    out = "<!doctype html>"
    out += "<h1>Test Cookie expiration (console)</h1>"
    out += "<button id=\"btn\">get cookie</button>"
    out += "<script src=/cookie.js></script>"
    return out

def do_login(session, params):
    if "nonce" not in session or "nonce" not in params: return
    if session["nonce"] != params["nonce"]: return
    username = params.get("username")
    password = params.get("password")
    if username in LOGINS and LOGINS[username] == password:
        session["user"] = username
        return "200 OK", list_topics(session)
    else:
        out = "<!doctype html>"
        out += "<h1>Invalid password for {}</h1>".format(username)
        return "401 Unauthorized", out

def show_comments(session, topic):
    action = "'/{}/add'".format(topic)
    out = "<!doctype html>"
    out += "<link rel=stylesheet href=/comment.css></link>"
    out += "<script src=https://example.com/evil.js></script>"
    out += "<h1>Posts about {}</h1>".format(topic)
    for entry, who in TOPICS[topic]:
        out += "<p>" + html.escape(entry) + "\n"
        out += "<i>by " + html.escape(who) + "</i></p>"
    if "user" in session:
        nonce = str(random.random())[2:]
        session["nonce"] = nonce
        out += "<h1>Hello, " + session["user"] + "</h1>"
        out += "<form action={} method=post>".format(action)
        out +=   "<p><input name=guest></p>"
        out +=   "<input name=nonce type=hidden value=" + nonce + ">"
        out +=   "<p><button>Post</button></p>"
        out += "</form>"
    else:
        out += "<a href=/login>Sign in to write in the guest book</a><br>"
    out += "<script src=/comment.js></script>"
    out += "<a href='/'>back to topics</a>"
    return out

def list_topics(session):
    out = "<!doctype html>"
    out += "<h1>List of topics</h1>"
    for topic in TOPICS:
        out += "<p><a href='/{}'>".format(topic) + html.escape(topic) + "</a></p>"
    if "user" in session:
        nonce = str(random.random())[2:]
        session["nonce"] = nonce
        out += "<form action=add_topic method=post>"
        out +=   "<p><input name=topic></p>"
        out +=   "<p><button>New Topic</button></p>"
        out +=   "<input name=nonce type=hidden value=" + nonce + ">"
        out += "</form>"
    else:
        out += "<a href=/login>Sign in to add a topic</a><br>"
    return out

def form_decode(body):
    params = {}
    for field in body.split("&"):
        name, value = field.split("=", 1)
        name = urllib.parse.unquote_plus(name)
        value = urllib.parse.unquote_plus(value)
        params[name] = value
    return params

def add_entry(session, params, topic):
    if "nonce" not in session or "nonce" not in params: return
    if session["nonce"] != params["nonce"]: return
    if "user" not in session: return
    if 'guest' in params and len(params['guest']) <= 100:
        TOPICS[topic].append((params['guest'], session["user"]))
    return show_comments(session, topic)

def add_topic(session, params):
    if "nonce" not in session or "nonce" not in params: return
    if session["nonce"] != params["nonce"]: return
    if 'topic' in params:
        TOPICS[params['topic']] = []
        return show_comments(session, params['topic'])
    else:
        return list_topics()

def not_found(url, method):
    out = "<!doctyle html>"
    out += "<h1>{} {} not found!</h1>".format(method, url)
    return out

def login_form(session):
    nonce = str(random.random())[2:]
    session["nonce"] = nonce
    body = "<!doctype html>"
    body += "<form action=/ method=post>"
    body += "<p>Username: <input name=username></p>"
    body += "<p>Password: <input name=password type=password></p>"
    body += "<input name=nonce type=hidden value=" + nonce + ">"
    body += "<p><button>Log in</button></p>"
    body += "</form>"
    return body

s = socket.socket(
    family=socket.AF_INET,
    type=socket.SOCK_STREAM,
    proto=socket.IPPROTO_TCP,
)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

s.bind(('', 8000))
s.listen()

SESSIONS = {}

def cleanup_sessions():
    delete_tokens = []
    out = "tokens before cleanup:"
    for token in SESSIONS:
        expires = SESSIONS[token]["expires"]
        now = datetime.now(timezone.utc)
        if expires < now:
            session_age = now - expires
        else:
            session_age = expires - now
        out += " {} {}".format(token, session_age.seconds)
    print(out)
    for token in SESSIONS:
        session = SESSIONS[token]
        if "expires" in session and is_cookie_expired(session["expires"]):
            print("deleting session with token {}".format(token))
            delete_tokens.append(token)
    print("cleanup_sessions: deleting {} of {} sessions".format(len(delete_tokens), len(SESSIONS)))
    for token in delete_tokens:
        del SESSIONS[token]

def handle_connection(conx):
    req = conx.makefile("b")
    reqline = req.readline().decode('utf8')
    method, url, version = reqline.split(" ", 2)
    # print("handling request {} {} {}".format(method, url, version))
    assert method in ["GET", "POST"]
    csp = "default-src http://localhost:8000"
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
    if "cookie" in headers:
        token = headers["cookie"][len("token="):]
    else:
        token = str(random.random())[2:]
    cleanup_sessions()
    session = SESSIONS.setdefault(token, { "expires": datetime.now(timezone.utc) + timedelta(seconds=10) })
    status, body = do_request(session, method, url, headers, body)
    response = "HTTP/1.0 {}\r\n".format(status)
    response += "Content-Length: {}\r\n".format(len(body.encode("utf8")))
    response += "Content-Security-Policy: {}\r\n".format(csp)
    # response += "Cache-Control: max-age=10000\r\n"
    if "cookie" not in headers:
        print("sending new cookie")
        template = "Set-Cookie: token={}; SameSite=Lax"
        template += "; Expires={}".format(datetime_to_http_date(session["expires"]))
        template += "\r\n"
        response += template.format(token)
    response += "\r\n" + body
    conx.send(response.encode('utf8'))
    conx.close()
    # print("closed connection {}".format(conx))

while True:
    # print("listing for new request")
    conx, addr = s.accept()
    # print("got new request")
    handle_connection(conx)