label = document.querySelectorAll("label")[0];

function lengthCheck() {
  var value = this.getAttribute("value");
  // var value = this.value
  if (value.length > 10) {
    label.innerHTML = "Comment too long!"
  }
}

input = document.querySelectorAll("input")[0];
input.addEventListener("keydown", lengthCheck);