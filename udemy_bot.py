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

def translate(text):
    try:
        if not text: return ""
        return GoogleTranslator(source='auto', target='ar').translate(text[:400])
    except:
        return text

def is_arabic(text):
    return bool(re.search(r'[\u0600-\u06FF]', text))

def send_photo(photo_url, caption):
    """إرسال رسالة مع صورة"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    try:
        r = requests.post(url, json={
            "chat_id": CHAT_ID,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": "Markdown"
        }, timeout=30)
        if r.status_code == 200:
            print(f"✅ Sent with photo: {r.status_code}")
            return True
        else:
            return False
    except Exception as e:
        print(f"❌ Photo error: {e}")
        return False

def send_text(text):
    """إرسال رسالة نصية فقط"""
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

def clean(text):
    if not text: return ""
    text = re.sub('<[^<]+?>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()[:300]

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

def get_time_warning(published):
    try:
        if published:
            pub_time = datetime.datetime(*published[:6])
            diff = datetime.datetime.now() - pub_time
            hours = diff.total_seconds() / 3600
            if hours > 12:
                return f"⚠️ نُشر منذ {int(hours)} ساعة — تحقق من الكوبون"
            elif hours > 6:
                return f"⏰ نُشر منذ {int(hours)} ساعات — تصرف بسرعة"
            else:
                mins = int(hours * 60)
                return f"🆕 نُشر منذ {mins} دقيقة"
    except:
        pass
    return "🆕 جديد"

def get_udemy_data(course_url):
    """جلب بيانات الكورس من Udemy"""
    try:
        match = re.search(r'udemy\.com/course/([^/?]+)', course_url)
        if not match:
            return None
        slug = match.group(1)
        api_url = f"https://www.udemy.com/api-2.0/courses/{slug}/"
        params = {
            "fields[course]": "rating,num_reviews,content_length_video,price,image_480x270,headline"
        }
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(api_url, params=params, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Udemy API error: {e}")
    return None

def get_image_from_feed(entry):
    """محاولة جلب الصورة من RSS"""
    try:
        # محاولة 1: من media_content
        if hasattr(entry, 'media_content') and entry.media_content:
            return entry.media_content[0].get('url', '')
        # محاولة 2: من media_thumbnail
        if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
            return entry.media_thumbnail[0].get('url', '')
        # محاولة 3: من summary بحث عن img
        summary = entry.get('summary', '')
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary)
        if img_match:
            return img_match.group(1)
    except:
        pass
    return None

def get_popularity(num_reviews):
    """تحديد مؤشر الشعبية"""
    if num_reviews >= 10000:
        return "🔥 مشهور جداً"
    elif num_reviews >= 1000:
        return "⭐ محبوب"
    else:
        return "🆕 جديد"

def format_duration(minutes):
    """تحويل الدقائق لساعات"""
    if not minutes:
        return None
    hours = minutes / 60
    if hours < 1:
        return f"{int(minutes)} دقيقة"
    return f"{hours:.1f} ساعة"

def is_100_percent_coupon(title, summary):
    text = (title + " " + summary).lower()
    return any(kw in text for kw in ["100% off", "free", "100%", "مجاني", "مجانا", "مجانً"])

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
                summary_raw = clean(entry.get("summary", entry.get("description", "")))

                if link in sent:
                    continue
                if not is_english_or_arabic(title):
                    continue
                if not is_100_percent_coupon(title, summary_raw):
                    continue

                # تحديد التصنيف
                category = get_category(title)

                # وقت النشر
                time_str = get_time_warning(entry.get("published_parsed"))

                # ترجمة النبذة إذا كانت إنجليزية
                if is_arabic(title):
                    summary_final = summary_raw
                else:
                    summary_final = translate(summary_raw)

                # جلب بيانات Udemy
                udemy_data = get_udemy_data(link)
                rating_text = ""
                duration_text = ""
                price_text = ""
                popularity_text = ""
                image_url = get_image_from_feed(entry)
                priority_badge = ""

                if udemy_data:
                    rating = udemy_data.get("rating", 0)
                    num_reviews = udemy_data.get("num_reviews", 0)
                    duration_mins = udemy_data.get("content_length_video", 0)
                    price = udemy_data.get("price", "")
                    img = udemy_data.get("image_480x270", "")

                    # تجاهل الكورسات ضعيفة التقييم
                    if rating and rating < 4.0:
                        save_sent(link)
                        continue

                    if rating:
                        rating_text = f"⭐ التقييم: *{rating:.1f}*"
                    if num_reviews:
                        popularity_text = get_popularity(num_reviews)
                        rating_text += f" | {popularity_text}"
                    if duration_mins:
                        dur = format_duration(duration_mins)
                        if dur:
                            duration_text = f"⏱️ المدة: {dur}\n"
                    if price and price != "Free":
                        price_text = f"💰 السعر الأصلي: *{price}* — الآن مجاني!\n"
                    if img:
                        image_url = img

                    # تنبيه أولوية للكورسات المميزة
                    if rating >= 4.5 and num_reviews >= 1000:
                        priority_badge = "⚡ *كورس مميز — لا تفوته!*\n"

                # بناء الرسالة
                caption = (
                    f"{priority_badge}"
                    f"{category} — *مجاني 100%* 🎁\n\n"
                    f"📚 *{title}*\n\n"
                    f"📝 {summary_final}\n\n"
                    f"{rating_text}\n"
                    f"{duration_text}"
                    f"{price_text}"
                    f"{time_str}\n\n"
                    f"🔗 [احصل على الكورس مجاناً]({link})"
                )

                # إرسال مع صورة أو بدون
                if image_url:
                    success = send_photo(image_url, caption)
                    if not success:
                        send_text(caption)
                else:
                    send_text(caption)

                save_sent(link)
                new_count += 1
                time.sleep(3)

        except Exception as e:
            print(f"❌ Error {feed_url}: {e}")

    print(f"✅ تم إرسال {new_count} كورس جديد")

def main():
    print("=" * 40)
    print("🎓 بوت كوبونات Udemy المطور")
    print(f"⏰ {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 40)
    fetch_coupons()
    print("✅ انتهى!")

if __name__ == "__main__":
    main()
