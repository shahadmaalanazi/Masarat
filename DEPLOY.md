# نشر ديمو مسارات

الواجهة ثابتة وتُنشر عبر GitHub Pages. خادم Python ينشر كخدمة ويب على Render، لأن Pages لا يشغّل Python.

## قبل الرفع إلى GitHub

1. أنشئ مستودعًا جديدًا، ثم أضف الملفات من هذا المجلد.
2. لا ترفع `.env` أو `.venv` أو أي ملف يحتوي مفتاحًا. ملف `.gitignore` يستبعد هذه الملفات مستقبلًا.
3. فعّل GitHub Pages من إعدادات المستودع واختر **GitHub Actions** كمصدر النشر.

## نشر خادم الوكلاء

1. أنشئ Web Service جديدًا في Render واربطه بالمستودع؛ سيقرأ إعداداته من `render.yaml`.
2. أضف `GOOGLE_API_KEY` من صفحة Environment في Render فقط. لا تضفه في GitHub Actions ولا في ملفات الموقع.
3. بعد إنشاء الخدمة، انسخ عنوانها إلى `site/config.js` مكان `https://SET-YOUR-RENDER-SERVICE.onrender.com`.
4. ضع عنوان GitHub Pages الخاص بالمستودع في `render.yaml` مكان `https://SET-YOUR-GITHUB-USERNAME.github.io` ضمن `CORS_ORIGINS`، ثم ادفع التعديل.

## نشر الواجهة

ارفع التعديلات إلى فرع `main`. سير العمل `.github/workflows/pages.yml` ينشر محتوى `site/` تلقائيًا. عنوان Pages يظهر في إعدادات Pages أو سجل GitHub Actions.

الخادم يحد الطلبات إلى 12 طلبًا في الدقيقة لكل عنوان IP كحماية أساسية لديمو عام. النتائج تظل محاكاة ولا تنفذ حجوزات.
