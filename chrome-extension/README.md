# Tez Yordamchi — Chrome Extension

Oddiy, Claude API'siz ishlaydigan umumiy maqsadli Chrome extension (Manifest V3).

## Funksiyalar

| Tab | Vazifasi |
|---|---|
| **Sahifa** | Joriy ochilgan sahifaning sarlavhasi va URL manzilini ko'rsatadi, URL'ni bir tugma bilan nusxalaydi. |
| **Eslatma** | Tez yozib qo'yish uchun bloknot. Matn `chrome.storage.local` da avtomatik saqlanadi — brauzer yopilsa ham yo'qolmaydi. |
| **Hisoblagich** | Yozilgan matndagi belgi, so'z va qatorlar sonini real vaqtda sanaydi. |

## Fayl tuzilishi

```
chrome-extension/
├── manifest.json      # extension konfiguratsiyasi (MV3)
├── popup.html         # popup oyna razmetkasi
├── popup.css          # dizayn (yorug'/qorong'i rejim)
├── popup.js           # asosiy logika (3 ta tab)
├── background.js      # service worker (kelajakda kengaytirish uchun)
└── icons/             # 16 / 48 / 128 px iconlar
```

## O'rnatish (developer rejimi)

1. Chrome'da `chrome://extensions/` sahifasini oching.
2. O'ng yuqoridagi **Developer mode** (Dasturchi rejimi) ni yoqing.
3. **Load unpacked** tugmasini bosing.
4. Shu `chrome-extension/` papkasini tanlang.
5. Extension paneldagi puzzle 🧩 belgisidan "Tez Yordamchi" ni topib, pin qiling.

## Kengaytirish g'oyalari

- **Kontekst menyu**: sahifada matn tanlab, o'ng tugma orqali eslatmaga qo'shish (`chrome.contextMenus`).
- **Eslatma vaqti**: `chrome.alarms` bilan belgilangan vaqtda bildirishnoma.
- **Sahifadan ma'lumot o'qish**: `chrome.scripting.executeScript` orqali content script inject qilib, sahifadagi narx/jadval kabi ma'lumotlarni yig'ish.
- **Ko'p eslatma**: bitta o'rniga ro'yxat ko'rinishida saqlash.
