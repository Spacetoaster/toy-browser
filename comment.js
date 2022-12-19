label = document.querySelectorAll("label")[0];
allow_submit = true;

function lengthCheck() {
  allow_submit = this.getAttribute("value").length <= 100;
  if (!allow_submit) {
    label.innerHTML = "Comment too long!"
  }
}

// input = document.querySelectorAll("input")[0];
// input.addEventListener("keydown", lengthCheck);

// form = document.querySelectorAll("form")[0];
// form.addEventListener("submit", function(e) {
//   if (!allow_submit) e.preventDefault();
// })

var a = new XMLHttpRequest();
// api.github.com sends "Access-Control-Allow-Origin: *", so it should work
a.open("GET", "https://api.github.com/", false)
// example.org sends no "Access-Control-Allow-Origin"-Header, request should not work
// a.open("GET", "http://example.org/", false)
a.send()
console.log("XHR response: " + a.responseText)
