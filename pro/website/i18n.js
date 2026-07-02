// Shared by index.html and success.html. Same string-lookup design as the
// Android app's static/index.html (see video_downloader/web/static/index.html)
// but persisted via localStorage instead of a server-side settings API, since
// this static site has no backend session of its own.
const LANGUAGES = [
  ['en', 'English'], ['de', 'Deutsch'], ['es', 'Español'], ['fr', 'Français'], ['pt', 'Português'],
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
const SUPPORTED_CODES = LANGUAGES.map((l) => l[0]);

// Stripe Checkout only localizes its own UI (payment form) in a subset of
// languages; anything else falls back to "auto" (Stripe then uses the
// buyer's browser locale itself, still a reasonable default).
const STRIPE_LOCALE_MAP = {
  de: 'de', es: 'es', fr: 'fr', pt: 'pt', it: 'it', nl: 'nl', pl: 'pl', ro: 'ro', el: 'el',
  cs: 'cs', sv: 'sv', da: 'da', fi: 'fi', no: 'nb', hu: 'hu', sk: 'sk', bg: 'bg', hr: 'hr',
  lt: 'lt', lv: 'lv', et: 'et', ru: 'ru', tr: 'tr', ja: 'ja', ko: 'ko', zh: 'zh', vi: 'vi',
  th: 'th', id: 'id', ms: 'ms', fil: 'fil', en: 'en',
};

let STRINGS = {};

function dtDetectLang() {
  const raw = (navigator.language || 'en').toLowerCase();
  const short = raw.split('-')[0];
  return SUPPORTED_CODES.includes(short) ? short : 'en';
}

function dtT(key, vars) {
  const parts = key.split('.');
  let node = STRINGS;
  for (const p of parts) node = node && typeof node === 'object' ? node[p] : undefined;
  let str = typeof node === 'string' ? node : key;
  if (vars) for (const [k, v] of Object.entries(vars)) str = str.split(`{${k}}`).join(v);
  return str;
}

async function dtLoadStrings(code) {
  try {
    const res = await fetch(`/i18n/${code}.json`, { cache: 'no-store' });
    if (!res.ok) throw new Error('not found');
    return await res.json();
  } catch (e) {
    return null;
  }
}

function dtApplyTranslations() {
  document.querySelectorAll('[data-i18n]').forEach((el) => { el.textContent = dtT(el.dataset.i18n); });
  document.querySelectorAll('[data-i18n-html]').forEach((el) => {
    // Only used for the one hero headline that legitimately needs an inline
    // <br/> and an emphasized word — every other string uses plain textContent.
    const emphasis = dtT('website.hero.title_emphasis');
    el.innerHTML = dtT(el.dataset.i18nHtml).split('{emphasis}').join(`<span>${emphasis}</span>`);
  });
  document.querySelectorAll('[data-i18n-attr]').forEach((el) => {
    const [attr, key] = el.dataset.i18nAttr.split(':');
    el.setAttribute(attr, dtT(key));
  });
  dtUpdateStripeLinks();
}

function dtUpdateStripeLinks() {
  const lang = localStorage.getItem('dt_lang') || 'auto';
  const effective = lang === 'auto' ? dtDetectLang() : lang;
  const stripeLocale = STRIPE_LOCALE_MAP[effective] || 'auto';
  document.querySelectorAll('a[data-stripe-link]').forEach((a) => {
    const base = a.dataset.stripeLink;
    a.href = `${base}?locale=${stripeLocale}`;
  });
}

async function dtSetLanguage(pref) {
  localStorage.setItem('dt_lang', pref);
  const effective = pref === 'auto' ? dtDetectLang() : pref;
  STRINGS = (await dtLoadStrings(effective)) || (await dtLoadStrings('en')) || {};
  dtApplyTranslations();
  document.querySelectorAll('.lang-switcher').forEach((sel) => { sel.value = pref; });
}

function dtPopulateLanguageSwitchers() {
  document.querySelectorAll('.lang-switcher').forEach((select) => {
    select.innerHTML = '';
    const autoOpt = document.createElement('option');
    autoOpt.value = 'auto';
    autoOpt.textContent = '🌐 Auto';
    select.appendChild(autoOpt);
    for (const [code, name] of LANGUAGES) {
      const opt = document.createElement('option');
      opt.value = code;
      opt.textContent = name;
      select.appendChild(opt);
    }
    select.addEventListener('change', (e) => dtSetLanguage(e.target.value));
  });
}

async function dtInitI18n() {
  dtPopulateLanguageSwitchers();
  const stored = localStorage.getItem('dt_lang') || 'auto';
  await dtSetLanguage(stored);
}
