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
    "https://www.tutorialbar.com/all-courses/feed/",
    "https://real.discount/feed/",
    "https://www.discudemy.com/feed",
    "https://www.udemyfreebies.com/feed/",
    "https://couponscorpion.com/feed/",
    "https://www.onlinecoursesite.com/feed/",
]

# --- تصنيف الكورسات ---
CATEGORIES = {
    "🤖 ذكاء اصطناعي": ["ai", "artificial intelligence", "machine learning", "deep learning", "chatgpt", "llm", "neural", "nlp", "computer vision", "generative"],
    "💻 برمجة": ["python", "javascript", "java", "programming", "coding", "developer", "software", "web development", "react", "node", "django", "flask"],
    "🎨 تصميم": ["design", "photoshop", "illustrator", "figma", "ui", "ux", "graphic", "canva", "adobe"],
    "📈 بيزنس وفريلانسر": ["business", "freelance", "marketing", "seo", "entrepreneur", "productivity", "management", "finance"],
    "📱 تطوير تطبيقات": ["android", "ios", "flutter", "swift", "kotlin", "mobile", "app development"],
    "🔐 أمن معلومات": ["cybersecurity", "hacking", "ethical hacking", "security", "network"],
    "📊 بيانات": ["data science", "data analysis", "excel", "sql", "tableau", "power bi", "statistics"],
    "🎬 فيديو وصوت": ["video editing", "premiere", "after effects", "youtube", "podcast", "audio"],
    "⚙️ أتمتة": ["automation", "n8n", "zapier", "make", "workflow", "automate"],
}

DB_FILE = "sent_coupons.txt"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

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
                return f"⚠️ نُشر منذ {int(hours)} ساعة"
            elif hours > 1:
                return f"⏰ نُشر منذ {int(hours)} ساعات"
            else:
                return f"🆕 نُشر منذ {int(hours*60)} دقيقة"
    except:
        pass
    return "🆕 جديد"

def get_popularity(num_students):
    if num_students >= 50000:
        return "🔥 مشهور جداً"
    elif num_students >= 10000:
        return "⭐ محبوب"
    elif num_students >= 1000:
        return "📈 في تصاعد"
    else:
        return "🆕 جديد"

def format_duration(minutes):
    if not minutes:
        return None
    hours = minutes / 60
    if hours < 1:
        return f"{int(minutes)} دقيقة"
    return f"{hours:.1f} ساعة"

def extract_coupon_code(url):
    """استخراج كود الكوبون من الرابط"""
    match = re.search(r'couponCode=([^&]+)', url)
    if match:
        return match.group(1)
    return None

def get_udemy_slug(url):
    """استخراج slug الكورس"""
    match = re.search(r'udemy\.com/course/([^/?]+)', url)
    if match:
        return match.group(1)
    return None

def scrape_udemy_page(course_url):
    """
    جلب كل معلومات الكورس والصورة مباشرة من صفحة Udemy
    هذه الطريقة تضمن الحصول على الصورة دائماً
    """
    try:
        r = requests.get(course_url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, 'html.parser')
        data = {}

        # --- الصورة (3 طرق مختلفة لضمان الحصول عليها) ---

        # الطريقة 1: og:image (الأكثر موثوقية)
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            data['image'] = og_image['content']

        # الطريقة 2: twitter:image
        if not data.get('image'):
            tw_image = soup.find('meta', attrs={'name': 'twitter:image'})
            if tw_image and tw_image.get('content'):
                data['image'] = tw_image['content']

        # الطريقة 3: أول صورة في الصفحة بحجم كبير
        if not data.get('image'):
            imgs = soup.find_all('img')
            for img in imgs:
                src = img.get('src', '')
                if 'udemy' in src and ('480x270' in src or '240x135' in src or 'course' in src):
                    data['image'] = src
                    break

        # --- التقييم ---
        rating_meta = soup.find('meta', attrs={'name': 'rating'})
        if rating_meta:
            data['rating'] = rating_meta.get('content', '')

        # --- النبذة ---
        desc_meta = soup.find('meta', attrs={'name': 'description'})
        if desc_meta:
            data['description'] = desc_meta.get('content', '')

        og_desc = soup.find('meta', property='og:description')
        if og_desc and not data.get('description'):
            data['description'] = og_desc.get('content', '')

        # --- JSON-LD للحصول على كل البيانات ---
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                import json
                json_data = json.loads(script.string)
                if isinstance(json_data, dict):
                    if json_data.get('@type') == 'Course':
                        if not data.get('image') and json_data.get('image'):
                            data['image'] = json_data['image']
                        if json_data.get('aggregateRating'):
                            data['rating'] = json_data['aggregateRating'].get('ratingValue', '')
                            data['review_count'] = json_data['aggregateRating'].get('reviewCount', '')
                        if json_data.get('description'):
                            data['description'] = json_data['description']
            except:
                continue

        print(f"✅ Scraped: image={'found' if data.get('image') else 'NOT found'}")
        return data

    except Exception as e:
        print(f"❌ Scrape error: {e}")
        return None

def verify_coupon(slug, coupon_code):
    """التحقق من صلاحية الكوبون عبر Udemy API"""
    try:
        api_url = f"https://www.udemy.com/api-2.0/courses/{slug}/"
        params = {
            "fields[course]": "rating,num_reviews,num_subscribers,content_length_video,price,discount_price,image_480x270",
            "couponCode": coupon_code
        }
        r = requests.get(api_url, params=params, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            d = r.json()
            price = d.get('discount_price', d.get('price', ''))
            # إذا السعر بعد الخصم = 0 أو Free = الكوبون صالح
            is_free = (
                str(price) == '0' or
                str(price) == '0.0' or
                'free' in str(price).lower() or
                price == 0
            )
            return is_free, d
    except Exception as e:
        print(f"❌ Verify error: {e}")
    return False, None

def send_with_photo(image_url, caption):
    """إرسال مع صورة"""
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
        else:
            print(f"⚠️ Photo failed: {r.text}")
            return False
    except Exception as e:
        print(f"❌ Photo error: {e}")
        return False

def send_text(caption):
    """إرسال نصي فقط"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": caption,
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

def is_100_percent(title, summary):
    text = (title + " " + summary).lower()
    return any(kw in text for kw in ["100% off", "free", "100%", "مجاني", "مجانا"])

def fetch_coupons():
    print(f"\n🎓 جلب كوبونات Udemy — {datetime.datetime.now().strftime('%H:%M')}")
    sent = load_sent()
    new_count = 0

    for feed_url in COUPON_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            print(f"\n📡 {feed_url} — {len(feed.entries)} كورس")

            for entry in feed.entries[:8]:
                try:
                    link = entry.get("link", "")
                    title = entry.get("title", "")
                    summary_raw = clean(entry.get("summary", entry.get("description", "")))

                    if not link or link in sent:
                        continue
                    if not is_english_or_arabic(title):
                        continue
                    if not is_100_percent(title, summary_raw):
                        continue

                    # استخراج slug وكود الكوبون
                    slug = get_udemy_slug(link)
                    coupon_code = extract_coupon_code(link)

                    if not slug:
                        continue

                    # بناء رابط مباشر بدون إعلانات
                    if coupon_code:
                        direct_link = f"https://www.udemy.com/course/{slug}/?couponCode={coupon_code}"
                    else:
                        direct_link = f"https://www.udemy.com/course/{slug}/"

                    # التحقق من صلاحية الكوبون
                    is_valid = True
                    api_data = None
                    if coupon_code:
                        is_valid, api_data = verify_coupon(slug, coupon_code)
                        if not is_valid:
                            print(f"❌ Expired coupon: {title[:40]}")
                            save_sent(link)
                            continue

                    print(f"✅ Valid coupon: {title[:40]}")

                    # جلب صورة وبيانات الكورس من الصفحة مباشرة
                    page_data = scrape_udemy_page(direct_link)

                    # --- بناء المعلومات ---
                    category = get_category(title)
                    time_str = get_time_str(entry.get("published_parsed"))

                    # الصورة
                    image_url = None
                    if page_data and page_data.get('image'):
                        image_url = page_data['image']

                    # النبذة
                    description = ""
                    if page_data and page_data.get('description'):
                        description = page_data['description'][:300]
                    elif summary_raw:
                        description = summary_raw

                    # ترجمة النبذة إذا إنجليزية
                    if description and not is_arabic(title):
                        description = translate(description)

                    # بيانات من API
                    rating_text = ""
                    students_text = ""
                    duration_text = ""
                    price_text = ""
                    popularity = ""
                    priority = ""

                    if api_data:
                        rating = api_data.get('rating', 0)
                        num_reviews = api_data.get('num_reviews', 0)
                        num_students = api_data.get('num_subscribers', 0)
                        duration_mins = api_data.get('content_length_video', 0)
                        original_price = api_data.get('price', '')
                        img_api = api_data.get('image_480x270', '')

                        # استخدام صورة API إذا لم نحصل عليها من الصفحة
                        if img_api and not image_url:
                            image_url = img_api

                        if rating and rating < 4.0:
                            save_sent(link)
                            continue

                        if rating:
                            rating_text = f"⭐ التقييم: *{rating:.1f}*"
                            if num_reviews:
                                rating_text += f" ({num_reviews:,} تقييم)"
                        if num_students:
                            popularity = get_popularity(num_students)
                            students_text = f"👨‍🎓 الطلاب: *{num_students:,}* طالب | {popularity}\n"
                        if duration_mins:
                            dur = format_duration(duration_mins)
                            if dur:
                                duration_text = f"⏱️ المدة: {dur}\n"
                        if original_price and str(original_price) not in ['0', 'Free', 'free']:
                            price_text = f"💰 السعر الأصلي: *{original_price}* — الآن مجاني!\n"
                        if rating >= 4.5 and num_students >= 10000:
                            priority = "⚡ *كورس مميز — لا تفوته!*\n"

                    # بناء الرسالة النهائية
                    caption = (
                        f"{priority}"
                        f"{category} — *مجاني 100%* 🎁\n\n"
                        f"📚 *{title}*\n\n"
                        f"📝 {description}\n\n"
                        f"{rating_text}\n"
                        f"{students_text}"
                        f"{duration_text}"
                        f"{price_text}"
                        f"{time_str}\n\n"
                        f"🔗 [احصل على الكورس مجاناً]({direct_link})"
                    )

                    # إرسال مع صورة مضمونة
                    sent_ok = False
                    if image_url:
                        print(f"🖼️ Sending with image: {image_url[:60]}")
                        sent_ok = send_with_photo(image_url, caption)

                    if not sent_ok:
                        print("📝 Sending text only...")
                        send_text(caption)

                    save_sent(link)
                    new_count += 1
                    time.sleep(3)

                except Exception as e:
                    print(f"❌ Entry error: {e}")
                    continue

        except Exception as e:
            print(f"❌ Feed error {feed_url}: {e}")

    print(f"\n✅ تم إرسال {new_count} كورس جديد")

def main():
    print("=" * 40)
    print("🎓 بوت كوبونات Udemy المطور")
    print(f"⏰ {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 40)
    fetch_coupons()
    print("\n✅ انتهى!")

if __name__ == "__main__":
    main()
