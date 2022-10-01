import socket
import ssl
import gzip
import cache

MAX_REDIRECTS = 10

def build_request(host, path):
    request_headers = {
        "HOST": host,
        "Connection": "close",
        "User-Agent": "Spacetoaster's Toy Browser",
        "Accept-Encoding": "gzip",
    }
    request = "GET {} HTTP/1.1\r\n".format(path).encode("utf8")
    for header, value in request_headers.items():
        request += "{}: {}\r\n".format(header, value).encode("utf8")
    request += "\r\n".encode("utf8")
    return request

def request_http(scheme, url, num_redirects):
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
    if headers["content-encoding"] == "gzip":
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
        body = response.read()

    s.close()
    cache.try_to_cache("{}://{}".format(scheme, url), headers, body)

    return headers, body

def handle_redirect(scheme, url, location, num_redirects):
    if location.startswith("/"):
        return request_http(scheme, url + location, num_redirects)
    else:
        return request(location, num_redirects)

def request_file(url):
    file = open(url, "r")
    body = file.read()
    return None, body

def request(url, num_redirects = 0):
    headers, body = None, None
    view_source = False
    if url.startswith("view-source:"):
        view_source = True
        url = url[len("view-source:"):]

    cached_response = cache.get_cached_response(url)
    if cached_response:
        return cached_response
    
    scheme, rest = url.split(":", 1)
    url = rest[2:] if rest.startswith("//") else rest
    assert scheme in ["http", "https", "file",
                      "data"], "Unknown scheme {}".format(scheme)
    if scheme in ["http", "https"]:
        headers, body = request_http(scheme, url, num_redirects)
    elif scheme == "file":
        headers, body = request_file(url)
    elif scheme == "data":
        headers, body = request_data(url)

    if (view_source):
        body = transform_for_viewsource(body)

    return headers, body

def request_data(url):
    assert url.startswith("text/html"), "data request not of type text/html"
    media_type, body = url.split(",", 1)
    return None, body

def transform_for_viewsource(body):
    body = body.replace("<", "&lt;")
    body = body.replace(">", "&gt;")
    body = "<body>{}</body>".format(body)
    return body