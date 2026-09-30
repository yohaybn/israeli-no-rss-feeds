# israeli-no-rss-feeds

פידי RSS לאתרים ישראליים מובילים שאין להם RSS משלהם - בלי סקרייפר ייעודי לכל אתר.

## איך זה עובד

1. `sites.json` - רשימת האתרים (URL אחד לכל אתר, בלי קונפיגורציה נוספת).
2. GitHub Actions רץ כל 30 דקות ומפעיל את [html2rss](https://github.com/html2rss/html2rss) (Ruby, קוד פתוח) במצב חילוץ אוטומטי (`auto-source`) על כל אתר: הוא מחפש קודם פיד קיים נסתר, אחר כך נתונים מובנים (JSON-LD, microformats, JSON פנימי של האתר), ורק בסוף ניתוח HTML היוריסטי.
3. התוצאה מנוקה ל**כותרת + קישור + תקציר קצר (עד 500 תווים) + תמונה כשזמינה** (ראו "חוקיות" למטה) ונשמרת ב-branch `gh-pages`. תאריך הפרסום האמיתי נשלף כשהאתר חושף אותו בעמוד הרשימה; אחרת מוצג זמן הסריקה.
4. הפידים מוגשים מ-GitHub Pages:

```
https://yohaybn.github.io/israeli-no-rss-feeds/feeds/<slug>.xml
```

דף סטטוס חי: https://yohaybn.github.io/israeli-no-rss-feeds/ (כולל `status.json` קריא-מכונה).

אם GitHub Pages לא זמין, אותם קבצים נגישים גם ישירות:

```
https://raw.githubusercontent.com/yohaybn/israeli-no-rss-feeds/gh-pages/feeds/<slug>.xml
```

## בקשת פיד חדש (שירות עצמי)

רוצים פיד לאתר שלא ברשימה? [פתחו בקשת פיד](https://github.com/yohaybn/israeli-no-rss-feeds/issues/new?template=feed-request.yml) עם שם האתר וה-URL. GitHub Actions מריץ html2rss auto-source על הכתובת: אם נמצאו פריטים נפתח PR אוטומטי עם ההגדרה (אחרי מיזוג הפיד באוויר תוך ~30 דקות); אם לא - מתקבלת תגובה ב-issue שהאתר דורש הגדרה ידנית.

**מיזוג אוטומטי:** בקשות שנפתחות על ידי בעל הריפו (@yohaybn) מתמזגות אוטומטית אם עוברות את בדיקות האימות (כתובת https, מינימום 3 פריטים, קישורי הפריטים נשארים באותו דומיין). בקשות של כל אחד אחר נשארות PR פתוח לסקירה ידנית - מיגון מול ספאם.

## האתרים ברשימה הראשונית

חדשות: 0404, רשת 13, כאן 11, i24NEWS, News1, nfc, החמל, מקור ראשון, ישראל היום, זמן ישראל, חי פה, عرب 48, بانيت.
ספורט: Sport5, עמותת הכדורסל. כלכלה: כלכליסט, ביזפורטל. חרדים ודת: עקטואליק, ביזם, לעדת, שטורעם, ישיבה, הידברות. נוספים: PassportNews, Israel Defense, גלי צה"ל, 103FM.

כל אתר נבדק ידנית שאין בו פיד RSS/Atom נגלה (תגית `<link>` או נתיבים נפוצים) לפני שנוסף. הערה: חלק מהאתרים חוסמים בוטים ברמת הרשת; אתר שלא מצליח מסומן בדף הסטטוס, והפיד האחרון שעבד נשמר.

## להוסיף אתר

פתחו PR שמוסיף שורה אחת ל-`sites.json`:

```json
{"slug": "mysite", "name": "האתר שלי", "url": "https://www.mysite.co.il", "lang": "he", "category": "news"}
```

`slug` באנגלית קטנה בלבד (`a-z`, `0-9`, `-`), ייחודי. ה-CI בודק את הסכמה, והריצה הבאה כבר מייצרת את הפיד. אם לאתר יש פיד מובנה, html2rss יגלה אותו לבד וישתמש בו - אז עדיף פשוט להשתמש בפיד המקורי.

## חוקיות ונימוס ברשת

- **בלי שכפול תוכן.** הפידים מצביעים לכתבה באתר המקור ומראים רק תקציר קצר (טקסט פשוט, עד 500 תווים) ותמונה ממוזערת מהרשימה, בדומה לאגרגטורי חדשות ולתצוגת קישור. גוף הכתבה המלא (`content:encoded`, תיאורים ארוכים) נחסם ונאכף ב-CI.
- **robots.txt נכבד.** אתר שחוסם את הדף ב-robots.txt מדולג אוטומטית.
- **תדירות מתונה.** בקשה אחת לאתר כל 30 דקות, ברצף (לא במקביל), עם השהיה בין אתרים.
- דפים ציבוריים בלבד, בלי עקיפת הגנות או התחברות.

אין לראות בזה ייעוץ משפטי; אם אתר מבקש להוסר מהרשימה - פתחו issue והוא יוסר.

## טכני

- הריצה המתוזמנת (`cron`) מוגדרת ל-30 דקות, אבל GitHub מעכב ריצות מתוזמנות בעומס - בפועל כל 30-60 דקות.
- `gh-pages` נכתב מחדש בכל ריצה (force push) כדי לא לנפח את ההיסטוריה; ריצות שבהן אתר נכשל שומרות את הפיד האחרון שעבד שלו.
- כשהריפו יעבור לבעלות `yohaybn` יש לעדכן את `FEEDS_BASE_URL` ב-workflow ואת הקישורים כאן.
- CI: `test.yml` מריץ בדיקות יחידה על לוגיקת הניקוי והסכמה; `generate-feeds.yml` מאמת כל פיד שנוצר לפני פרסום.

## רישיון

MIT. תודה לפרויקט [html2rss](https://github.com/html2rss/html2rss) שעושה את כל העבודה הקשה.

---

# English

RSS feeds for leading Israeli sites that don't have one - without a per-site scraper.

**Request a new feed (self-service):** [open a feed request](https://github.com/yohaybn/israeli-no-rss-feeds/issues/new?template=feed-request.yml) with the site name and URL. A GitHub Actions job runs html2rss auto-source on it: if items are found it opens a PR automatically (live ~30 min after merge); otherwise it comments on the issue that a hand-written config is needed. Requests opened by the repo owner auto-merge when validation gates pass (https only, >=3 items, item links stay on the submitted domain); everyone else's PRs wait for manual review (spam protection).

**How:** a single config list (`sites.json`) + a GitHub Actions job (every 30 min) that runs the [html2rss](https://github.com/html2rss/html2rss) gem in auto-source mode over the list, normalizes each feed to **title + link + a short plain-text teaser (≤500 chars) + an image enclosure when the listing exposes one** (real publish dates where the listing exposes them, scrape time otherwise), and publishes the result to the `gh-pages` branch, served by GitHub Pages at `https://yohaybn.github.io/israeli-no-rss-feeds/feeds/<slug>.xml` (raw-URL fallback available). Live status page and machine-readable `status.json` at the same URL.

**Add a site:** PR one line into `sites.json` (see format above); CI validates the schema and the next run generates the feed. If a site actually has a hidden native feed, html2rss discovers and uses it automatically.

**Legality & politeness:** no article-content republication (full bodies blocked, enforced in CI; only the site's own short listing teaser and thumbnail), robots.txt respected, one request per site every 30 minutes, sequential with delays, public pages only. Not legal advice; sites asking to be removed will be removed.

MIT license.

## WordPress REST sources

For WordPress publishers without usable RSS, add a domain entry to `sites.json` with `"generator": "wordpress"` (plus slug, name, HTTPS URL, language and category). Each entry gets its own feed. The endpoint is derived automatically from the domain: `/wp-json/wp/v2/posts`. An optional same-host `wordpress_api` remains supported for existing configs.

Before enabling/publishing a site, the generator checks robots and requires a non-empty, valid WordPress posts JSON response with publisher IDs, UTC dates, same-host links and rendered titles. Disabled REST APIs, HTTP failures, HTML responses and malformed JSON are skipped with a clear per-site log/status reason. Other sites continue and last-good XML stays untouched. Requests include only the latest 25 IDs, UTC dates, links, headlines and excerpts, never full bodies. Refresh remains every 30 minutes through the existing Actions/Pages pipeline.

Verified WordPress list (2026-09-30):

| Site | Native RSS status | REST status |
| --- | --- | --- |
| LetsAI (`letsai.co.il`) | `/feed/`, `?feed=rss2` and RSS aliases redirect to homepage HTML; robots also blocks feeds | Valid posts, latest Sep 30 |
| TECH-IL (`tech-il.co.il`) | `/feed/` and `?feed=rss2` redirect to homepage HTML | Valid posts, latest Sep 29 |
| The Verifier (`theverifier.co.il`) | Advertises RSS, but XML currently fails parsing due to duplicate `xmlns:media` attribute | Valid posts, latest Sep 28 |
| Newsgeek (`newsgeek.co.il`) | `/feed/` and `?feed=rss2` redirect to homepage HTML | Valid posts, latest Sep 30; consumer/news blog, not Geektime |

The Verifier has a broken RSS feed, not no RSS at all. If its publisher repairs that feed, prefer the native feed. Sites already serving valid RSS (including Geektime, TGspot, GadgetSite, HWzone, HTMag, GameTech, Y4PC, G-Rafa and TechZ) are not duplicated. Unreachable or API-blocked sites are not enabled based on guesses. Utechnet had a usable REST API but no posts newer than February 2025, so it was not added to this current-news list.

## Calcalist category feeds

Only Calcalist's 13 main categories are enabled in sites.json, matching the recommendation catalog. Subcategories are not generated or published.
The `calcalist` adapter reads only public category listing metadata (headline,
permalink, short teaser, publication date and image), including the JSON already
embedded in category pages. It never fetches article bodies or unlocks premium text.
24/7 and Buzz use the same public listing endpoints used by those pages.
All configured categories are refreshed by the existing 30-minute Actions schedule.
Temporary failures preserve previously published XML for active feeds. Retired Calcalist files are removed from publication on the next generator run. New categories introduced by
the publisher need a sites.json/catalog update; navigation discovery is not repeated
on every run. Financial quote tables, contact/legal pages and external course stores
are not article categories and are not turned into feeds.
