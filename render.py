def show(body):
    tag_name = ""
    in_body = False
    in_angle = False
    output = ""
    for c in body:
        if c == "<":
            in_angle = True
            tag_name = ""
        elif c == ">":
            in_angle = False
            if "body" in tag_name:
                in_body = not in_body
        elif in_angle:
            tag_name += c
        elif in_body:
            output += c
    output = output.replace("&lt;", "<")
    output = output.replace("&gt;", ">")
    print(output)