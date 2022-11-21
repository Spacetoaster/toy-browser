from datetime import datetime

cache = {}

def try_to_cache(url, headers, body):
    if not "cache-control" in headers:
        return
    cache_control = headers["cache-control"]
    if cache_control.startswith("max-age"):
        max_age_value = cache_control[len("max-age="):]
        if not max_age_value.isnumeric():
            return
        max_age = int(max_age_value)
        age = 0
        if "age" in headers:
            age = int(headers["age"])
        now_timestamp = int(datetime.timestamp(datetime.now()))
        cache[url] = {
            "response": (headers, body),
            "fresh_until": now_timestamp + max_age - age,
        }

def get_cached_response(url):
    if url in cache:
        cached = cache[url]
        now_timestamp = int(datetime.timestamp(datetime.now()))
        fresh_until = cached["fresh_until"]
        if now_timestamp <= fresh_until:
            response = cached["response"]
            return response[0], response[1]