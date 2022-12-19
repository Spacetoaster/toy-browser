import socket
import ssl
import gzip
import cache
from helpers import parse_cookie_string, is_cookie_expired

MAX_REDIRECTS = 10

COOKIE_JAR = {}

def build_request(host, path, top_level_url, payload = None):
    method = "POST" if payload else "GET"
    request_headers = {
        "HOST": host,
        "Connection": "close",
        "User-Agent": "Spacetoaster's Toy Browser",
        "Accept-Encoding": "gzip",
    }
    body = "{} {} HTTP/1.1\r\n".format(method, path)
    for header, value in request_headers.items():
        body += "{}: {}\r\n".format(header, value)
    if host in COOKIE_JAR:
        cookie, params = COOKIE_JAR[host]
        allow_cookie = True
        if top_level_url and params.get("samesite", "none") == "lax":
            _, _, top_level_host, _ = top_level_url.split("/", 3)
            if ":" in top_level_host:
                top_level_host, _ = top_level_host.split(":", 1)
            allow_cookie = (host == top_level_host or method == "GET")
        if "expires" in params and is_cookie_expired(params["expires"]):
            allow_cookie = False
            del COOKIE_JAR[host]
        if allow_cookie:
            body += "Cookie: {}\r\n".format(cookie)
    if payload:
        length = len(payload.encode("utf8"))
        body += "Content-Length: {}\r\n".format(length)
    body += "\r\n" + (payload if payload else "")
    return body.encode("utf8")

def request_http(scheme, url, top_level_url, num_redirects = 0, payload = None):
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

    try:
        s.connect((host, port))
    except ssl.SSLError:
        return {}, "SSL Error: preventing connection to {}".format(host)
    request = build_request(host, path, top_level_url, payload)
    s.send(request)

    response = s.makefile("rb")
    statusline = response.readline().decode('utf-8')
    version, status, explanation = statusline.split(" ", 2)
    headers = {}
    while True:
        line = response.readline().decode('utf-8')
        if line == "\r\n":
            break
        header, value = line.split(":", 1)
        headers[header.lower()] = value.strip()
    
    if status.startswith("3") and "location" in headers:
        if num_redirects >= MAX_REDIRECTS:
            raise Exception("Maximum number of redirects reached")
        return handle_redirect(scheme, url, headers["location"], num_redirects + 1)

    assert status == "200", "{}: {}".format(status, explanation)
    body = ""
    if "content-encoding" in headers and headers["content-encoding"] == "gzip":
        if "transfer-encoding" in headers and headers["transfer-encoding"] == "chunked":
            all_chunks = b''
            while True:
                line = response.readline().decode('utf-8')
                if line == "\r\n":
                    continue
                chunkSize = int(line, 16)
                if chunkSize == 0:
                    break
                chunk = response.read(chunkSize)
                all_chunks += chunk
            body = gzip.decompress(all_chunks).decode('utf-8')
        else:
            body_decompressed = gzip.decompress(response.read())
            body = body_decompressed.decode('utf-8')
    else:
        body = response.read().decode('utf-8')

    s.close()
    cache.try_to_cache("{}://{}".format(scheme, url), headers, body)
    if "set-cookie" in headers:
        COOKIE_JAR[host] = parse_cookie_string(headers["set-cookie"])

    return headers, body

def handle_redirect(scheme, url, location, num_redirects):
    if location.startswith("/"):
        return request_http(scheme, url + location, url + location, num_redirects)
    else:
        return request(location, location, num_redirects)

def request_file(url):
    file = open(url, "r")
    body = file.read()
    return {}, body

def request(url, top_level_url, num_redirects = 0, payload=None):
    headers, body = None, None
    view_source = False
    if url.startswith("view-source:"):
        view_source = True
        url = url[len("view-source:"):]
    
    method = "POST" if payload else "GET"

    cached_response = cache.get_cached_response(url)
    if cached_response and method == "GET":
        return cached_response[0], cached_response[1], view_source
    
    scheme, rest = url.split(":", 1)
    url = rest[2:] if rest.startswith("//") else rest
    assert scheme in ["http", "https", "file",
                      "data"], "Unknown scheme {}".format(scheme)
    if scheme in ["http", "https"]:
        headers, body = request_http(scheme, url, top_level_url, num_redirects, payload)
    elif scheme == "file":
        headers, body = request_file(url)
    elif scheme == "data":
        headers, body = request_data(url)

    return headers, body, view_source

def request_data(url):
    assert url.startswith("text/html"), "data request not of type text/html"
    media_type, body = url.split(",", 1)
    return None, body