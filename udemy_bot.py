import feedparser
import requests
import time
import re
import os
import datetime
from deep_translator import GoogleTranslator

# --- الإعدادات ---
TOKEN = "8787606333:AAE2Vs2Gq1fVaJtgl3vGYypTN_bqA1FkB-M"
CHAT_ID = "1934770017"

# --- مصادر كوبونات Udemy 100% ---
COUPON_FEEDS = [
    "https://www.tutorialbar.com/all-courses/feed/",
    "https://real.discount/feed/",
    "https://www.discudemy.com/feed",
    "https://www.udemyfreebies.com/feed/",
    "https://couponscorpion.com/feed/",
    "https://www.onlinecoursesite.com/feed/",
]

# --- تصنيف الكورسات ---
CATEGORIES = {
    "🤖 ذكاء اصطناعي": ["ai", "artificial intelligence", "machine learning", "deep learning", "chatgpt", "llm", "neural", "nlp", "computer vision"],
    "💻 برمجة": ["python", "javascript", "java", "programming", "coding", "developer", "software", "web development", "react", "node"],
    "🎨 تصميم": ["design", "photoshop", "illustrator", "figma", "ui", "ux", "graphic", "canva", "adobe"],
    "📈 بيزنس وفريلانسر": ["business", "freelance", "marketing", "seo", "entrepreneur", "productivity", "management", "finance"],
    "📱 تطوير تطبيقات": ["android", "ios", "flutter", "swift", "kotlin", "mobile", "app development"],
    "🔐 أمن معلومات": ["cybersecurity", "hacking", "ethical hacking", "security", "network"],
    "📊 بيانات": ["data science", "data analysis", "excel", "sql", "tableau", "power bi", "statistics"],
    "🎬 فيديو وصوت": ["video editing", "premiere", "after effects", "youtube", "podcast", "audio"],
}

DB_FILE = "sent_coupons.txt"

def load_sent():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_sent(link):
    with open(DB_FILE, "a") as f:
        f.write(link + "\n")

def send(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }, timeout=30)
        print(f"✅ Sent: {r.status_code}")
        time.sleep(1)
    except Exception as e:
        print(f"❌ Error: {e}")

def clean(text):
    if not text: return ""
    text = re.sub('<[^<]+?>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()[:250]

def is_english_or_arabic(text):
    """تحقق إذا الكورس إنجليزي أو عربي"""
    arabic = re.search(r'[\u0600-\u06FF]', text)
    english = re.search(r'[a-zA-Z]', text)
    # رفض اللغات الأخرى مثل الهندية والصينية وغيرها
    other = re.search(r'[\u0900-\u097F\u4E00-\u9FFF\u3040-\u309F]', text)
    if other:
        return False
    return bool(arabic or english)

def get_category(title):
    """تحديد تصنيف الكورس"""
    title_lower = title.lower()
    for category, keywords in CATEGORIES.items():
        if any(kw in title_lower for kw in keywords):
            return category
    return "📚 تعليم عام"

def get_time_warning(published):
    """تحذير إذا الكوبون قديم"""
    try:
        if published:
            pub_time = datetime.datetime(*published[:6])
            diff = datetime.datetime.now() - pub_time
            hours = diff.total_seconds() / 3600
            if hours > 12:
                return f"⚠️ نُشر منذ {int(hours)} ساعة — قد يكون انتهى"
            elif hours > 6:
                return f"⏰ نُشر منذ {int(hours)} ساعات — تصرف بسرعة"
            else:
                return f"🆕 نُشر منذ {int(hours*60)} دقيقة"
    except:
        pass
    return "🆕 جديد"

def get_udemy_rating(course_url):
    """محاولة جلب تقييم الكورس"""
    try:
        # استخراج slug من رابط Udemy
        match = re.search(r'udemy\.com/course/([^/?]+)', course_url)
        if not match:
            return None
        slug = match.group(1)
        api_url = f"https://www.udemy.com/api-2.0/courses/{slug}/"
        params = {"fields[course]": "rating,num_reviews,content_length_video"}
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(api_url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            rating = data.get("rating", 0)
            reviews = data.get("num_reviews", 0)
            return rating, reviews
    except:
        pass
    return None

def is_100_percent_coupon(title, summary):
    """تحقق إذا الكوبون 100% مجاني"""
    text = (title + " " + summary).lower()
    return (
        "100% off" in text or
        "free" in text or
        "100%" in text or
        "مجاني" in text or
        "مجانا" in text or
        "مجانً" in text
    )

def fetch_coupons():
    print(f"\n🎓 جلب كوبونات Udemy — {datetime.datetime.now().strftime('%H:%M')}")
    sent = load_sent()
    new_count = 0

    for feed_url in COUPON_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            print(f"📡 {feed_url} — {len(feed.entries)} كورس")

            for entry in feed.entries[:10]:
                link = entry.get("link", "")
                title = entry.get("title", "")
                summary = clean(entry.get("summary", entry.get("description", "")))

                # تجاهل المرسل مسبقاً
                if link in sent:
                    continue

                # تحقق من اللغة
                if not is_english_or_arabic(title):
                    continue

                # تحقق من 100%
                if not is_100_percent_coupon(title, summary):
                    continue

                # تحديد التصنيف
                category = get_category(title)

                # وقت النشر
                time_warning = get_time_warning(entry.get("published_parsed"))

                # محاولة جلب التقييم
                rating_info = get_udemy_rating(link)
                rating_text = ""
                if rating_info:
                    rating, reviews = rating_info
                    if rating < 4.0:
                        save_sent(link)
                        continue  # تجاهل الكورسات ضعيفة التقييم
                    rating_text = f"⭐ التقييم: *{rating:.1f}* ({reviews:,} تقييم)\n"

                # بناء الرسالة
                msg = (
                    f"{category} — *كورس مجاني 100%* 🎁\n\n"
                    f"📚 *{title}*\n\n"
                    f"📝 {summary}\n\n"
                    f"{rating_text}"
                    f"{time_warning}\n\n"
                    f"🔗 [احصل على الكورس مجاناً]({link})"
                )

                send(msg)
                save_sent(link)
                new_count += 1
                time.sleep(2)

        except Exception as e:
            print(f"❌ Error {feed_url}: {e}")

    print(f"✅ تم إرسال {new_count} كورس جديد")

def main():
    print("=" * 40)
    print("🎓 بوت كوبونات Udemy")
    print(f"⏰ {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 40)
    fetch_coupons()
    print("✅ انتهى!")

if __name__ == "__main__":
    main()
