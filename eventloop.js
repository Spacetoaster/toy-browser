var count = 0;
function callback() {
  var output = document.querySelectorAll("div")[1];
  output.innerHTML = "count: " + (count++);
  if (count < 100) {
    for (var i = 0; i < 5e6; i++);
    requestAnimationFrame(callback);
  }
}
requestAnimationFrame(callback);