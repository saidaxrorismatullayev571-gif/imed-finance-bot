"use strict";

// ---- Tab navigatsiyasi ----
const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".panel");

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    const name = tab.dataset.tab;
    tabs.forEach((t) => t.classList.toggle("active", t === tab));
    panels.forEach((p) =>
      p.classList.toggle("active", p.id === `panel-${name}`)
    );
  });
});

// ---- 1) Joriy sahifa ma'lumoti ----
const titleEl = document.getElementById("page-title");
const urlEl = document.getElementById("page-url");
const copyBtn = document.getElementById("copy-url");

chrome.tabs.query({ active: true, currentWindow: true }, (tabsArr) => {
  const tab = tabsArr[0];
  if (!tab) return;
  titleEl.textContent = tab.title || "(sarlavhasiz)";
  urlEl.textContent = tab.url || "—";
});

copyBtn.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(urlEl.textContent);
    copyBtn.textContent = "Nusxalandi ✓";
    setTimeout(() => (copyBtn.textContent = "URL nusxalash"), 1200);
  } catch {
    copyBtn.textContent = "Xatolik";
    setTimeout(() => (copyBtn.textContent = "URL nusxalash"), 1200);
  }
});

// ---- 2) Tez eslatma (chrome.storage.local orqali doimiy saqlash) ----
const noteInput = document.getElementById("note-input");
const noteStatus = document.getElementById("note-status");
const clearNote = document.getElementById("clear-note");
const NOTE_KEY = "quickNote";

chrome.storage.local.get(NOTE_KEY, (data) => {
  noteInput.value = data[NOTE_KEY] || "";
});

let saveTimer;
noteInput.addEventListener("input", () => {
  noteStatus.textContent = "Saqlanmoqda…";
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    chrome.storage.local.set({ [NOTE_KEY]: noteInput.value }, () => {
      noteStatus.textContent = "Saqlangan";
    });
  }, 400);
});

clearNote.addEventListener("click", () => {
  noteInput.value = "";
  chrome.storage.local.set({ [NOTE_KEY]: "" }, () => {
    noteStatus.textContent = "Tozalandi";
  });
});

// ---- 3) Matn hisoblagich ----
const counterInput = document.getElementById("counter-input");
const statChars = document.getElementById("stat-chars");
const statWords = document.getElementById("stat-words");
const statLines = document.getElementById("stat-lines");

function updateStats() {
  const text = counterInput.value;
  statChars.textContent = text.length;
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  statWords.textContent = words;
  statLines.textContent = text ? text.split(/\n/).length : 0;
}

counterInput.addEventListener("input", updateStats);
updateStats();
