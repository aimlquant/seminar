(function () {
  "use strict";

  const allSlides = Array.from(document.querySelectorAll(".slide"));
  const includeAppendix = new URLSearchParams(window.location.search).get("appendix") === "1";
  const slides = includeAppendix
    ? allSlides
    : allSlides.filter((slide) => slide.dataset.deckAppendix !== "true");
  const counter = document.getElementById("deckCounter");
  const progress = document.getElementById("progress");
  const toc = document.getElementById("toc");
  const tocItems = document.getElementById("tocItems");
  const tocButton = document.getElementById("tocButton");
  const settingsPanel = document.getElementById("settingsPanel");
  const settingsToggle = document.getElementById("settingsToggle");
  const themeButton = document.getElementById("themeButton");
  let current = 0;
  let touchStart = null;
  let chromeTimer = null;

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function hashIndex() {
    const match = window.location.hash.match(/(?:#\/|#slide-)(\d+)$/);
    return match ? clamp(Number(match[1]) - 1, 0, slides.length - 1) : 0;
  }

  function slideLabel(slide, index) {
    return slide.getAttribute("aria-label") ||
      slide.querySelector("h1")?.textContent.trim() ||
      `슬라이드 ${index + 1}`;
  }

  function updateHash(index) {
    const nextHash = `#/${index + 1}`;
    if (window.location.hash !== nextHash) {
      window.history.replaceState(null, "", nextHash);
    }
  }

  function showSlide(index, options = {}) {
    current = clamp(index, 0, slides.length - 1);
    allSlides.forEach((slide) => {
      const slideIndex = slides.indexOf(slide);
      const active = slideIndex === current;
      slide.classList.toggle("is-deck-omitted", slideIndex < 0);
      slide.classList.toggle("is-active", active);
      slide.setAttribute("aria-hidden", String(!active));
    });

    slides.forEach((slide, slideIndex) => {
      slide.querySelectorAll("[data-slide-total]").forEach((node) => {
        node.textContent = String(slides.length);
      });
      slide.querySelectorAll("[data-slide-number]").forEach((node) => {
        node.textContent = String(slideIndex + 1).padStart(2, "0");
      });
    });

    counter.textContent = `${current + 1} / ${slides.length}`;
    progress.style.width = `${((current + 1) / slides.length) * 100}%`;
    tocItems.querySelectorAll(".toc-item").forEach((item, itemIndex) => {
      item.classList.toggle("current", itemIndex === current);
      item.setAttribute("aria-current", itemIndex === current ? "page" : "false");
    });
    document.title = `${slideLabel(slides[current], current)} · ${slides[0].querySelector("h1")?.textContent.trim() || "발표자료"}`;
    if (!options.skipHash) updateHash(current);
  }

  function move(delta) {
    showSlide(current + delta);
  }

  function buildToc() {
    slides.forEach((slide, index) => {
      const button = document.createElement("button");
      const number = document.createElement("span");
      const label = document.createElement("span");
      button.type = "button";
      button.className = "toc-item";
      number.textContent = String(index + 1).padStart(2, "0");
      label.textContent = slideLabel(slide, index);
      button.append(number, label);
      button.addEventListener("click", () => {
        showSlide(index);
        setToc(false);
      });
      tocItems.appendChild(button);
    });
  }

  function numberFigures() {
    let figureNumber = 0;
    slides.forEach((slide) => {
      slide.querySelectorAll("figure").forEach((figure) => {
        const caption = figure.querySelector(":scope > figcaption");
        if (!caption) return;
        figureNumber += 1;
        figure.dataset.deckFigureNumber = String(figureNumber);
        const explicitTitle = caption.querySelector("[data-deck-figure-title]")?.textContent.trim();
        const slideTitle = slide.querySelector("h1")?.textContent.trim();
        figure.dataset.deckFigureTitle = explicitTitle || slideTitle || "발표 그림";

        const bandLabel = caption.querySelector(":scope > b");
        if (bandLabel) {
          bandLabel.textContent = `그림 ${figureNumber}`;
          return;
        }
        const title = caption.querySelector(":scope > strong");
        if (!title) return;
        title.dataset.deckFigureTitle ||= title.textContent.trim();
        title.textContent = `그림 ${figureNumber} · ${title.dataset.deckFigureTitle}`;
      });
    });
  }

  function setToc(open) {
    if (open) setSettings(false);
    toc.classList.toggle("open", open);
    toc.setAttribute("aria-hidden", String(!open));
    tocButton.setAttribute("aria-expanded", String(open));
    if (open) showChrome();
  }

  function setSettings(open) {
    settingsPanel.classList.toggle("is-open", open);
    settingsPanel.setAttribute("aria-hidden", String(!open));
    settingsToggle.setAttribute("aria-expanded", String(open));
    if (open) {
      setToc(false);
      showChrome();
    }
  }

  function savedTheme() {
    try {
      return window.localStorage.getItem("aimlquant-deck-theme");
    } catch (_error) {
      return null;
    }
  }

  function applyTheme(theme) {
    document.documentElement.className = `theme-${theme}`;
    themeButton.textContent = theme === "dark" ? "☾" : "☀";
    themeButton.setAttribute("aria-pressed", String(theme === "dark"));
    themeButton.setAttribute("title", theme === "dark" ? "라이트 모드로 전환" : "나이트 모드로 전환");
    try {
      window.localStorage.setItem("aimlquant-deck-theme", theme);
    } catch (_error) {
      // Local files and private browsing may reject storage. Navigation still works.
    }
  }

  function toggleTheme() {
    applyTheme(document.documentElement.classList.contains("theme-dark") ? "light" : "dark");
  }

  function toggleFullscreen() {
    if (document.fullscreenElement) {
      document.exitFullscreen?.();
    } else {
      document.documentElement.requestFullscreen?.();
    }
  }

  function fitStage() {
    const scale = Math.min(window.innerWidth / 1280, window.innerHeight / 720);
    document.documentElement.style.setProperty("--deck-scale", String(scale));
  }

  function hideChrome() {
    if (!toc.classList.contains("open") && !settingsPanel.classList.contains("is-open")) {
      document.body.classList.add("chrome-hidden");
    }
  }

  function showChrome() {
    document.body.classList.remove("chrome-hidden");
    window.clearTimeout(chromeTimer);
    chromeTimer = window.setTimeout(hideChrome, 2600);
  }

  document.getElementById("prevButton").addEventListener("click", () => move(-1));
  document.getElementById("nextButton").addEventListener("click", () => move(1));
  themeButton.addEventListener("click", toggleTheme);
  document.getElementById("fullscreenButton").addEventListener("click", toggleFullscreen);
  tocButton.addEventListener("click", () => setToc(!toc.classList.contains("open")));
  settingsToggle.addEventListener("click", () => setSettings(!settingsPanel.classList.contains("is-open")));

  document.addEventListener("keydown", (event) => {
    showChrome();
    if (event.key === "Escape") {
      setToc(false);
      setSettings(false);
      return;
    }
    if (event.target.matches("input, textarea, button, a, select, [contenteditable='true']")) return;
    if (["ArrowRight", "PageDown", " "].includes(event.key)) {
      event.preventDefault();
      move(1);
    } else if (["ArrowLeft", "PageUp"].includes(event.key)) {
      event.preventDefault();
      move(-1);
    } else if (event.key === "Home") {
      event.preventDefault();
      showSlide(0);
    } else if (event.key === "End") {
      event.preventDefault();
      showSlide(slides.length - 1);
    } else if (event.key.toLowerCase() === "f") {
      toggleFullscreen();
    } else if (event.key.toLowerCase() === "d") {
      toggleTheme();
    } else if (event.key.toLowerCase() === "m") {
      setToc(!toc.classList.contains("open"));
    }
  });

  document.addEventListener("click", (event) => {
    if (toc.classList.contains("open") && !event.target.closest(".toc, .toc-button")) {
      setToc(false);
    }
    if (settingsPanel.classList.contains("is-open") && !event.target.closest(".deck-settings")) {
      setSettings(false);
    }
  });
  document.addEventListener("mousemove", showChrome);
  document.addEventListener("touchstart", (event) => {
    touchStart = event.touches[0]?.clientX ?? null;
    showChrome();
  }, { passive: true });
  document.addEventListener("touchend", (event) => {
    if (touchStart === null) return;
    const delta = (event.changedTouches[0]?.clientX ?? touchStart) - touchStart;
    if (Math.abs(delta) > 50) move(delta < 0 ? 1 : -1);
    touchStart = null;
  }, { passive: true });
  window.addEventListener("hashchange", () => showSlide(hashIndex(), { skipHash: true }));
  window.addEventListener("resize", fitStage);
  window.addEventListener("beforeprint", () => document.body.classList.remove("chrome-hidden"));

  numberFigures();
  buildToc();
  fitStage();
  applyTheme(savedTheme() === "dark" ? "dark" : "light");
  showSlide(hashIndex(), { skipHash: true });
  showChrome();
})();
