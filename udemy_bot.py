import feedparser
import requests
import time
import re
import os
import datetime
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup

# --- الإعدادات ---
TOKEN = "8787606333:AAE2Vs2Gq1fVaJtgl3vGYypTN_bqA1FkB-M"
CHAT_ID = "1934770017"

# --- مصادر كوبونات Udemy ---
COUPON_FEEDS = [
    "https://www.discudemy.com/feed",
    "https://www.tutorialbar.com/all-courses/feed/",
    "https://real.discount/feed/",
    "https://www.udemyfreebies.com/feed/",
    "https://couponscorpion.com/feed/",
    "https://www.onlinecoursesite.com/feed/",
    "https://freebiesglobal.com/feed/",
    "https://www.learnvern.com/feed",
]

# --- تصنيف الكورسات ---
CATEGORIES = {
    "🤖 ذكاء اصطناعي": ["ai", "artificial intelligence", "machine learning", "deep learning", "chatgpt", "llm", "neural", "nlp", "computer vision", "generative"],
    "💻 برمجة": ["python", "javascript", "java", "programming", "coding", "developer", "software", "web", "react", "node", "django"],
    "🎨 تصميم": ["design", "photoshop", "illustrator", "figma", "ui", "ux", "graphic", "canva", "adobe"],
    "📈 بيزنس": ["business", "freelance", "marketing", "seo", "entrepreneur", "productivity", "management", "finance"],
    "📱 تطبيقات": ["android", "ios", "flutter", "swift", "kotlin", "mobile", "app"],
    "🔐 أمن معلومات": ["cybersecurity", "hacking", "ethical hacking", "security", "network"],
    "📊 بيانات": ["data science", "data analysis", "excel", "sql", "tableau", "power bi"],
    "🎬 فيديو": ["video editing", "premiere", "after effects", "youtube", "podcast"],
    "⚙️ أتمتة": ["automation", "n8n", "zapier", "make", "workflow"],
}

DB_FILE = "sent_coupons.txt"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
}

def load_sent():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_sent(link):
    with open(DB_FILE, "a") as f:
        f.write(link + "\n")

def translate(text):
    try:
        if not text: return ""
        return GoogleTranslator(source='auto', target='ar').translate(text[:400])
    except:
        return text

def is_arabic(text):
    return bool(re.search(r'[\u0600-\u06FF]', text))

def is_english_or_arabic(text):
    other = re.search(r'[\u0900-\u097F\u4E00-\u9FFF\u3040-\u309F]', text)
    if other:
        return False
    return bool(re.search(r'[a-zA-Z\u0600-\u06FF]', text))

def get_category(title):
    title_lower = title.lower()
    for category, keywords in CATEGORIES.items():
        if any(kw in title_lower for kw in keywords):
            return category
    return "📚 تعليم عام"

def get_time_str(published):
    try:
        if published:
            pub_time = datetime.datetime(*published[:6])
            diff = datetime.datetime.now() - pub_time
            hours = diff.total_seconds() / 3600
            if hours > 12:
                return f"⚠️ نُشر منذ {int(hours)} ساعة — تحقق من الكوبون"
            elif hours > 1:
                return f"⏰ نُشر منذ {int(hours)} ساعات"
            else:
                return f"🆕 نُشر منذ {int(hours*60)} دقيقة"
    except:
        pass
    return "🆕 جديد"

def clean(text):
    if not text: return ""
    text = re.sub('<[^<]+?>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()[:300]

def is_100_percent(title, summary):
    text = (title + " " + summary).lower()
    return any(kw in text for kw in ["100% off", "free", "100%", "مجاني", "مجانا"])

def extract_udemy_link(text):
    """استخراج رابط Udemy من النص"""
    match = re.search(r'https?://(?:www\.)?udemy\.com/course/[^\s"\'<>]+', text)
    if match:
        return match.group(0)
    return None

def get_direct_udemy_link(entry_link, summary):
    """الحصول على رابط Udemy المباشر"""
    # محاولة من الرابط نفسه
    slug = re.search(r'udemy\.com/course/([^/?]+)', entry_link)
    if slug:
        coupon = re.search(r'couponCode=([^&\s]+)', entry_link)
        if coupon:
            return f"https://www.udemy.com/course/{slug.group(1)}/?couponCode={coupon.group(1)}"
        return f"https://www.udemy.com/course/{slug.group(1)}/"

    # محاولة من الـ summary
    udemy_link = extract_udemy_link(summary)
    if udemy_link:
        return udemy_link

    return entry_link

def scrape_course_image(udemy_url):
    """جلب صورة الكورس مباشرة من Udemy"""
    try:
        r = requests.get(udemy_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, 'html.parser')

        # الطريقة 1: og:image
        og = soup.find('meta', property='og:image')
        if og and og.get('content'):
            print(f"🖼️ Image found via og:image")
            return og['content']

        # الطريقة 2: twitter:image
        tw = soup.find('meta', attrs={'name': 'twitter:image'})
        if tw and tw.get('content'):
            print(f"🖼️ Image found via twitter:image")
            return tw['content']

        # الطريقة 3: JSON-LD
        import json
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string or '')
                if isinstance(data, dict) and data.get('image'):
                    print(f"🖼️ Image found via JSON-LD")
                    return data['image']
            except:
                continue

        # الطريقة 4: بحث مباشر عن صور الكورس
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if 'udemy' in src and ('480x270' in src or '240x135' in src):
                print(f"🖼️ Image found via img tag")
                return src

    except Exception as e:
        print(f"❌ Image scrape error: {e}")
    return None

def get_course_description(udemy_url):
    """جلب وصف الكورس من Udemy"""
    try:
        r = requests.get(udemy_url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            desc = soup.find('meta', attrs={'name': 'description'})
            if desc and desc.get('content'):
                return desc['content'][:300]
            og_desc = soup.find('meta', property='og:description')
            if og_desc and og_desc.get('content'):
                return og_desc['content'][:300]
    except:
        pass
    return None

def send_with_photo(image_url, caption):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    try:
        r = requests.post(url, json={
            "chat_id": CHAT_ID,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "Markdown"
        }, timeout=30)
        if r.status_code == 200:
            print("✅ Sent with photo!")
            return True
        print(f"⚠️ Photo failed: {r.status_code}")
        return False
    except Exception as e:
        print(f"❌ Photo error: {e}")
        return False

def send_text(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }, timeout=30)
        print(f"✅ Sent text: {r.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")

def fetch_coupons():
    print(f"\n🎓 جلب كوبونات Udemy — {datetime.datetime.now().strftime('%H:%M')}")
    sent = load_sent()
    new_count = 0

    for feed_url in COUPON_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            entries = feed.entries
            print(f"\n📡 {feed_url} — {len(entries)} كورس")

            for entry in entries[:10]:
                try:
                    link = entry.get("link", "")
                    title = entry.get("title", "")
                    summary_raw = entry.get("summary", entry.get("description", ""))

                    if not link or link in sent:
                        continue
                    if not is_english_or_arabic(title):
                        continue
                    if not is_100_percent(title, clean(summary_raw)):
                        continue

                    # الحصول على رابط Udemy المباشر
                    direct_link = get_direct_udemy_link(link, summary_raw)
                    print(f"\n📘 {title[:50]}")
                    print(f"🔗 {direct_link[:60]}")

                    # التصنيف والوقت
                    category = get_category(title)
                    time_str = get_time_str(entry.get("published_parsed"))

                    # جلب صورة الكورس
                    image_url = scrape_course_image(direct_link)

                    # جلب وصف الكورس
                    description = get_course_description(direct_link)
                    if not description:
                        description = clean(summary_raw)

                    # ترجمة الوصف إذا إنجليزي
                    if description and not is_arabic(description):
                        description = translate(description)

                    # بناء الرسالة
                    caption = (
                        f"{category} — *مجاني 100%* 🎁\n\n"
                        f"📚 *{title}*\n\n"
                        f"📝 {description}\n\n"
                        f"{time_str}\n\n"
                        f"🔗 [احصل على الكورس مجاناً]({direct_link})"
                    )

                    # إرسال مع صورة أو بدون
                    if image_url:
                        sent_ok = send_with_photo(image_url, caption)
                        if not sent_ok:
                            send_text(caption)
                    else:
                        send_text(caption)

                    save_sent(link)
                    new_count += 1
                    time.sleep(3)

                except Exception as e:
                    print(f"❌ Entry error: {e}")
                    continue

        except Exception as e:
            print(f"❌ Feed error: {e}")

    print(f"\n✅ تم إرسال {new_count} كورس جديد")

def main():
    print("=" * 40)
    print("🎓 بوت كوبونات Udemy")
    print(f"⏰ {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 40)
    fetch_coupons()
    print("\n✅ انتهى!")

if __name__ == "__main__":
    main()
