function lengthCheck() {
  var name = this.getAttribute("name");
  var value = this.getAttribute("value");
  console.log("lenghCheck called with length " + value.length);
  if (value.length > 5) {
    console.log("Input " + name + "has too much text.");
  }
}

var inputs = document.querySelectorAll("input");
for (var i = 0; i < inputs.length; i++) {
  inputs[i].addEventListener("keydown", lengthCheck)
}