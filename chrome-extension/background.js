"use strict";

// Service worker (Manifest V3). Hozircha minimal — kelajakda kengaytirish uchun poydevor.
// Masalan: kontekst menyu, alarms (eslatma vaqti), badge yangilash va h.k.

chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === "install") {
    console.log("Tez Yordamchi o'rnatildi.");
  }
});
