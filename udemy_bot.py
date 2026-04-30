import feedparser
import requests
import time
import re
import os
import datetime
import json
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup

# --- الإعدادات ---
TOKEN = "8787606333:AAE2Vs2Gq1fVaJtgl3vGYypTN_bqA1FkB-M"
CHAT_ID = "1934770017"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# --- مصادر RSS المباشرة (رابط Udemy مباشرة) ---
RSS_DIRECT = [
    "https://www.tutorialbar.com/all-courses/feed/",
    "https://real.discount/feed/",
]

# --- مصادر RSS غير المباشرة (نستخرج الرابط من الصفحة) ---
RSS_INDIRECT = [
    "https://www.discudemy.com/feed",
    "https://www.udemyfreebies.com/feed/",
    "https://couponscorpion.com/feed/",
    "https://freebiesglobal.com/feed/",
    "https://www.onlinecoursesite.com/feed/",
]

# --- تصنيف الكورسات ---
CATEGORIES = {
    "🤖 ذكاء اصطناعي": ["ai", "artificial intelligence", "machine learning", "deep learning", "chatgpt", "llm", "neural", "nlp", "computer vision", "generative", "gpt"],
    "💻 برمجة": ["python", "javascript", "java", "programming", "coding", "developer", "software", "web", "react", "node", "django", "flask", "typescript"],
    "🎨 تصميم": ["design", "photoshop", "illustrator", "figma", "ui", "ux", "graphic", "canva", "adobe", "sketch"],
    "📈 بيزنس": ["business", "freelance", "marketing", "seo", "entrepreneur", "productivity", "management", "finance", "accounting", "trading"],
    "📱 تطبيقات": ["android", "ios", "flutter", "swift", "kotlin", "mobile", "app development"],
    "🔐 أمن معلومات": ["cybersecurity", "hacking", "ethical hacking", "security", "network", "penetration"],
    "📊 بيانات": ["data science", "data analysis", "excel", "sql", "tableau", "power bi", "statistics", "pandas"],
    "🎬 فيديو": ["video editing", "premiere", "after effects", "youtube", "podcast", "filmmaking"],
    "⚙️ أتمتة": ["automation", "n8n", "zapier", "make", "workflow", "automate"],
    "🗣️ لغات": ["english", "arabic", "spanish", "language", "ielts", "toefl", "communication"],
}

DB_FILE = "sent_coupons.txt"
MAX_HOURS = 24  # رفض الكوبونات الأقدم من 6 ساعات

def load_sent():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_sent(link):
    with open(DB_FILE, "a") as f:
        f.write(link + "\n")

def translate_text(text):
    try:
        if not text: return ""
        return GoogleTranslator(source='auto', target='ar').translate(text[:400])
    except:
        return text

def is_arabic_text(text):
    return bool(re.search(r'[\u0600-\u06FF]', text))

def get_language_flag(title):
    """تحديد علم اللغة حسب الكورس"""
    if is_arabic_text(title):
        return "🇸🇦"
    return "🇬🇧"

def is_english_or_arabic(text):
    other = re.search(r'[\u0900-\u097F\u4E00-\u9FFF\u3040-\u309F\u0400-\u04FF]', text)
    if other:
        return False
    text_lower = text.lower()
    non_english_words = [
        'fur', 'und', 'mit', 'von', 'auf', 'der', 'die', 'das', 'ein', 'eine',
        'ist', 'sind', 'werden', 'nicht', 'auch', 'zum', 'zur', 'beim', 'vom',
        'dem', 'den', 'des', 'grundlagen', 'komplett', 'lernen', 'schritt',
        'pour', 'avec', 'dans', 'les', 'une', 'sur', 'par', 'qui',
        'que', 'est', 'sont', 'cours', 'apprendre', 'formation', 'debutant',
        'desde', 'curso', 'aprende', 'completo', 'espanol', 'guia',
        'aprenda', 'portugues', 'italiano', 'dalla', 'impara',
        'icin', 'ile', 'ogren', 'kurs',
    ]
    words = text_lower.split()
    if sum(1 for w in words if w in non_english_words) >= 1:
        return False
    return bool(re.search(r'[a-zA-Z\u0600-\u06FF]', text))

def get_category(title):
    title_lower = title.lower()
    for category, keywords in CATEGORIES.items():
        if any(kw in title_lower for kw in keywords):
            return category
    return "📚 تعليم عام"

def get_coupon_age_hours(published):
    try:
        if published:
            pub_time = datetime.datetime(*published[:6])
            diff = datetime.datetime.now() - pub_time
            return diff.total_seconds() / 3600
    except:
        pass
    return 0

def is_coupon_fresh(published):
    age = get_coupon_age_hours(published)
    if age == 0:
        return True
    return age <= MAX_HOURS

def get_time_str(published):
    try:
        hours = get_coupon_age_hours(published)
        if hours == 0:
            return "🆕 جديد"
        elif hours < 1:
            return f"🆕 نُشر منذ {int(hours*60)} دقيقة"
        elif hours < 6:
            return f"⏰ نُشر منذ {int(hours)} ساعات"
        else:
            return f"⚠️ نُشر منذ {int(hours)} ساعة"
    except:
        return "🆕 جديد"

def get_priority_badge(rating, num_students):
    """تحديد شارة الأولوية"""
    try:
        r = float(rating) if rating else 0
        s = int(num_students) if num_students else 0
        if r >= 4.5 and s >= 10000:
            return "⚡ *كورس مميز جداً*"
        elif s >= 10000:
            return "🔥 *كورس رائج*"
        elif r >= 4.5:
            return "⭐ *كورس عالي التقييم*"
        elif s < 1000:
            return "🆕 *كورس جديد*"
    except:
        pass
    return ""

def clean_html(text):
    if not text: return ""
    text = re.sub('<[^<]+?>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# ==========================================
# استخراج رابط Udemy من مواقع الوسيطة
# ==========================================
def extract_udemy_link_from_page(page_url):
    try:
        r = requests.get(page_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None, False
        html = r.text
        soup = BeautifulSoup(html, 'html.parser')

        # التحقق من انتهاء الكوبون
        page_text_lower = soup.get_text().lower()
        expired_keywords = ['expired', 'coupon expired', 'this coupon expired', 'sorry', 'you are late']
        if any(kw in page_text_lower for kw in expired_keywords):
            print(f"❌ Expired coupon")
            return None, False

        # البحث عن رابط Udemy مع كوبون
        patterns = [
            r'https?://(?:www\.)?udemy\.com/course/[^\s"\'<>\)]+couponCode=[^\s"\'<>\)&]+',
            r'https?://(?:www\.)?udemy\.com/course/[^\s"\'<>\)]+',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, html)
            for match in matches:
                clean_url = match.rstrip('.,;)"\'')
                if 'udemy.com/course/' in clean_url:
                    print(f"✅ Udemy link: {clean_url[:70]}")
                    return clean_url, True

        # البحث في الروابط
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'udemy.com/course/' in href:
                return href.rstrip('.,;)"\''), True

    except Exception as e:
        print(f"❌ Extract error: {e}")
    return None, False

# ==========================================
# جلب معلومات الكورس من Udemy
# ==========================================
def get_course_info(udemy_url):
    info = {
        'image': None,
        'description': None,
        'rating': None,
        'num_students': None,
        'duration_hours': None,
        'num_lectures': None,
        'original_price': None,
        'is_expired': False
    }
    try:
        r = requests.get(udemy_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return info

        soup = BeautifulSoup(r.text, 'html.parser')
        page_text = soup.get_text().lower()

        # التحقق من انتهاء الكوبون
        if 'coupon not found' in page_text or 'coupon has expired' in page_text:
            info['is_expired'] = True
            return info

        html = r.text

        # --- الصورة ---
        og_img = soup.find('meta', property='og:image')
        if og_img and og_img.get('content'):
            info['image'] = og_img['content']

        if not info['image']:
            tw_img = soup.find('meta', attrs={'name': 'twitter:image'})
            if tw_img and tw_img.get('content'):
                info['image'] = tw_img['content']

        # --- JSON-LD للبيانات الكاملة ---
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string or '')
                if isinstance(data, dict):
                    if not info['image'] and data.get('image'):
                        info['image'] = data['image']
                    if data.get('aggregateRating'):
                        info['rating'] = data['aggregateRating'].get('ratingValue', '')
                    if data.get('description'):
                        info['description'] = data['description'][:400]
            except:
                continue

        # --- الوصف ---
        if not info['description']:
            desc = soup.find('meta', attrs={'name': 'description'})
            if desc and desc.get('content'):
                info['description'] = desc['content'][:400]

        if not info['description']:
            og_desc = soup.find('meta', property='og:description')
            if og_desc and og_desc.get('content'):
                info['description'] = og_desc['content'][:400]

        # --- بيانات من الصفحة (عدد الطلاب، المدة، السعر) ---
        # عدد الطلاب
        students_match = re.search(r'([\d,]+)\s*(?:students?|learners?|enrolled)', html, re.IGNORECASE)
        if students_match:
            info['num_students'] = students_match.group(1).replace(',', '')

        # المدة والمحاضرات
        duration_match = re.search(r'(\d+\.?\d*)\s*(?:total hours?|hours? total)', html, re.IGNORECASE)
        if duration_match:
            info['duration_hours'] = duration_match.group(1)

        lectures_match = re.search(r'(\d+)\s*lectures?', html, re.IGNORECASE)
        if lectures_match:
            info['num_lectures'] = lectures_match.group(1)

        # السعر الأصلي
        price_match = re.search(r'\$(\d+\.?\d*)', html)
        if price_match:
            info['original_price'] = f"${price_match.group(1)}"

        print(f"📊 img:{'✅' if info['image'] else '❌'} desc:{'✅' if info['description'] else '❌'} rating:{info['rating']} students:{info['num_students']}")

    except Exception as e:
        print(f"❌ Course info error: {e}")
    return info

# ==========================================
# إرسال التيليجرام
# ==========================================
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
        print(f"⚠️ Photo failed {r.status_code}")
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

# ==========================================
# بناء وإرسال الرسالة
# ==========================================
def build_and_send(title, udemy_url, time_str, published):
    info = get_course_info(udemy_url)

    if info.get('is_expired'):
        print(f"❌ Expired on Udemy")
        return False

    # علم اللغة والتصنيف
    flag = get_language_flag(title)
    category = get_category(title)

    # الوصف مترجم
    description = info.get('description', '')
    if not description:
        description = "كورس تعليمي متميز على منصة Udemy"
    if description and not is_arabic_text(description):
        description = translate_text(description)

    # شارة الأولوية
    priority = get_priority_badge(info.get('rating'), info.get('num_students'))

    # بناء الرسالة بشكل احترافي
    lines = []

    if priority:
        lines.append(f"{priority}\n")

    lines.append(f"{flag} *{title}*")
    lines.append(f"🎁 *كورس مجاني 100%*\n")
    lines.append(f"📝 {description}\n")

    if info.get('rating'):
        lines.append(f"⭐ التقييم: *{info['rating']}*")

    lines.append(f"📚 المجال: {category}")

    if info.get('duration_hours') and info.get('num_lectures'):
        lines.append(f"⏰ مدة الكورس: *{info['duration_hours']} ساعة* ({info['num_lectures']} محاضرة)")
    elif info.get('duration_hours'):
        lines.append(f"⏰ مدة الكورس: *{info['duration_hours']} ساعة*")

    if info.get('num_students'):
        try:
            s = int(info['num_students'])
            lines.append(f"👥 عدد الطلاب: *{s:,}*")
        except:
            lines.append(f"👥 عدد الطلاب: *{info['num_students']}*")

    if info.get('original_price'):
        lines.append(f"💰 السعر الأصلي: *{info['original_price']}* — الآن مجاني!")

    lines.append(f"{time_str}\n")
    lines.append(f"🔗 [اضغط هنا للتسجيل المجاني]({udemy_url})")

    caption = "\n".join(lines)

    # إرسال مع صورة أو بدون
    image = info.get('image')
    if image:
        success = send_with_photo(image, caption)
        if not success:
            send_text(caption)
    else:
        send_text(caption)

    return True

# ==========================================
# معالجة RSS المباشر
# ==========================================
def process_direct_feeds():
    print("\n🔗 RSS المباشر...")
    sent = load_sent()
    count = 0

    for feed_url in RSS_DIRECT:
        try:
            feed = feedparser.parse(feed_url)
            print(f"📡 {feed_url} — {len(feed.entries)} كورس")

            for entry in feed.entries[:10]:
                link = entry.get("link", "")
                title = entry.get("title", "")
                summary = clean_html(entry.get("summary", ""))
                published = entry.get("published_parsed")

                if not link or link in sent:
                    continue
                if not is_english_or_arabic(title):
                    continue
                if not is_coupon_fresh(published):
                    print(f"⏭️ Too old: {title[:40]}")
                    save_sent(link)
                    continue

                # البحث عن رابط Udemy مباشر
                full_text = summary + " " + link
                udemy_match = re.search(
                    r'https?://(?:www\.)?udemy\.com/course/[^\s"\'<>]+',
                    full_text
                )
                udemy_url = udemy_match.group(0).rstrip('.,;)"\'') if udemy_match else link

                if 'udemy.com' not in udemy_url:
                    continue

                time_str = get_time_str(published)
                print(f"\n📘 {title[:50]}")

                success = build_and_send(title, udemy_url, time_str, published)
                save_sent(link)
                if success:
                    count += 1
                time.sleep(3)

        except Exception as e:
            print(f"❌ {feed_url}: {e}")

    return count

# ==========================================
# معالجة RSS غير المباشر
# ==========================================
def process_indirect_feeds():
    print("\n🔍 RSS غير المباشر...")
    sent = load_sent()
    count = 0

    for feed_url in RSS_INDIRECT:
        try:
            feed = feedparser.parse(feed_url)
            print(f"📡 {feed_url} — {len(feed.entries)} كورس")

            for entry in feed.entries[:8]:
                link = entry.get("link", "")
                title = entry.get("title", "")
                published = entry.get("published_parsed")

                if not link or link in sent:
                    continue
                if not is_english_or_arabic(title):
                    continue
                if not is_coupon_fresh(published):
                    print(f"⏭️ Too old: {title[:40]}")
                    save_sent(link)
                    continue

                print(f"\n📘 {title[:50]}")
                print(f"🌐 {link[:60]}")

                udemy_url, is_valid = extract_udemy_link_from_page(link)
                if not is_valid or not udemy_url:
                    save_sent(link)
                    continue

                time_str = get_time_str(published)
                success = build_and_send(title, udemy_url, time_str, published)
                save_sent(link)
                if success:
                    count += 1
                time.sleep(4)

        except Exception as e:
            print(f"❌ {feed_url}: {e}")

    return count

# ==========================================
# التشغيل الرئيسي
# ==========================================
def main():
    print("=" * 45)
    print("🎓 بوت كوبونات Udemy الاحترافي")
    print(f"⏰ {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 45)

    total = 0
    total += process_direct_feeds()
    total += process_indirect_feeds()

    print(f"\n✅ تم إرسال {total} كورس جديد")
    print("=" * 45)

if __name__ == "__main__":
    main()
