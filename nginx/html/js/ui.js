const modeButtons = Array.from(document.querySelectorAll(".menu-btn"));
const simplePanel = document.getElementById("simple-panel");
const manualPanel = document.getElementById("manual-panel");

const setMode = (mode) => {
  const showManual = mode === "manual";

  modeButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.mode === mode);
  });

  manualPanel.hidden = !showManual;
  simplePanel.hidden = showManual;
};

modeButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setMode(button.dataset.mode);
  });
});

// Default sample view is the yellow panel mode.
setMode("model");
