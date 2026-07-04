// Language switcher for the static legal documents (impressum/datenschutz/agb).
// Unlike index.html/success.html (single file, translated in-place via i18n.js's
// JSON strings), these are long-form legal prose - each language is its own
// fully pre-translated, self-contained HTML file (<doc>.<lang>.html; the German
// original, the legally authoritative version, keeps the plain <doc>.html
// name with no suffix). This file just needs to know the language list and
// how to navigate between the sibling files - same LANGUAGES list as i18n.js,
// kept as a separate copy since these pages don't load the rest of i18n.js's
// (irrelevant here) JSON-string-translation machinery.
const LEGAL_LANGUAGES = [
  ['de', 'Deutsch'], ['en', 'English'], ['es', 'Español'], ['fr', 'Français'], ['pt', 'Português'],
  ['it', 'Italiano'], ['nl', 'Nederlands'], ['pl', 'Polski'], ['ro', 'Română'], ['el', 'Ελληνικά'],
  ['cs', 'Čeština'], ['sv', 'Svenska'], ['da', 'Dansk'], ['fi', 'Suomi'], ['no', 'Norsk'],
  ['hu', 'Magyar'], ['sk', 'Slovenčina'], ['bg', 'Български'], ['hr', 'Hrvatski'], ['lt', 'Lietuvių'],
  ['sl', 'Slovenščina'], ['et', 'Eesti'], ['lv', 'Latviešu'], ['sr', 'Српски'], ['uk', 'Українська'],
  ['ru', 'Русский'], ['tr', 'Türkçe'], ['ar', 'العربية'], ['he', 'עברית'], ['fa', 'فارسی'],
  ['ur', 'اردو'], ['hi', 'हिन्दी'], ['bn', 'বাংলা'], ['ta', 'தமிழ்'], ['te', 'తెలుగు'],
  ['mr', 'मराठी'], ['gu', 'ગુજરાતી'], ['kn', 'ಕನ್ನಡ'], ['ml', 'മലയാളം'], ['pa', 'ਪੰਜਾਬੀ'],
  ['ja', '日本語'], ['ko', '한국어'], ['zh', '中文'], ['vi', 'Tiếng Việt'], ['th', 'ไทย'],
  ['id', 'Bahasa Indonesia'], ['ms', 'Bahasa Melayu'], ['fil', 'Filipino'], ['sw', 'Kiswahili'], ['am', 'አማርኛ'],
];

(function () {
  const scriptTag = document.currentScript;
  const doc = scriptTag.dataset.doc; // "agb" | "datenschutz" | "impressum"
  const current = document.documentElement.lang || 'de';
  const container = document.getElementById('legal-lang-switcher');
  if (!container || !doc) return;

  const select = document.createElement('select');
  select.className = 'lang-switcher';
  select.setAttribute('aria-label', 'Language');
  for (const [code, name] of LEGAL_LANGUAGES) {
    const opt = document.createElement('option');
    opt.value = code;
    opt.textContent = name;
    if (code === current) opt.selected = true;
    select.appendChild(opt);
  }
  select.addEventListener('change', (e) => {
    const lang = e.target.value;
    location.href = lang === 'de' ? `${doc}.html` : `${doc}.${lang}.html`;
  });
  container.appendChild(select);
})();
