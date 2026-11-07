(function () {
  var scan = document.getElementById("scan");
  var mask = document.getElementById("mask");
  var lens = document.getElementById("lens");
  var touchId = null;

  function radius() {
    var width = scan.getBoundingClientRect().width;
    return Math.max(68, Math.min(width * 0.46, 124));
  }

  function place(clientX, clientY, lift) {
    var rect = scan.getBoundingClientRect();
    var x = clientX - rect.left;
    var y = clientY - rect.top - lift;
    var size = radius();
    mask.style.clipPath = "circle(" + size + "px at " + x + "px " + y + "px)";
    lens.style.left = x + "px";
    lens.style.top = y + "px";
    lens.style.width = size * 2 + "px";
    lens.style.height = size * 2 + "px";
    lens.hidden = false;
  }

  function hide() {
    lens.hidden = true;
    mask.style.clipPath = "circle(0px at 50% 50%)";
  }

  scan.addEventListener("pointermove", function (event) {
    if (event.pointerType === "touch") {
      if (event.pointerId !== touchId) return;
      event.preventDefault();
      place(event.clientX, event.clientY, radius() * 0.9);
      return;
    }
    place(event.clientX, event.clientY, 0);
  });

  scan.addEventListener("pointerleave", function (event) {
    if (touchId !== null) return;
    hide();
  });

  scan.addEventListener("pointerdown", function (event) {
    if (event.pointerType === "mouse") return;
    event.preventDefault();
    touchId = event.pointerId;
    scan.setPointerCapture(event.pointerId);
    place(event.clientX, event.clientY, radius() * 0.9);
  });

  function endTouch(event) {
    if (event.pointerId !== touchId) return;
    touchId = null;
    hide();
  }

  scan.addEventListener("pointerup", endTouch);
  scan.addEventListener("pointercancel", endTouch);
})();
