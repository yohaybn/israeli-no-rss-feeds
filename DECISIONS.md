# DECISIONS

החלטות מתמשכות בפרויקט, כדי שסוכנים ותורמים לא יעבדו כפול.
לכל החלטה: מה הוחלט, למה, ומה נפסל. חדשות בסוף.

## 1. html2rss auto-source על GitHub Actions, לא סקרייפר לאתר ולא שרת (2026-09-25)
רשימת `sites.json` אחת + job מתוזמב (כל 30 דקות) שמריץ html2rss במצב auto-source.
הריפו ציבורי כי דקות Actions חינמיות בריפו ציבורי; ריפו פרטי היה חורג ממכסת הדקות.
נדחה: html2rss-web עצמי על Synology ("אני לא רוצה שרת אצלי"), rss-bridge (סלקטור
לכל אתר), RSSHub (אין routes לאתרים), הטמעת html2rss באפליקציה או פורט ל-Kotlin
(Ruby עם תלויות native; בעלות על היוריסטיקות לנצח ועדכוני extractor כגרסאות אפליקציה).

## 2. קו חוקי קבוע (2026-09-25)
דפים ציבוריים בלבד, בלי עקיפת הגנות או התחברות. robots.txt נכבד. הפידים מכילים
כותרת + קישור + תקציר קצר (עד 500 תווים) ותמונה ממוזערת בלבד; גוף כתבה מלא
(`content:encoded`, תיאורים ארוכים) חסום ונאכף ב-CI. אתר שמבקש להוסר - מוסר.

## 3. רק אתרים בלי RSS מקורי שמיש (2026-09-30)
כל אתר נבדק שאין לו פיד RSS/Atom נגלה לפני הוספה. אם מתגלה או מתקן פיד מקורי,
מעדיפים אותו על המגונרט (מקרה The Verifier: RSS שבור; אם יתוקן - חוזרים אליו).
אתרים עם RSS תקין (Geektime, TGspot, GadgetSite וכו') לא משוכפלים.

## 4. כלכליסט: בדיוק 13 הקטגוריות הראשיות (2026-09-30)
ב-`sites.json`, בפרסום ובקטלוג ההמלצות. תתי-קטגוריות הוסרו (תיקון להחלטת 87 פידים).
טבלאות מניות, דפי משפט/יצירת קשר וחנויות קורסים חיצוניות אינם קטגוריות כתבות
ולא הופכים לפידים. קבצי פידים שהוסרו מהסקופ נמחקים מהפרסום בריצה הבאה.
קטגוריה חדשה של המפרסם דורשת עדכון מפורש; אין גילוי ניווט מחדש בכל ריצה.

## 5. בקשות פיד בשירות עצמי עם שער אימות (2026-09)
בקשות שנפתחות על ידי בעל הריפו מתמזגות אוטומטית רק אחרי אימות: https, מינימום
3 פריטים, וקישורי פריטים באותו דומיין. בקשות של כל אחד אחר מחכות לסקירה ידנית
(מיגון ספאם).

## 6. WordPress: generator גנרי, לא תצורה לאתר (2026-09)
`"generator": "wordpress"` ב-`sites.json`; ה-endpoint נגזר מהדומיין
(`/wp-json/wp/v2/posts`). נשלפים 25 הפוסטים האחרונים, מטא-דאטה בלבד (מזהה, תאריך
UTC, קישור, כותרת, תקציר), לעולם לא גוף מלא. API כבוי/שבור/לא-JSON מדולג עם סיבה
ברורה, והפיד האחרון שעבד נשמר.

## 7. TECH-IL relay: Worker צר, לא פרוקסי פתוח (2026-09-30)
ה-Cloudflare Worker משרת רק את robots.txt ואת רשימת ה-WordPress הקבועה של TECH-IL.
ללא העברת cookies/כותרות, ללא hosts אחרים, ללא שיטות כתיבה. cache של 15 דקות,
שגיאות upstream לא נשמרות, תוכנית חינמית בלבד, והטוקן רק ב-GitHub secrets.
אם `TECH_IL_WORKER_URL` לא מוגדר - חוזרים לשליפה ישירה.

## 8. פרסום: gh-pages נכתב מחדש, last-good נשמר (2026-09)
`gh-pages` מקבל force push בכל ריצה כדי לא לנפח את ההיסטוריה. כשל זמני באתר
משאיר את הפיד האחרון שעבד באוויר ומסמן את האתר בדף הסטטוס.

---

# English

1. html2rss auto-source on GitHub Actions (every 30 min) over a single `sites.json`; public repo because Actions minutes are free there. Rejected: self-hosted html2rss-web, rss-bridge, RSSHub, in-app embedding or a Kotlin port. (2026-09-25)
2. Fixed legal line: public pages only, robots.txt respected, title + link + <=500-char teaser + thumbnail; full bodies blocked and enforced in CI; removal on request. (2026-09-25)
3. Only sites without usable native RSS; a discovered or repaired native feed wins over the generated one (The Verifier case). (2026-09-30)
4. Calcalist scope is exactly the 13 main categories in sites.json, publication and catalog; retired files are deleted from publication; quote tables, legal pages and course stores are not feeds. (2026-09-30)
5. Self-service feed requests: owner-opened requests auto-merge only after validation (https, >=3 items, same-domain item links); all others wait for manual review. (2026-09)
6. WordPress: generic `generator: "wordpress"` with the endpoint derived from the domain; latest 25 posts, metadata only, never full bodies; broken APIs are skipped with a clear reason and last-good XML stays. (2026-09)
7. TECH-IL relay is a narrow Worker (robots.txt + the fixed listing only), not an open proxy: no header forwarding, 15-minute cache, free plan only, token only in GitHub secrets. (2026-09-30)
8. Publishing: gh-pages is force-pushed each run; temporary failures keep the last working feed live and flag the site on the status page. (2026-09)
