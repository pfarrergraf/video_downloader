#!/usr/bin/env node
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const ROOTS = ["video_downloader/web/static/i18n", "pro/website/i18n"];

export const PRO_LIMIT = {
  am: "Pro የDownloadThatን ዕለታዊ የመተግበሪያ ማውረድ ገደብ ያስወግዳል።",
  ar: "يزيل Pro حد التنزيل اليومي داخل تطبيق DownloadThat.",
  bg: "Pro премахва дневния лимит за изтегляния в приложението DownloadThat.",
  bn: "Pro DownloadThat অ্যাপের দৈনিক ডাউনলোড সীমা সরিয়ে দেয়।",
  cs: "Pro odstraní denní limit stahování v aplikaci DownloadThat.",
  da: "Pro fjerner DownloadThats daglige downloadgrænse i appen.",
  de: "Pro entfernt das tägliche App-Downloadlimit von DownloadThat.",
  el: "Το Pro καταργεί το ημερήσιο όριο λήψεων της εφαρμογής DownloadThat.",
  en: "Pro removes DownloadThat's daily app download limit.",
  es: "Pro elimina el límite diario de descargas de la aplicación DownloadThat.",
  et: "Pro eemaldab DownloadThati rakenduse päevase allalaadimispiirangu.",
  fa: "نسخه Pro محدودیت روزانه دانلود در برنامه DownloadThat را حذف می‌کند.",
  fi: "Pro poistaa DownloadThat-sovelluksen päivittäisen latausrajan.",
  fil: "Inaalis ng Pro ang pang-araw-araw na limitasyon sa pag-download ng DownloadThat app.",
  fr: "Pro supprime la limite quotidienne de téléchargements de l’application DownloadThat.",
  gu: "Pro DownloadThat એપની દૈનિક ડાઉનલોડ મર્યાદા દૂર કરે છે.",
  he: "Pro מסיר את מגבלת ההורדות היומית באפליקציית DownloadThat.",
  hi: "Pro, DownloadThat ऐप की दैनिक डाउनलोड सीमा हटा देता है।",
  hr: "Pro uklanja dnevno ograničenje preuzimanja u aplikaciji DownloadThat.",
  hu: "A Pro eltávolítja a DownloadThat alkalmazás napi letöltési korlátját.",
  id: "Pro menghapus batas unduhan harian di aplikasi DownloadThat.",
  it: "Pro rimuove il limite giornaliero di download dell’app DownloadThat.",
  ja: "ProではDownloadThatアプリの1日あたりのダウンロード上限がなくなります。",
  kn: "Pro DownloadThat ಆ್ಯಪ್‌ನ ದೈನಂದಿನ ಡೌನ್‌ಲೋಡ್ ಮಿತಿಯನ್ನು ತೆಗೆದುಹಾಕುತ್ತದೆ.",
  ko: "Pro는 DownloadThat 앱의 일일 다운로드 제한을 제거합니다.",
  lt: "Pro pašalina „DownloadThat“ programos dienos atsisiuntimų limitą.",
  lv: "Pro noņem DownloadThat lietotnes dienas lejupielāžu ierobežojumu.",
  ml: "Pro DownloadThat ആപ്പിലെ പ്രതിദിന ഡൗൺലോഡ് പരിധി നീക്കുന്നു.",
  mr: "Pro DownloadThat अॅपची दैनिक डाउनलोड मर्यादा काढून टाकते.",
  ms: "Pro mengalih keluar had muat turun harian aplikasi DownloadThat.",
  nl: "Pro verwijdert de dagelijkse downloadlimiet van de DownloadThat-app.",
  no: "Pro fjerner den daglige nedlastingsgrensen i DownloadThat-appen.",
  pa: "Pro DownloadThat ਐਪ ਦੀ ਰੋਜ਼ਾਨਾ ਡਾਊਨਲੋਡ ਸੀਮਾ ਹਟਾਉਂਦਾ ਹੈ।",
  pl: "Pro usuwa dzienny limit pobierania w aplikacji DownloadThat.",
  pt: "O Pro remove o limite diário de downloads da aplicação DownloadThat.",
  ro: "Pro elimină limita zilnică de descărcări din aplicația DownloadThat.",
  ru: "Pro снимает суточный лимит загрузок в приложении DownloadThat.",
  sk: "Pro odstráni denný limit sťahovania v aplikácii DownloadThat.",
  sl: "Pro odstrani dnevno omejitev prenosov v aplikaciji DownloadThat.",
  sr: "Pro уклања дневно ограничење преузимања у апликацији DownloadThat.",
  sv: "Pro tar bort den dagliga nedladdningsgränsen i DownloadThat-appen.",
  sw: "Pro huondoa kikomo cha kila siku cha upakuaji katika programu ya DownloadThat.",
  ta: "Pro, DownloadThat செயலியின் தினசரி பதிவிறக்க வரம்பை நீக்குகிறது.",
  te: "Pro DownloadThat యాప్‌లోని రోజువారీ డౌన్‌లోడ్ పరిమితిని తొలగిస్తుంది.",
  th: "Pro จะนำขีดจำกัดการดาวน์โหลดรายวันของแอป DownloadThat ออก",
  tr: "Pro, DownloadThat uygulamasındaki günlük indirme sınırını kaldırır.",
  uk: "Pro скасовує добовий ліміт завантажень у застосунку DownloadThat.",
  ur: "Pro، DownloadThat ایپ کی یومیہ ڈاؤن لوڈ حد ختم کر دیتا ہے۔",
  vi: "Pro loại bỏ giới hạn tải xuống hằng ngày trong ứng dụng DownloadThat.",
  zh: "Pro 会移除 DownloadThat 应用内的每日下载限制。",
};

export const FREE_MARKER = {
  am: "በነፃ",
  ar: "مجانًا",
  bg: "безплатно",
  bn: "বিনামূল্যে",
  cs: "zdarma",
  da: "gratis",
  de: "kostenlos",
  el: "δωρεάν",
  en: "free",
  es: "gratis",
  et: "tasuta",
  fa: "رایگان",
  fi: "maksutta",
  fil: "libre",
  fr: "gratuitement",
  gu: "મફત",
  he: "בחינם",
  hi: "मुफ़्त",
  hr: "besplatno",
  hu: "ingyenesen",
  id: "gratis",
  it: "gratuitamente",
  ja: "無料",
  kn: "ಉಚಿತವಾಗಿ",
  ko: "무료",
  lt: "nemokamai",
  lv: "bez maksas",
  ml: "സൗജന്യമായി",
  mr: "विनामूल्य",
  ms: "percuma",
  nl: "gratis",
  no: "gratis",
  pa: "ਮੁਫ਼ਤ",
  pl: "bezpłatnie",
  pt: "gratuitamente",
  ro: "gratuit",
  ru: "бесплатно",
  sk: "zadarmo",
  sl: "brezplačno",
  sr: "бесплатно",
  sv: "gratis",
  sw: "bila malipo",
  ta: "இலவசமாக",
  te: "ఉచితంగా",
  th: "ฟรี",
  tr: "ücretsiz",
  uk: "безкоштовно",
  ur: "مفت",
  vi: "miễn phí",
  zh: "免费",
};

const ROLLING_WINDOW = {
  am: "በተንቀሳቃሽ 24 ሰዓታት {count} የተሳኩ ማውረዶች",
  ar: "{count} عمليات تنزيل ناجحة خلال كل 24 ساعة متحركة",
  bg: "{count} успешни изтегляния за всеки подвижен период от 24 часа",
  bn: "প্রতি চলমান 24 ঘণ্টায় {count}টি সফল ডাউনলোড",
  cs: "{count} úspěšná stažení za každých klouzavých 24 hodin",
  da: "{count} gennemførte downloads pr. løbende 24 timer",
  de: "{count} erfolgreiche Downloads je rollierenden 24 Stunden",
  el: "{count} επιτυχημένες λήψεις ανά κυλιόμενο 24ωρο",
  en: "{count} successful downloads per rolling 24 hours",
  es: "{count} descargas correctas por cada periodo móvil de 24 horas",
  et: "{count} edukat allalaadimist iga jooksva 24 tunni jooksul",
  fa: "{count} دانلود موفق در هر بازه شناور ۲۴ ساعته",
  fi: "{count} onnistunutta latausta liukuvan 24 tunnin aikana",
  fil: "{count} matagumpay na download sa bawat rolling na 24 oras",
  fr: "{count} téléchargements réussis par période glissante de 24 heures",
  gu: "દરેક રોલિંગ 24 કલાકમાં {count} સફળ ડાઉનલોડ",
  he: "{count} הורדות מוצלחות בכל חלון מתגלגל של 24 שעות",
  hi: "हर रोलिंग 24 घंटे में {count} सफल डाउनलोड",
  hr: "{count} uspješna preuzimanja u svakom kliznom razdoblju od 24 sata",
  hu: "{count} sikeres letöltés minden gördülő 24 órában",
  id: "{count} unduhan berhasil per 24 jam bergulir",
  it: "{count} download riusciti per ogni periodo mobile di 24 ore",
  ja: "ローリング方式の24時間ごとに成功したダウンロード{count}件",
  kn: "ಪ್ರತಿ ರೋಲಿಂಗ್ 24 ಗಂಟೆಗಳಲ್ಲಿ {count} ಯಶಸ್ವಿ ಡೌನ್‌ಲೋಡ್‌ಗಳು",
  ko: "이동식 24시간마다 성공한 다운로드 {count}회",
  lt: "{count} sėkmingi atsisiuntimai per slenkantį 24 valandų laikotarpį",
  lv: "{count} veiksmīgas lejupielādes katrā slīdošajā 24 stundu periodā",
  ml: "ഓരോ റോളിംഗ് 24 മണിക്കൂറിലും {count} വിജയകരമായ ഡൗൺലോഡുകൾ",
  mr: "प्रत्येक रोलिंग 24 तासांत {count} यशस्वी डाउनलोड",
  ms: "{count} muat turun berjaya bagi setiap tempoh 24 jam bergerak",
  nl: "{count} geslaagde downloads per voortschrijdende 24 uur",
  no: "{count} vellykkede nedlastinger per rullerende 24 timer",
  pa: "ਹਰ ਰੋਲਿੰਗ 24 ਘੰਟਿਆਂ ਵਿੱਚ {count} ਸਫਲ ਡਾਊਨਲੋਡ",
  pl: "{count} udane pobrania w każdym ruchomym okresie 24 godzin",
  pt: "{count} downloads bem-sucedidos por cada período móvel de 24 horas",
  ro: "{count} descărcări reușite în fiecare interval glisant de 24 de ore",
  ru: "{count} успешные загрузки за каждые скользящие 24 часа",
  sk: "{count} úspešné stiahnutia za každých kĺzavých 24 hodín",
  sl: "{count} uspešni prenosi v vsakem drsečem obdobju 24 ur",
  sr: "{count} успешна преузимања у сваком клизном периоду од 24 сата",
  sv: "{count} lyckade nedladdningar per rullande 24 timmar",
  sw: "Vipakuliwa {count} vilivyofanikiwa kwa kila kipindi kinachosogea cha saa 24",
  ta: "ஒவ்வொரு நகரும் 24 மணி நேரத்திலும் {count} வெற்றிகரமான பதிவிறக்கங்கள்",
  te: "ప్రతి రోలింగ్ 24 గంటల్లో {count} విజయవంతమైన డౌన్‌లోడ్‌లు",
  th: "ดาวน์โหลดสำเร็จ {count} ครั้งต่อช่วงเวลา 24 ชั่วโมงแบบต่อเนื่อง",
  tr: "Her kayan 24 saat içinde {count} başarılı indirme",
  uk: "{count} успішні завантаження за кожні ковзні 24 години",
  ur: "ہر رولنگ 24 گھنٹوں میں {count} کامیاب ڈاؤن لوڈز",
  vi: "{count} lượt tải xuống thành công trong mỗi khoảng 24 giờ liên tục",
  zh: "每个滚动的24小时内可成功下载{count}次",
};

export const ROLLING_FREE = Object.fromEntries(
  Object.entries(ROLLING_WINDOW).map(([locale, claim]) => [
    locale,
    `${claim} (${FREE_MARKER[locale]})`,
  ]),
);

export function normalizeClaims(document, locale) {
  const proLimit = PRO_LIMIT[locale];
  const rolling = ROLLING_FREE[locale];
  if (!proLimit) throw new Error(`Missing localized Pro limit claim for ${locale}`);
  if (!rolling) throw new Error(`Missing localized rolling quota claim for ${locale}`);
  const quota = (count) => rolling.replace("{count}", count);
  if (document.app?.license) {
    document.app.license.status_free = `${quota("{limit}")}. ${proLimit}`;
  }
  if (document.app?.limit) {
    document.app.limit.body = `${quota("{limit}")}. ${proLimit} ({hours} h).`;
  }
  if (document.website?.pricing) {
    document.website.pricing.lead = `${quota("3")}. ${proLimit}`;
    document.website.pricing.feature_unlimited = proLimit;
  }
  if (document.website?.faq) {
    document.website.faq.q1_body = `${quota("3")}. ${proLimit}`;
  }
  return document;
}

export function normalizeAllClaims(roots = ROOTS) {
  let changed = 0;
  for (const root of roots) {
    for (const name of readdirSync(root).filter((entry) => entry.endsWith(".json"))) {
      const path = join(root, name);
      const before = readFileSync(path, "utf8");
      const document = normalizeClaims(JSON.parse(before), name.replace(/\.json$/, ""));
      const after = `${JSON.stringify(document, null, 2)}\n`;
      if (after !== before) {
        writeFileSync(path, after, "utf8");
        changed += 1;
      }
    }
  }
  return changed;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.stdout.write(`Normalized public claims in ${normalizeAllClaims()} locale file(s).\n`);
}
