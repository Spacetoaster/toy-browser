from parser import Element
import werkzeug.http
from datetime import datetime, timezone

def resolve_url(url, current):
    if "://" in url:
        return url
    elif url.startswith("/"):
        scheme, hostpath = current.split("://", 1)
        host, oldpath = hostpath.split("/", 1)
        return scheme + "://" + host + url
    elif url.startswith("#"):
        return current.split("#")[0] + url
    else:
        dir, _ = current.rsplit("/", 1)
        while url.startswith("../"):
            url = url[3:]
            if dir.count("/") == 2: continue
            dir, _ = dir.rsplit("/", 1)
        return dir + "/" + url

def tree_to_list(tree, list):
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list

def node_tree_to_html(node, include_node = True):
    s = ""
    if isinstance(node, Element):
        if include_node:
            s += "<{}".format(node.tag)
            if node.attributes:
                for attr in node.attributes:
                    s += " "
                    s += "{}=\"{}\"".format(attr, node.attributes[attr])
            s += ">"
        for child in node.children:
            s += node_tree_to_html(child)
        if include_node:
            s += "</{}>".format(node.tag)
    else:
        s += node.text
    return s

def url_origin(url):
    scheme_colon, _, host, _ = url.split("/", 3)
    return scheme_colon + "//" + host

def parse_cookie_string(cookie_str):
    params = {}
    if ";" in cookie_str:
        cookie, rest = cookie_str.split(";", 1)
        for param_pair in rest.split(";"):
            param_pair = param_pair.strip()
            if param_pair == "HttpOnly":
                params[param_pair] = True
                continue
            name, value = param_pair.split("=", 1)
            if name == "Expires":
                value = datetime_from_http_date(value)
            else:
                value = value.lower()
            params[name.lower()] = value
    else:
        cookie = cookie_str
    return (cookie, params)

def datetime_from_http_date(http_date_str):
    return werkzeug.http.parse_date(http_date_str)

def datetime_to_http_date(datetime_obj):
    return werkzeug.http.http_date(datetime_obj)

def is_cookie_expired(expires_date):
    return expires_date < datetime.now(timezone.utc)