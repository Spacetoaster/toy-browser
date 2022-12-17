label = document.querySelectorAll("label")[0];
allow_submit = true;

function lengthCheck() {
  allow_submit = this.getAttribute("value").length <= 100;
  if (!allow_submit) {
    label.innerHTML = "Comment too long!"
  }
}

input = document.querySelectorAll("input")[0];
input.addEventListener("keydown", lengthCheck);

form = document.querySelectorAll("form")[0];
form.addEventListener("submit", function(e) {
  if (!allow_submit) e.preventDefault();
})

console.log("cookie (before set): " + document.cookie)
document.cookie = "token=42; SameSite=Lax"
console.log("cookie (after set): " + document.cookie)