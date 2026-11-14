# הצעה: חוזה גוף השגיאה של cluster-client

**סטטוס:** לביצוע. ההוראות מיועדות לסוכן שיתקן את הקוד.
**תאריך:** 2026-11-13
**מקור:** בדיקת e2e מלאה (service → DataPower stand-in → cluster-client → Redis Enterprise 8.2.0-25), ב-redis-enterprise-services.

קרא קודם את `AGENTS.md`. כללי הקוד, הטסטים וה-commits שלו חלים גם כאן.

## למה

1. **תשובת שגיאה של cluster-client נחסמת ב-DataPower.** DataPower לא מבין תוכן ולא מסתכל על סטטוס. הוא בודק
   **כל** גוף מול סכמת התשובות: גוף שעומד בסכמה עובר, וגוף שלא עומד בה נחסם. בסכמה שנמסרה לחברה
   (`response-schema-depth.json` ב-redis-enterprise-services, `docs/reference/firewall-schemas/`) מחרוזת ברמה 2
   וברמה 3 מוגבלת ל-512 תווים, ומחרוזת ברמה 4 ל-256. היום `reason` הוא `error.message` של jsonschema, ובכשל של
   `anyOf` הוא מכיל את **כל** הגוף שנבדק, אלפי תווים. לכן הוא נחסם, והמנהל (service) מקבל חסימה של DataPower במקום
   את ההסבר. גם `invalid_request` של היום (`{"detail": [{"loc": ..., "msg": ...}]}`) שם מחרוזות ברמה 4.
2. **סיסמאות דולפות.** אותו `error.message` מכיל את ה-bdb המלא, כולל `authentication_admin_pass` ו-
   `authentication_redis_pass`. משם הוא עובר לתשובה, ללוג של המנהל ול-Redis של המנהל.
3. **בכוונה, ההסבר נשאר בתשובה** (החלטת הבעלים מ-2026-11-01: "הערך החסום ב-`reason` נשאר, כדי לא לעבור לרשת
   השנייה"). לכן לא מוחקים את ההסבר. מעבירים אותו בצורה שעוברת את הסכמה, ומסירים ממנו רק את הסיסמאות הידועות.

## ההחלטה ב-AGENTS.md שמוחלפת

השורה הזו ב-`AGENTS.md` (בפרק "Decisions that look odd but are deliberate") **מוחלפת**:

> **The rejection `reason` keeps the blocked value**, as jsonschema wrote it, even a password, in the answer to
> the manager and in the failure file.

- **מה מחליף אותה:** בתשובה ובקובץ הכשלים מוסרים רק השדות שרשומים ב-`redacted_fields`. כל השאר עובר במלואו.
- **איפה נשמר המקור:** ה-`error.message` המקורי המלא, כולל הסיסמה, נרשם בלוג DEBUG. כך תמיד יש מקום אחד עם
  השגיאה המלאה.
- **למה:** מגבלת 512 התווים של DataPower, והחלטת הבעלים מ-2026-11-13.

## עיקרון-על: קודם המידע, ורק אחר כך האבטחה

**החלטת הבעלים (2026-11-13), בצורה קיצונית:** הדבר הכי חשוב הוא שההסבר יגיע במלואו לצד השני. אבטחה באה
רק אחרי זה.

- **מה שצפינו אפשר למחוק.** הכוונה רק לנתיבים שרשומים ב-`redacted_fields`. אלה סיסמאות ידועות, ומוחקים אותן בדיוק
  לפי הרשימה, לא יותר.
- **מה שלא צפינו עובר במלואו, גם אם יש בו סיסמה.** אין ניחושים של "נראה כמו סוד", אין סינון לפי מילים ואין
  קיצור "ליתר ביטחון".
- **אין fallback כללי.** לא עוטפים את בניית ההסבר ב-`except Exception`. תופסים רק חריגה ספציפית שבאמת יכולה
  לקרות, בשמה. בדיקה של הקוד הנוכחי: `remove_fields` רץ על JSON שכבר פוענח, עם נתיבים שכבר נבדקו בהפעלה, ולא
  זורק. לכן בבניית ההסבר אין היום שום `try`.
- **המגבלה היחידה שמותר לה לקצר מידע היא הסכמה עצמה** (ראה "חיתוך" למטה).
- **`internal_error` מעביר את כל מה שיש.** סוג החריגה, `str(error)` וה-traceback, מחולקים לחלקים. היום הוא מעביר רק
  את שם הסוג, וזה איבוד מידע.

## החוזה החדש

**כלל-על:** כל גוף ש-cluster-client בונה בעצמו, כלומר כל תשובה עם `x-edge-error`, חייב לעמוד ב-
`response-schema-depth.json`. זה כולל `response_rejected`, `connection_failed`, `timeout`, `invalid_request` ו-
`internal_error`. גוף של הקלאסטר עצמו ממשיך לעבור כמו שהוא, byte for byte.

```json
{
  "error": "response_rejected",
  "rule": "anyOf",
  "field": "$.shard_list",
  "reason": ["...עד 512 תווים...", "...המשך..."]
}
```

| שדה | תוכן | מגבלה |
|---|---|---|
| `error` | הקוד מהקונפיג, כמו היום | קצר |
| `rule` | ה-keyword של jsonschema שנכשל (`error.validator`: `type`, `maxLength`, `anyOf`...). רק ב-`response_rejected`. ב-JSON לא תקין: הערך מהקונפיג (`not_json_rule`, ברירת מחדל `not_json`) | קצר |
| `field` | `error.json_path`, כמו היום | עד 512 תווים, ראה "חיתוך" |
| `reason` | **רשימה** של חלקים, כל אחד עד 512 תווים, שמחוברים יחד הם ההסבר המלא | עד 500 חלקים, ראה "חיתוך" |

למה רשימה: הרשימה `reason` היא ערך ברמה 2 (עד 500 פריטים), וכל חלק בה הוא מחרוזת ברמה 3 (עד 512 תווים), כלומר עד
כ-256KB. זה מספיק לכל `error.message` שראינו. את זה צריך לאמת בטסט מול הסכמה עצמה, ולא להסתמך על המספרים כאן.

## חיתוך

- **`reason`:** כל חלק הוא עד `part_length` (512) תווים. אם הטקסט נכנס ב-`max_parts` (500) חלקים, הוא נשלח כולו.
  אחרת חלקים 1 עד 499 הם תוכן, וחלק 500 **בא במקום תוכן** ואומר כמה תווים לא נשלחו. נוסח ההודעה בקונפיג, עם מקום
  למספר.
- **`field`:** אם הוא ארוך מ-`part_length`, הוא נחתך מההתחלה ומקבל `...` בתחילתו, כדי שהסוף (השדה עצמו) יישאר.
  ה-`...` **נספר בתוך** 512 התווים: התוצאה היא בדיוק 512 תווים.

## בלי סודות: בונים את ההסבר מעותק מנוקה

- `rules.redacted_fields` כבר קיים ומשמש את לוג הכשלים. הוא רשימת הנתיבים של הסיסמאות.
- ההחלטה אם התשובה נדחית ממשיכה להיות על הגוף האמיתי. הכשל המקורי (`best_match` על הגוף האמיתי) הוא הכשל
  שגרם לחסימה.
- **`rule` ו-`field` נלקחים תמיד מהכשל המקורי.**
- **`reason`:** מסירים את `redacted_fields` מעותק של הגוף ומאמתים את העותק שוב.
  - אם בעותק יש כשל **באותו `json_path`** של הכשל המקורי (מבין כל הכשלים של העותק, `best_match` על אלה שה-
    `json_path` שלהם זהה): `reason` הוא ה-`message` של הכשל הזה. אין בו סיסמאות, כי הן הוסרו.
  - אחרת (למשל הכשל היה בשדה סיסמה עצמו, או שבעותק אין כשל באותו נתיב): `reason` הוא ההודעה של שדה מוסתר
    מהקונפיג (`redacted_reason`, ברירת מחדל `the failing value is a redacted field`), בלי הערך.
- **המקור המלא נרשם ב-DEBUG:** `validate_body` רושם ב-DEBUG את ה-`error.message` המקורי של הכשל המקורי. זו קריאת לוג
  ידנית שמותרת לפי כלל 4 (ההודעה צריכה נתון מתוך הפונקציה). צריך לעדכן בכלל 4 ב-`AGENTS.md` את "(only the failure
  WARNING does this)".
- **לוג הכשלים שומר את השגיאה כולה, בלי חיתוך** (`record_failure`), ו-`cluster_response` ממשיך להיות מנוקה כמו היום.

**כלל (החלטת הבעלים מ-2026-11-14):** כל כשל שהשירות עונה עליו בעצמו נכתב ללוג הכשלים ב-WARNING או ב-ERROR, עם
`reason` ו-`field` מלאים, ולא רק ב-DEBUG. רק התשובה נחתכת למגבלות ה-firewall. זה כולל גם את `invalid_request` ואת
`internal_error`.

## שאר הכשלים

| כשל | היום | אחרי |
|---|---|---|
| `connection_failed` / `timeout` | `reason` = `cannot reach {url}: {str(error)}`, ועלול לעבור 512 | אותו טקסט, מחולק לחלקים ב-`reason` |
| `response_rejected` על JSON לא תקין | `the response body is not JSON: {error}` | `rule` = `not_json_rule` מהקונפיג, `field: "$"`, ו-`reason` מחולק לחלקים |
| `internal_error` | `reason` = שם סוג החריגה, ובלוג הכשלים רק שם הסוג | `reason` = סוג החריגה, `str(error)` וה-traceback, מחולקים לחלקים. בתשובה מחולק לחלקים, ובלוג הכשלים במלואו |
| `invalid_request` | `{"detail": error.detail}` | `FailureBody` כמו כל השאר: `error`, ו-`reason` מחולק לחלקים מ-`str(error.detail)` |

## מה לשנות בקוד

1. `app/models.py`: ‏`FailureBody` מקבל את השדות `error`, ‏`rule: str | None`, ‏`field: str | None` ו-
   `reason: list[str]`. ‏`FailureDetails` מחזיק את אותם שדות במלואם (`reason: str`), ו-`RequestFailure` (רשומת
   הלוג) יורש ממנו.
2. `app/config/failures.py`: ‏`FailureSettings` מקבל את `part_length` (512), ‏`max_parts` (500), ‏`not_json_rule`
   (`not_json`), ‏`redacted_reason` (`the failing value is a redacted field`), נוסח ההודעה על תווים שלא נשלחו ואת
   הקידומת של `field` חתוך (`...`). בלי ערכים קבועים בקוד: המגבלות תלויות בסכמה שנמסרה לחברה.
3. מודול חדש לחלוקה, למשל `app/failures/reason_parts.py`: פונקציה שמקבלת טקסט ומחזירה רשימת חלקים לפי הקונפיג,
   ופונקציה לקיצור `field`.
4. `app/errors.py`: ‏`RequestFailedError` מקבל `rule` בנוסף ל-`reason` ול-`field`.
5. `app/schema.py`: ‏`validate_body` מקבל גם את `redacted_fields` ואת ההודעה של שדה מוסתר, בונה את ההסבר מהעותק
   המנוקה כמו שמתואר למעלה, ורושם ב-DEBUG את ה-`error.message` המקורי. ‏`best_match` נשאר.
6. `app/response_builder.py`: מעביר את `rules.redacted_fields` ל-`validate_body`, ומשתמש ב-`not_json_rule` ב-JSON
   לא תקין.
7. `app/failures/response.py` ו-`app/failures/log.py`: ‏`failure_details` בונה את השגיאה המלאה. רשומת הלוג
   משתמשת בה כמו שהיא, ו-`failure_body` חותך ממנה את התשובה.
8. `app/failures/handlers.py`: גם `refused_request_response` וגם `internal_error_response` מחזירים `FailureBody`.
   שניהם כותבים ללוג הכשלים את השגיאה המלאה: `invalid_request` ב-WARNING, `internal_error` ב-ERROR.
9. `AGENTS.md`: מחליפים את השורה שמופיעה בפרק "ההחלטה ב-AGENTS.md שמוחלפת", מעדכנים את כלל 4 ואת תיאור החוזה.
   `README.md`: מתעדים את החוזה החדש ואת הכלל שכל גוף של cluster-client עובר את הסכמה.
10. **דיאגרמות** (`docs/diagrams/`): מעדכנים באותה משימה.

## טסטים (מעטים, על הלוגיקה בלבד, טענה אחת בכל טסט)

1. גוף bdb עם `authentication_admin_pass: "TOPSECRET"` שנכשל בסכמה: `TOPSECRET` לא מופיע בגוף התשובה.
2. אותו גוף: `TOPSECRET` לא מופיע ברשומת הלוג.
3. כשל שה-`error.message` שלו ארוך מ-512 תווים: כל חלק ב-`reason` הוא עד 512 תווים.
4. אותו כשל: חיבור החלקים שווה להסבר המנוקה.
5. טקסט ארוך מ-500 חלקים: יש בדיוק 500 חלקים.
6. אותו טקסט: החלק האחרון אומר כמה תווים לא נשלחו.
7. **כל** גוף שגיאה ש-cluster-client בונה עובר אימות מול `response-schema-depth.json`. טסט אחד עם parametrize על
   rejection, not JSON, connection failed, timeout, invalid request ו-internal error. העתק את הסכמה ל-
   `tests/support/` כקובץ קבוע.
8. `field` ארוך מ-512 תווים: אורכו 512 בדיוק.
9. אותו `field`: הוא נגמר בסוף הנתיב המקורי.
10. כשל בשדה סיסמה עצמו: `field` הוא הנתיב של שדה הסיסמה.
11. אותו כשל: `rule` הוא ה-keyword של הכשל המקורי.
12. אותו כשל: `reason` הוא ההודעה של שדה מוסתר מהקונפיג.
13. שני כשלים, אחד בשדה סיסמה ש-`best_match` בוחר ואחד בשדה אחר: `field` הוא שדה הסיסמה (הכשל המקורי).
14. סוד שלא רשום ב-`redacted_fields` (למשל שדה סיסמה חדש שלא הכרנו): הוא **כן** מופיע בהסבר. זו התנהגות מכוונת.
15. `internal_error`: הגוף מכיל את `str(error)`.
16. `internal_error`: הגוף מכיל את ה-traceback.
17. כשל עם `reason` ארוך מ-500 חלקים: ברשומת לוג הכשלים ה-`reason` שלם, בלי חיתוך.
18. אותו כשל: ה-`field` ברשומה שלם.
19. `internal_error` עם הודעה ארוכה: ה-ERROR בלוג הכשלים מכיל את ה-traceback כולו.
20. `invalid_request` עם פירוט ארוך: ה-WARNING בלוג הכשלים מכיל אותו כולו.

## מה לא משנים

- גוף של הקלאסטר עובר כמו שהוא. גם תשובת שגיאה של הקלאסטר (`error_code`, `description`) לא נוגעים בה.
- ה-headers: ‏`x-edge-error` ו-`x-edge-cluster-status` נשארים כמו היום. המנהל קורא מהם את הקוד, ולא מפרש את הגוף.
- הסיסמה בלוג DEBUG נשארת, בכוונה (החלטה מ-2026-11-01). התיקון כאן נוגע רק בתשובה ובלוג הכשלים.
- הדיאגרמות לא מצוירות מחדש.

## הצד של המנהל (redis-enterprise-services), לידיעה

המנהל לא מפרש את הגוף של cluster-client. הוא מעביר אותו כמו שהוא בתוך השגיאה שלו, ליד הקוד מה-header. לכן כל
עוד הגוף עומד בסכמה, אפשר לשנות אותו כאן בלי לשבור את המנהל.
