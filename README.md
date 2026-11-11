<div align="center">

# ⚽ MASARAT | مسارات

### منصة ذكية متعددة الوكلاء لتنسيق رحلات مشجعي كرة القدم

من المباراة إلى المدرج، يجمع مسارات تفاصيل الرحلة وخياراتها في خطة واحدة تساعد المشجع على الاستعداد ليوم المباراة.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Multi-Agent](https://img.shields.io/badge/System-Multi--Agent-7C4DFF)
![FIPA-ACL](https://img.shields.io/badge/Communication-FIPA--ACL-00A884)
![GitHub Pages](https://img.shields.io/badge/Frontend-GitHub%20Pages-222222)
![Render](https://img.shields.io/badge/API-Render-46E3B7)

[جرّب الديمو](https://shahadmaalanazi.github.io/Masarat/) · [English](#english)

</div>

---

## 📖 نبذة عن المشروع

**مسارات (MASARAT)** هو نموذج تفاعلي يوضح كيف يمكن لوكلاء ذكاء اصطناعي متخصصين التعاون لتنسيق رحلة مشجع إلى مباراة كرة قدم. يختار المستخدم مدينة الانطلاق والمباراة والميزانية، ثم يتبادل الوكلاء الطلبات والنتائج ليعرضوا خيارات المباراة والسفر والإقامة ضمن خطة واحدة.

يعرض الديمو خطوات التنسيق ورسائل الوكلاء وقرار المنسّق، ليُظهر آلية عمل نظام متعدد الوكلاء بدل الاكتفاء بعرض نتيجة ثابتة.


## ✨ المميزات

- 🤝 تعاون خمسة وكلاء متخصصين عبر المنسّق
- 💬 عرض رسائل التواصل وفق FIPA-ACL أثناء تنفيذ الطلب
- 🧭 مشاهدة تسلسل تنفيذ الوكلاء ونتائج كل خطوة
- ⚽ عرض معلومات المباراة والملعب والتذكرة التقديرية
- ✈️ مقارنة خيارات النقل، مع مراعاة عدم الحاجة للسفر بين المدن عند تطابق مدينة الانطلاق والمباراة
- 🏨 عرض خيارات الإقامة وأسمائها عند توفرها في مخزون الديمو
- 💰 جمع التكلفة التقديرية ومراجعة الخطة حسب الميزانية
- 🔁 طلب خيارات بديلة للسفر أو الإقامة ومشاهدة أثر الاختيار على الخطة
- 🌐 واجهة بالعربية والإنجليزية

## 🤖 الوكلاء

| الوكيل | المهمة |
| --- | --- |
| **Fan Agent** · وكيل المشجع | يستقبل المدينة والمباراة والميزانية والأولوية. |
| **Coordinator Agent** · المنسّق | يوزع الطلبات، يجمع العروض، ويراجع الخطة والميزانية. |
| **Venue Agent** · وكيل المباراة | يعيد معلومات المباراة والملعب وتقدير التذكرة. |
| **Travel Agent** · وكيل السفر | يبحث في خيارات النقل المتاحة في بيانات الديمو. |
| **Accommodation Agent** · وكيل الإقامة | يبحث في خيارات السكن المتاحة في بيانات الديمو. |

## 🔄 آلية العمل

```text
تفضيلات المشجع
      ↓
Coordinator Agent ── REQUEST ──→ وكلاء المباراة والسفر والإقامة
      ↑                              │
      └──── INFORM / PROPOSE ────────┘
      ↓
مراجعة الخيارات والميزانية
      ↓
خطة رحلة واضحة مع التكلفة التقديرية
```

## 🛠 التقنيات المستخدمة

### الواجهة الأمامية

- HTML, CSS, JavaScript
- نشر الواجهة الثابتة عبر GitHub Pages

### الخادم والوكلاء

- Python 3.11
- وكلاء المشروع وطبقة الرسائل ACL
- HTTP API مبني على مكتبات Python القياسية
- تكامل Google Gemini عبر `langchain-google-genai` عند تهيئة المفتاح
- خيارات احتياطية تعتمد على بيانات الديمو عند عدم توفر التكامل الاختياري

## 🏗 معمارية النظام

```text
واجهة المشجع (GitHub Pages)
          │
          │ HTTP: /api/matches · /api/coordinate
          ▼
خادم الديمو (Render)
          │
          ▼
Coordinator Agent
   ┌──────┼──────────┐
   ▼      ▼          ▼
Venue   Travel   Accommodation
 Agent   Agent      Agent
   └──────┼──────────┘
          ▼
  مراجعة الخيارات والميزانية
          │
          ▼
     الخطة والرسائل
```

## 📂 هيكل المشروع

```text
Masaraat/
├── site/                       # واجهة GitHub Pages والملفات الثابتة
├── .github/workflows/pages.yml # نشر الموقع تلقائيًا
├── *_agent.py                  # الوكلاء والمنسّق
├── acl.py                      # الرسائل بين الوكلاء
├── web_demo_server.py          # واجهة API للديمو
├── venue_data.py               # بيانات جدول المباريات
├── real_data.py                # بيانات خيارات الديمو
├── deploy_demo.py              # تشغيل خادم الديمو وتهيئة مخزون تجريبي
├── run_demo.py                 # مثال تشغيل التنسيق من سطر الأوامر
├── render.yaml                 # إعداد نشر الخادم على Render
└── requirements.txt            # اعتماديات Python
```

## 🚀 تشغيل مثال الوكلاء محليًا

يتطلب Python 3.11 أو أحدث:

```bash
git clone https://github.com/shahadmaalanazi/Masarat.git
cd Masaraat
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
python run_demo.py
```

لتشغيل خادم API المحلي بدل المثال من سطر الأوامر:

```bash
python deploy_demo.py
```

سيبدأ الخادم على `http://localhost:8765` افتراضيًا. تُضبط المنفذ وعنوان الواجهة المسموح بها عبر متغيري البيئة `PORT` و`CORS_ORIGINS`.

## 🌐 النشر

### GitHub Pages

ينشر سير العمل `.github/workflows/pages.yml` محتويات مجلد `site/` عند الدفع إلى فرع `main`. اختر **GitHub Actions** كمصدر النشر من إعدادات Pages في المستودع.

### Render

يعرّف `render.yaml` خدمة الويب وفحص الصحة `/api/health`. اربط Render بالمستودع وأضف الإعدادات المطلوبة من لوحة الخدمة. تفاصيل النشر موجودة في [DEPLOY.md](DEPLOY.md).

## 🔐 حماية مفاتيح API

- خزّن `GOOGLE_API_KEY` في إعدادات Environment لخدمة Render فقط عند الحاجة إلى Gemini.
- لا تضف أي مفتاح في ملفات الواجهة أو GitHub Actions أو هذا المستودع.
- إذا سبق رفع مفتاح إلى GitHub، أبطله وأنشئ مفتاحًا بديلًا؛ حذفه من آخر نسخة لا يزيله من سجل Git.

---

<a id="english"></a>

## English

**MASARAT** is a bilingual multi-agent prototype for coordinating football fans' trips. Enter a departure city, match, and budget; five specialized agents collaborate through a coordinator to assemble match, travel, and stay options into one estimated plan.

The demo shows the execution timeline, FIPA-ACL messages, coordinator decisions, and alternative-offer flow. The included match schedule is historical project data. Travel, accommodation, and some ticket prices are simulated; the app does not make bookings.

### Agents

- **Fan Agent:** captures the request and preferences.
- **Coordinator Agent:** delegates requests, compares offers, and reviews the budget.
- **Venue Agent:** provides match, stadium, and estimated ticket information.
- **Travel Agent:** searches the demo transport inventory.
- **Accommodation Agent:** searches the demo stay inventory.

### Run locally

Requires Python 3.11 or later:

```bash
git clone https://github.com/shahadmaalanazi/Masaraat.git
cd Masaraat
python -m venv .venv
# Activate .venv for your operating system
pip install -r requirements.txt
python run_demo.py
```

Run the local API with `python deploy_demo.py` (default: `http://localhost:8765`). The public frontend is hosted on [GitHub Pages](https://shahadmaalanazi.github.io/Masarat/); deployment details are in [DEPLOY.md](DEPLOY.md).

Store `GOOGLE_API_KEY` in Render's environment settings. Never commit API keys or place them in frontend files.
