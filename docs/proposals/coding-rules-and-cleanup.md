# הצעה: כללי קוד וסידור, לפי redis-enterprise-services

**סטטוס:** עברנו על הנקודות. ההחלטות למטה, והן גוברות על מה שכתוב בהמשך המסמך. סעיף 3 (ניקיון ותלויות) עדיין פתוח.
**תאריך:** 2026-11-01

## החלטות הבעלים (2026-11-01)

| נושא | החלטה |
|---|---|
| סיסמה ב-DEBUG | נשארת, בכוונה |
| הערך החסום ב-`reason` | נשאר, בכוונה, כדי לא לעבור לרשת השנייה |
| תשובה בינארית, כותרת חסרה, אותיות גדולות בקונפיג, הפניות, `certifi` | תוקן |
| basedpyright strict, `ANN`, `import-linter`, `uv run --frozen`, `[dependency-groups]` | נוסף |
| `__init__.py` | נשארים בכל חבילה, ריקים. בלי `__all__` ובלי re-exports |
| שגיאות | קובץ אחד, `app/errors.py`. הקודים בקונפיג |
| YAML | לא |
| לוגים | דקורטורים, וקריאה ישירה כשצריך משהו מתוך הפונקציה |
| טסטים | unit בלבד, רק הלוגיקה של הפרויקט, בלי התנהגות של ספרייה ובלי סף כיסוי |
| מחלקות ו-`Protocol` | לא, נשארות פונקציות |
| טכנולוגיות נוספות | לא עכשיו. קודם משנים סכמה, ואת הלוגיקה רק אם אין ברירה |
| תשובות שאינן JSON | ממשיכות להידחות |
| שאריות Redis | נשארות עד שתתווסף טכנולוגיה |
| שם | `cluster-client` ו-`x-cluster-*` נשארים |
| Tracing | OpenTelemetry, בלי מטריקות. הייצוא ל-OTLP כבוי כברירת מחדל |

המסמך מרכז שלושה דברים:
1. הכללים שלפיהם נבנה `redis-enterprise-services`.
2. איפה הם סותרים את הכללים שכבר כתובים ב-`AGENTS.md` של הפרויקט הזה.
3. מה עוד כדאי לסדר כאן.

ההכרעה בכל סתירה היא שלך.

---

## 0. המטרה של הפרויקט (מהבעלים, 2026-11-01)

**השירות צריך להיות טיפש ככל האפשר**, כדי שאפשר יהיה להשתמש בו כמו שהוא גם בטכנולוגיות אחרות. לא רק ב-Redis
Enterprise, אלא גם, למשל:
- קלאסטר Mongo וכד', דרך קריאות ה-API שלו
- סתם `curl` דרך חומת האש

**הוחלט (מהבעלים, 2026-11-01):** קריאות API בלבד (HTTP). בלי קריאות TCP, לפחות כרגע.

**שאלות לדיון, שנובעות מהמטרה הזו:**
- **בדיקת התשובה מול JSON Schema:** היא קיימת כדי שהתשובה תעבור את חומת האש. אבל היא מניחה שהתשובה היא JSON.
  השאלה: האם הבדיקה הזו היא חלק מהשירות הבסיסי, או שכבה אופציונלית לפי הגדרה? למשל schema לכל יעד, או בלי
  schema בכלל.
- **שמות שקשורים ל-Redis Enterprise:** בקוד ובקונפיג יש שמות כמו `cluster`, `x-cluster-*` ו-"Redis Enterprise
  REST API", ובכותרות שעוברות הלאה יש `cluster-state-id` ו-`x-task-id`. שירות כללי צריך שמות כלליים, וקונפיג לכל
  יעד.
- **שלושה שמות לאותו פרויקט:**
  - התיקייה: `cluster-relay`
  - ה-repo ב-GitHub וה-package: `cluster-client`
  - ה-prefix של ה-env: `CLUSTER_CLIENT_`

  כדאי לבחור שם אחד, וכדאי שיהיה כללי.

---

## 1. הכללים של redis-enterprise-services

### מבנה וארכיטקטורה
- **OOP ו-SOLID:** הזרקת תלויות (DI) בבנאי, ותלות בממשק (`Protocol`), לא במחלקה. רק נקודת ההרכבה
  (composition root, ה-`app`) בונה מחלקות קונקרטיות.
- **קבצים קטנים:** קובץ אחד לכל מושג. פונקציות ומחלקות קטנות, עם תפקיד אחד.
- **שכבות שנאכפות בכלי:** `import-linter` רץ ב-pre-commit.
  - כל חבילה ברמה העליונה חייבת להופיע ברשימת השכבות (`exhaustive = true`). חבילה חדשה נכשלת עד שנותנים לה מקום.
  - חבילות באותה רמה, שמחוברות ב-`|`, לא מייבאות זו מזו.
  - יש גם כללי `forbidden`. למשל: "מעל ה-API של הקלאסטר אף אחד לא מייבא את ה-transport".
- **בלי `__init__.py` בכלל.** כל import הוא ישיר, מהמודול שמגדיר את השם. אין re-exports.
- **תיקייה עם יותר מ-10 קבצים** מתפצלת לתת-חבילות לפי נושא.
- **אבני לגו:** כל חלק עצמאי וניתן לשימוש חוזר, ולא נעול בתוך flow אחד.

### קוד
- **ארגומנטים keyword-only:** `*` בכל חתימה, וכל קריאה עם שמות, כולל קריאות לספריות כשאפשר. רק חתימות שהפריימוורק
  קובע נשארות פוזיציונליות.
- **טיפוסים מלאים** על הכל, כולל משתנים מקומיים. תחביר מודרני: `list[str]`, `X | None`.
- **בדיקת טיפוסים:** `basedpyright` במצב `strict`, עם `reportUnnecessaryTypeIgnoreComment = "error"`. רץ
  ב-pre-commit.
- **Pydantic v2 לכל מבנה נתונים:** `model_config = ConfigDict(...)`, ו-`Field()` לברירות מחדל ולוולידציה. בלי
  dataclasses.
- **בלי הערות בקוד.** שמות ברורים מחליפים הערות. docstrings רק ל-API ציבורי של ספרייה.
- **בלי ערכים בקוד:** כל ערך מגיע מ-`config/*.yaml` דרך Pydantic Settings. הקונפיג מפוצל לקובץ YAML לכל נושא, וכל
  קובץ מתאים למודול settings משלו. סודות מגיעים רק מ-env או מ-Secret.
- **שגיאות:**
  - היררכיה של exceptions משלנו, בתיקייה `exceptions/`. לכל שגיאה יש `code` ו-`status_code`.
  - אסור `except:` ואסור `except Exception:` בלי טיפול מוגדר.
- **לוגים:** `logger = logging.getLogger(name=__name__)` בכל מודול, וקריאה מפורשת ברמה המתאימה, בכל חמש הרמות.
  ההגדרה של ה-handlers וה-formatters מגיעה כולה מהקונפיג.
- **Tracing:** OpenTelemetry. ה-`traceparent` ממשיך מבקשה לבקשה, והספריות `FastAPI` ו-`requests` מקבלות
  instrumentation. ה-OTLP exporter מוגדר בקונפיג.

### טסטים
- **מעט טסטים, unit בלבד, רק על הלוגיקה המרכזית.** בלי טסטים על קוד שרק מחבר חלקים.
- **אף פעם לא בודקים התנהגות של ספרייה** (Pydantic, פרסור של env, logging).
- **כל טסט בודק התנהגות אחת.**
- **כל טסט נבדק בבאג שנשתל:** משנים את הקוד ומוודאים שהטסט נכשל. לפני ההרצה מנקים את `__pycache__`.
- **בדיקה מול המערכת האמיתית:** כל חלק נבדק גם מול הקלאסטרים האמיתיים בסביבה המקומית, וכל בקשה ותשובה נשמרות
  (`docs/reference/cluster-samples`, תיקייה שלא נכנסת ל-git).
- הכלל הזה גובר על כלל שלוש השכבות (unit, integration, E2E) ועל סף הכיסוי, שמופיעים בהנחיות הכלליות.

### כלים (מהקבצים של redis-enterprise-services)

`pyproject.toml`:

```toml
[tool.ruff]
line-length = 110
target-version = "py314"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP", "B", "SIM", "RUF", "BLE", "S", "ANN"]

[tool.basedpyright]
include = ["src", "tests"]
typeCheckingMode = "strict"
reportUnnecessaryTypeIgnoreComment = "error"

[[tool.importlinter.contracts]]
type = "layers"
containers = ["<package>"]
exhaustive = true
layers = ["app", "api", "...", "config | exceptions"]
```

`.pre-commit-config.yaml`:
- כל ה-hooks רצים דרך `uv run --frozen`, לא דרך `.venv/bin`.
- הסדר: `ruff check --fix`, `ruff format`, `basedpyright`, `lint-imports`.

### תהליך עבודה
- **ענפים:** `main` הוא הגרסה השלמה, ו-`dev` הוא העבודה השוטפת. לכל שינוי יש ענף קטן מ-`dev`, עם prefix:
  `feature/`, `bugfix/`, `refactor/` או `hotfix/`. ה-commits לפי Conventional Commits.
- **PR לכל שינוי, ו-CR על GitHub:**
  - סוכן חדש כותב review אחד עם הערות inline.
  - מתקנים, משיבים על כל הערה, ומריצים CR נקי חדש אחרי כל תיקון קוד.
  - הבעלים ממזג, ורק באישור.
- **צעד אחד בכל פקודה:** תשובות ב-GitHub, מיזוג, pull, מחיקת ענף ופתיחת ענף חדש, כל אחד בנפרד.
- **בונים בחלקים קטנים.** כל חלק מקבל PR משלו.
- **החלטות של הבעלים:** לא ממציאים עובדות. מה שהוא החלטה של הבעלים, שואלים.

---

## 2. סתירות מול `AGENTS.md` הנוכחי

| נושא | redis-enterprise-services | cluster-relay היום (`AGENTS.md`) | לדיון |
|---|---|---|---|
| מבנה | מחלקות, Protocols, DI, שכבות | "Functions, not classes… no protocols/interfaces with one implementation, no extra layers" (כלל 7) | המטרה "טיפש ככל האפשר" עשויה להצדיק פשטות. מצד שני, שימוש חוזר ביעדים שונים (Redis Enterprise, Mongo, curl) הוא בדיוק המקום שבו ממשק עם כמה מימושים מועיל |
| `__init__.py` | אין בכלל | `app/__init__.py`, `app/config/__init__.py` עם `__all__` ו-re-exports, ו-`__init__.py` בכל תיקיית טסטים | |
| לוגים | קריאה מפורשת ל-`logger` | `@log_debug` על כל פונקציה, ו-`@log_info` בצעדים מרכזיים (כלל 4) | |
| טסטים | מעט, unit בלבד | unit, integration ו-e2e, וסף כיסוי של 80% | |
| בדיקת טיפוסים | basedpyright strict | אין | |
| שכבות | import-linter | אין | |
| pre-commit | `uv run --frozen`, 4 hooks | `.venv/bin/ruff`, 2 hooks | |
| ruff | כולל `ANN` | כולל `PT`, בלי `ANN` | |
| Git | `dev`, ענפים, PR, CR | "single branch `main`", ו"never commit unless asked" | |
| מודלים | `ConfigDict` ו-`Field` | `FrozenModel` בסיסי משותף | אפשר לשלב |

---

## 3. מה עוד לסדר כאן

**Tracing ב-OpenTelemetry:** בוצע (`app/telemetry.py`). בתשובה חוזרת עכשיו הכותרת `traceresponse` במקום `traceparent`.

**ניקיון:**
- `_to_delete/cluster-relay.tgz`: למחוק (בהחלטה שלך).
- `logs/`, `.coverage`, `.pytest_cache`, `.ruff_cache`: מקומיים בלבד, וכולם כבר ב-`.gitignore`.
- `CONVERSATION.md`: ב-`.gitignore`. האם הוא עדיין נחוץ?
- `CLAUDE.md` מפנה ל-`AGENTS.md` בלבד. אחרי הדיון כדאי שהכללים שיוחלטו ייכתבו שם, במקום אחד.
- הענף `feature/cleanlog-standalone` (commit אחד: "cleanlog standalone logger"): למזג או למחוק?

**תלויות:** ב-`pyproject.toml` יש רק גבולות תחתונים ישנים, למשל `fastapi>=0.110` ו-`pydantic>=2.6`. כדאי לעדכן אותם
לגרסאות שבשימוש בפועל (ב-`uv.lock`), ולהוסיף בדיקת חולשות בתלויות.

**פתוחים מ-`AGENTS.md`:**
- `/health/ready` צריך לבדוק משהו אמיתי.
- האם השירות מחזיק רשימת קלאסטרים ופרטי גישה (`docs/proposals/cluster-health-check.md`). זה תלוי גם בשאלת
  "הטיפשות" מסעיף 0.
- הצורה הסופית של גוף התשובה בדחייה.

**החוזה מול redis-enterprise-services:** `docs/contracts/edge-service.md` ב-redis-enterprise-services מתאר את
הממשק מול השירות הזה: הכותרות `x-cluster-*`, `x-edge-error` ו-`x-edge-cluster-status`, והסיווג של כל תשובה. כל שינוי
בשמות או בהתנהגות כאן חייב להתעדכן גם שם.
