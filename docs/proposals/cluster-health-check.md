# הצעה: בדיקת בריאות של קלאסטרי Redis בעלייה

**סטטוס:** מזכר לבדיקה. לא מומש. צריך להחליט אם להוסיף. תלוי ב[החלטת היסוד](#החלטת-יסוד-האם-ה-cluster-client-מכיר-את-הקלאסטרים).
**תאריך:** 2026-10-17

## הרעיון

כשה־cluster-client עולה, הוא בודק כל קלאסטר Redis Enterprise שמוגדר בסביבה שלו ורושם את התוצאה.
הפיצ'ר אופציונלי: בלי קונפיגורציה הוא כבוי, וה־cluster-client מתנהג בדיוק כמו היום.

ה־cluster-client רץ באותה רשת שבה נמצאים הקלאסטרים, אז הקריאה לא עוברת בחומת האש.

## ה־endpoints של Redis

| Endpoint | מה הוא בודק | הרשאה |
|---|---|---|
| `GET /v1/cluster/check` | כל ה־nodes: bootstrap, services, pidfiles, sockets, port range, capabilities, host settings, TCP בין nodes | `view_all_nodes_checks` |
| `GET /v1/local/node/master_healthcheck` | רק האם ה־node שעונה מחובר ל־node הראשי ולמאגר הקונפיגורציה (CCS) | `view_cluster_info` |

תשובה של `/v1/cluster/check`:

```json
{
  "cluster_test_result": false,
  "nodes": [
    { "node_uid": "1", "result": true },
    { "node_uid": "3", "result": false, "error": "process alert_mgr is not running ..." }
  ]
}
```

- **status code:** הקריאה מחזירה תמיד 200, גם כשהקלאסטר לא בריא. ההחלטה נקבעת לפי `cluster_test_result` מתוך ה־body.
- **שגיאות:** לכל node מופיעה רק השגיאה הראשונה שלו.

מקורות:
[cluster/check](https://redis.io/docs/latest/operate/rs/references/rest-api/requests/cluster/check),
[master_healthcheck](https://redis.io/docs/latest/operate/rs/references/rest-api/requests/node_master_healthcheck/),
[nodes/check](https://redis.io/docs/latest/operate/rs/references/rest-api/requests/nodes/check)

## קונפיגורציה מוצעת (ENV)

רשימת הקלאסטרים, לא סודית, ב־ConfigMap דרך `config:` ב־`values.yaml`:

```env
CLUSTER_CLIENT_CLUSTER_HEALTH__ENABLED=true
CLUSTER_CLIENT_CLUSTER_HEALTH__TIMEOUT_SECONDS=5
CLUSTER_CLIENT_CLUSTER_HEALTH__VERIFY_TLS=true
CLUSTER_CLIENT_CLUSTER_HEALTH__CA_BUNDLE_PATH=/etc/cluster-client/ca.pem
CLUSTER_CLIENT_CLUSTERS=[{"name": "east-1", "url": "https://east-1.internal:9443"}, {"name": "east-2", "url": "https://east-2.internal:9443"}]
```

פרטי הגישה ב־Kubernetes Secret, דרך `envFromSecrets` שכבר קיים ב־chart:

```env
CLUSTER_CLIENT_CLUSTER_CREDENTIALS={"east-1": {"username": "...", "password": "..."}, "east-2": {...}}
```

- **סיסמאות:** נשמרות כ־`SecretStr` של Pydantic, ולא מופיעות בלוג או ב־repr.
- **אימות:** בעלייה נבדק שלכל קלאסטר ברשימה יש פרטי גישה. אם חסרים, השירות לא עולה, עם שגיאה ברורה.

## החלטת יסוד: האם ה־cluster-client מכיר את הקלאסטרים?

בדיקת הבריאות בעלייה אפשרית רק אם ה־cluster-client מחזיק רשימת קלאסטרים. לכן ההחלטה הזו באה לפני כל השאר.

| אפשרות | מה ה־cluster-client מחזיק | בקשה לקלאסטר שהוא לא מכיר | בדיקת בריאות בעלייה |
|---|---|---|---|
| **(א) לא מכיר כלום** | כלום. ה־URL ופרטי האימות מגיעים מה־manager עם כל בקשה | מועברת כמו שהיא | לא אפשרית. ה־manager שולח `GET /v1/cluster/check` דרך ה־cluster-client |
| **(ב) רשימה + פרטי גישה** | שם, URL ופרטי גישה לכל קלאסטר ברשת שלו | נדחית עם שגיאה "לא מכיר" | אפשרית |
| **(ג) רשימה בלבד (allowlist)** | שם ו־URL. פרטי האימות עדיין מגיעים מה־manager | נדחית עם שגיאה "לא מכיר" | רק אם מוסיפים גם פרטי גישה |

### מה נגזר מכל אפשרות

- **אבטחה:** ב־(ב) וב־(ג) ה־cluster-client לא יכול לשמש כ־proxy פתוח. גם אם מישהו מגיע אליו, הוא מעביר בקשות רק לקלאסטרים שברשימה. ב־(א) ה־cluster-client מעביר לכל URL שמגיע אליו.
- **פרטי גישה:** ב־(ב) הסיסמאות של כל רשת נשארות בתוך הרשת, ולא עוברות בחומת האש עם כל בקשה. ב־(א) וב־(ג) הן עוברות בכל בקשה.
- **קונפיגורציה:** ב־(ב) וב־(ג) כל cluster-client צריך קונפיגורציה משלו: ConfigMap ו־Secret לכל רשת. ב־(א) כל ה־cluster-clients זהים.
- **הוספת קלאסטר:** ב־(ב) וב־(ג) צריך לעדכן את ה־cluster-client של הרשת. ב־(א) מספיק לעדכן את ה־manager.

### שאלות שנפתחות אם בוחרים ב־(ב) או ב־(ג)

1. **זיהוי הקלאסטר בבקשה:** לפי ה־host ב־URL המלא שב־header, או לפי header חדש עם שם הקלאסטר?
2. **השגיאה:** איזה status code? `404`, או `403`, או `421 Misdirected Request`? צריך גוף שגיאה מסודר, למשל `{"error": "unknown_cluster", "cluster": "..."}`, ולוג WARNING.
3. **פרטי אימות ב־(ב):** אם ה־manager שולח פרטי אימות למרות שה־cluster-client מחזיק משלו, מה קודם? לדחות את הבקשה, לדרוס את מה שנשלח, או להשתמש במה שנשלח?
4. **עדכון הרשימה:** רק ב־redeploy (שינוי ConfigMap או Secret), או גם בלי restart?

## החלטות פתוחות (בדיקת הבריאות, רלוונטי רק ל־(ב))

1. **מה קורה כשקלאסטר לא בריא?**
   - (א) השירות לא עולה.
   - (ב) `/health/ready` מחזיר 503, ו־Kubernetes מפסיק לשלוח אליו תעבורה.
   - (ג) נרשמת שגיאה בלוג, והשירות ממשיך.

   **המלצה: (ג) כברירת מחדל, ו־(ב) כאופציה בקונפיגורציה.** קלאסטר אחד תקול לא צריך להפיל את ה־cluster-client לכל השאר.
2. **רק בעלייה, או גם מחזורית?** בדיקה מחזורית מאפשרת ש־`/health/ready` ישקף את המצב הנוכחי.
3. **איזו בדיקה?** `cluster/check` מלא, או `master_healthcheck` הקל, או שניהם: הקל קודם, המלא רק אם הקל עבר.
4. **הרשאה:** לבדוק לאיזה role יש `view_all_nodes_checks`. עדיף משתמש ייעודי עם הרשאות קריאה בלבד.
5. **TLS:** ה־REST API של Redis Enterprise רץ על port 9443, לרוב עם תעודה פנימית. צריך CA bundle, לא `verify=False`.

## מימוש משוער (אם מאשרים)

```
app/config/cluster_settings.py        ClusterSettings, ClusterHealthSettings, ClusterCredentials
app/clusters/health_client.py         calls /v1/cluster/check, returns ClusterHealthReport
app/clusters/health_report.py         Pydantic model of the response
app/clusters/startup_check.py         runs the checks in the FastAPI lifespan, in parallel
app/exceptions/                       MissingClusterCredentialsError, ClusterUnreachableError
```

- **הרשמה ב־factory:** `create_app(settings)` מוסיף את הבדיקה ל־lifespan רק אם `cluster_health.enabled`.
- **בדיקות:** unit מול שרת Redis מדומה (`httpx.MockTransport`). integration עם `create_app` והגדרות של שני קלאסטרים, אחד בריא ואחד לא. e2e עם שרת מדומה אמיתי על port.
- **ספרייה חדשה:** `httpx` עובר מ־dev ל־dependencies.
