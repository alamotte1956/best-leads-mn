(function () {
  "use strict";

  const root = document.getElementById("leadiq-rewards-wheel");
  if (!root || root.dataset.initialized === "true") return;
  root.dataset.initialized = "true";

  const prizes = [
    ["10% OFF", "#205b91"],
    ["$25 CREDIT", "#d65a15"],
    ["FREE LEAD", "#173452"],
    ["15% OFF", "#bc623b"],
    ["$10 CREDIT", "#317b98"],
    ["5% OFF", "#bc623b"],
    ["$50 CREDIT", "#3567b6"],
    ["20% OFF", "#d65a15"]
  ];

  const ns = "http://www.w3.org/2000/svg";
  const segments = document.getElementById("iq-segments");
  const rotor = document.getElementById("iq-rotor");
  const button = document.getElementById("iq-spin");
  const result = document.getElementById("iq-result");


  function point(radius, degrees) {
    const radians = degrees * Math.PI / 180;
    return [
      180 + radius * Math.cos(radians),
      180 + radius * Math.sin(radians)
    ];
  }

  prizes.forEach(function (prize, index) {
    const start = index * 45 - 90;
    const end = start + 45;
    const a = point(174, start);
    const b = point(174, end);

    const path = document.createElementNS(ns, "path");
    path.setAttribute(
      "d",
      "M180 180 L" + a[0] + " " + a[1] +
      " A174 174 0 0 1 " + b[0] + " " + b[1] + " Z"
    );
    path.setAttribute("fill", prize[1]);
    path.setAttribute("stroke", "white");
    path.setAttribute("stroke-width", "2");
    segments.appendChild(path);

    const text = document.createElementNS(ns, "text");
    text.setAttribute("x", "180");
    text.setAttribute("y", "68");
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("font-size", "11");
    text.setAttribute("font-weight", "bold");
    text.setAttribute("fill", "white");
    text.setAttribute(
      "transform",
      "rotate(" + (index * 45 + 22.5) + " 180 180)"
    );
    text.textContent = prize[0];
    segments.appendChild(text);
  });

  let rotation = 0;
  let spinning = false;
  button.disabled = false;
  button.textContent = "SPIN THE DEMO";
  button.addEventListener("click", function () {
    if (spinning) return;
    spinning = true;
    button.disabled = true;
    button.textContent = "SPINNING…";
    root.classList.remove("is-result");
    root.setAttribute("aria-busy", "true");
    result.textContent = "Demo wheel is spinning…";
    const index = Math.floor(Math.random() * prizes.length);
    const target = (360 - (index * 45 + 22.5)) % 360;
    const delta = (target - (rotation % 360) + 360) % 360;
    rotation += 6 * 360 + delta;
    const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let finished = false;
    let fallback;
    function finish(event) {
      if (event && (event.target !== rotor || event.propertyName !== "transform")) return;
      if (finished) return;
      finished = true;
      clearTimeout(fallback);
      rotor.removeEventListener("transitionend", finish);
      spinning = false;
      root.removeAttribute("aria-busy");
      root.classList.add("is-result");
      result.textContent = "Demo result: " + prizes[index][0] + ". Illustration only — no reward was awarded.";
      button.disabled = false;
      button.textContent = "SPIN DEMO AGAIN";
    }
    rotor.addEventListener("transitionend", finish);
    rotor.style.transition = reduced ? "none" : "transform 3.8s cubic-bezier(.12,.75,.15,1)";
    rotor.style.transform = "rotate(" + rotation + "deg)";
    if (reduced) finish();
    else fallback = setTimeout(finish, 4400);
  });
})();
