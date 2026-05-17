import { createI18n } from "vue-i18n/dist/vue-i18n.esm-browser.prod.js";
import en from "./lang/en.json";

const languageList = {
    "ru-RU": "Русский",
    "ka": "Georgian",
};

let messages = {
    en,
};

for (let lang in languageList) {
    messages[lang] = {
        languageName: languageList[lang]
    };
}

const rtlLangs = [ "he-IL", "fa", "ar-SY", "ur" ];

/**
 * Find the best matching locale to display
 * If no locale can be matched, the default is "en"
 * @returns {string} the locale that should be displayed
 */
export function currentLocale() {
    for (const locale of [ localStorage.locale, navigator.language, ...navigator.languages ]) {
        // localstorage might not have a value or there might not be a language in `navigator.language`
        if (!locale) {
            continue;
        }
        if (locale in messages) {
            return locale;
        }
        // some locales are further specified such as "en-US".
        // If we only have a generic locale for this, we can use it too
        const genericLocale = locale.split("-")[0];
        if (genericLocale in messages) {
            return genericLocale;
        }
    }
    return "en";
}

export const localeDirection = () => {
    return rtlLangs.includes(currentLocale()) ? "rtl" : "ltr";
};

export const i18n = createI18n({
    locale: currentLocale(),
    fallbackLocale: "en",
    silentFallbackWarn: true,
    silentTranslationWarn: true,
    messages: messages,
});
