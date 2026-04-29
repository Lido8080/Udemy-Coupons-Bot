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

# --- مصادر RSS ---
RSS_DIRECT = [
    "https://www.tutorialbar.com/all-courses/feed/",
    "https://real.discount/feed/",
]

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
    "📈 بيزنس": ["business", "freelance", "marketing", "seo", "entrepreneur", "productivity", "management", "finance", "accounting"],
    "📱 تطبيقات": ["android", "ios", "flutter", "swift", "kotlin", "mobile", "app development"],
    "🔐 أمن معلومات": ["cybersecurity", "hacking", "ethical hacking", "security", "network", "penetration"],
    "📊 بيانات": ["data science", "data analysis", "excel", "sql", "tableau", "power bi", "statistics", "pandas"],
    "🎬 فيديو": ["video editing", "premiere", "after effects", "youtube", "podcast", "filmmaking"],
    "⚙️ أتمتة": ["automation", "n8n", "zapier", "make", "workflow", "automate"],
    "🗣️ لغات": ["english", "arabic", "spanish", "language", "ielts", "toefl", "communication"],
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

def translate_text(text):
    try:
        if not text: return ""
        return GoogleTranslator(source='auto', target='ar').translate(text[:400])
    except:
        return text

def is_arabic(text):
    return bool(re.search(r'[\u0600-\u06FF]', text))

def is_english_or_arabic(text):
    # رفض اللغات ذات أحرف خاصة
    other = re.search(r'[\u0900-\u097F\u4E00-\u9FFF\u3040-\u309F\u0400-\u04FF]', text)
    if other:
        return False

    text_lower = text.lower()

    # كلمات تدل على لغات أخرى — ألمانية، فرنسية، إسبانية، برتغالية، إيطالية، تركية
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
    non_en_count = sum(1 for w in words if w in non_english_words)

    if non_en_count >= 1:
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

def is_coupon_fresh(published, max_hours=2):
    age = get_coupon_age_hours(published)
    if age == 0:
        return True
    return age <= max_hours

def get_time_str(published):
    try:
        if published:
            hours = get_coupon_age_hours(published)
            if hours > 12:
                return f"⚠️ نُشر منذ {int(hours)} ساعة"
            elif hours > 1:
                return f"⏰ نُشر منذ {int(hours)} ساعات"
            else:
                mins = int(hours * 60)
                return f"🆕 نُشر منذ {mins} دقيقة"
    except:
        pass
    return "🆕 جديد"

def clean_html(text):
    if not text: return ""
    text = re.sub('<[^<]+?>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# ==========================================
# استخراج رابط Udemy من مواقع الوسيطة
# ==========================================
def extract_udemy_link_from_page(page_url):
    """زيارة صفحة الموقع واستخراج رابط Udemy + التحقق من الصلاحية"""
    try:
        r = requests.get(page_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None, False

        html = r.text
        soup = BeautifulSoup(html, 'html.parser')

        # التحقق من انتهاء الكوبون
        expired_keywords = ['expired', 'coupon expired', 'this coupon expired', 'sorry', 'you are late']
        page_text_lower = soup.get_text().lower()
        if any(kw in page_text_lower for kw in expired_keywords):
            print(f"❌ Expired coupon detected")
            return None, False

        # البحث عن رابط Udemy في الصفحة
        udemy_patterns = [
            r'https?://(?:www\.)?udemy\.com/course/[^\s"\'<>\)]+couponCode=[^\s"\'<>\)]+',
            r'https?://(?:www\.)?udemy\.com/course/[^\s"\'<>\)]+',
        ]

        for pattern in udemy_patterns:
            matches = re.findall(pattern, html)
            for match in matches:
                # تنظيف الرابط
                clean_url = match.rstrip('.,;)')
                if 'udemy.com/course/' in clean_url:
                    print(f"✅ Found Udemy link: {clean_url[:70]}")
                    return clean_url, True

        # البحث في الروابط
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'udemy.com/course/' in href:
                clean_url = href.rstrip('.,;)')
                print(f"✅ Found Udemy link in anchor: {clean_url[:70]}")
                return clean_url, True

    except Exception as e:
        print(f"❌ Extract error: {e}")
    return None, False

# ==========================================
# جلب معلومات الكورس من Udemy مباشرة
# ==========================================
def get_course_info(udemy_url):
    """جلب صورة + وصف + تقييم من صفحة Udemy"""
    info = {
        'image': None,
        'description': None,
        'rating': None,
        'is_expired': False
    }
    try:
        r = requests.get(udemy_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return info

        soup = BeautifulSoup(r.text, 'html.parser')

        # التحقق من انتهاء الكوبون على صفحة Udemy
        page_text = soup.get_text().lower()
        if 'coupon not found' in page_text or 'coupon has expired' in page_text:
            info['is_expired'] = True
            return info

        # --- الصورة (4 طرق) ---
        # الطريقة 1: og:image
        og_img = soup.find('meta', property='og:image')
        if og_img and og_img.get('content'):
            info['image'] = og_img['content']

        # الطريقة 2: twitter:image
        if not info['image']:
            tw_img = soup.find('meta', attrs={'name': 'twitter:image'})
            if tw_img and tw_img.get('content'):
                info['image'] = tw_img['content']

        # الطريقة 3: JSON-LD
        if not info['image']:
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    data = json.loads(script.string or '')
                    if isinstance(data, dict):
                        if data.get('image'):
                            info['image'] = data['image']
                            break
                        if data.get('@graph'):
                            for item in data['@graph']:
                                if item.get('image'):
                                    info['image'] = item['image']
                                    break
                except:
                    continue

        # الطريقة 4: img tag
        if not info['image']:
            for img in soup.find_all('img'):
                src = img.get('src', '')
                if 'udemy' in src and ('480x270' in src or '240x135' in src or 'course_image' in src):
                    info['image'] = src
                    break

        # --- الوصف ---
        desc = soup.find('meta', attrs={'name': 'description'})
        if desc and desc.get('content'):
            info['description'] = desc['content'][:350]

        if not info['description']:
            og_desc = soup.find('meta', property='og:description')
            if og_desc and og_desc.get('content'):
                info['description'] = og_desc['content'][:350]

        # --- التقييم ---
        rating_meta = soup.find('meta', attrs={'name': 'rating'})
        if rating_meta:
            info['rating'] = rating_meta.get('content', '')

        print(f"📊 Image: {'✅' if info['image'] else '❌'} | Desc: {'✅' if info['description'] else '❌'}")

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
        print(f"⚠️ Photo failed {r.status_code}: {r.text[:100]}")
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

def build_and_send(title, udemy_url, time_str, category, published_time):
    """بناء الرسالة وإرسالها"""
    # جلب معلومات الكورس من Udemy
    info = get_course_info(udemy_url)

    if info.get('is_expired'):
        print(f"❌ Coupon expired on Udemy: {title[:40]}")
        return False

    # الوصف
    description = info.get('description', '')
    if not description:
        description = "كورس تعليمي متميز على منصة Udemy"

    # ترجمة الوصف إذا إنجليزي
    if description and not is_arabic(description):
        description = translate_text(description)

    # تحديد الأولوية
    priority = ""
    if info.get('rating'):
        try:
            if float(info['rating']) >= 4.5:
                priority = "⚡ *كورس مميز — لا تفوته!*\n"
        except:
            pass

    # بناء الرسالة
    caption = (
        f"{priority}"
        f"{category} — *مجاني 100%* 🎁\n\n"
        f"📚 *{title}*\n\n"
        f"📝 {description}\n\n"
    )

    if info.get('rating'):
        caption += f"⭐ التقييم: *{info['rating']}*\n"

    caption += (
        f"{time_str}\n\n"
        f"🔗 [احصل على الكورس مجاناً]({udemy_url})"
    )

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
# معالجة RSS المباشر (tutorialbar, real.discount)
# ==========================================
def process_direct_feeds():
    print("\n🔗 معالجة RSS المباشر...")
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

                if not link or link in sent:
                    continue
                if not is_english_or_arabic(title):
                    continue

                # رفض الكوبونات القديمة (أكثر من ساعتين)
                if not is_coupon_fresh(entry.get("published_parsed")):
                    print(f"⏭️ Too old, skipping: {title[:40]}")
                    save_sent(link)
                    continue

                # البحث عن رابط Udemy في المحتوى مباشرة
                full_content = summary + " " + link
                udemy_match = re.search(
                    r'https?://(?:www\.)?udemy\.com/course/[^\s"\'<>]+',
                    full_content
                )

                if udemy_match:
                    udemy_url = udemy_match.group(0).rstrip('.,;)')
                else:
                    udemy_url = link

                if 'udemy.com' not in udemy_url:
                    continue

                category = get_category(title)
                time_str = get_time_str(entry.get("published_parsed"))

                print(f"\n📘 {title[:50]}")
                success = build_and_send(title, udemy_url, time_str, category, entry.get("published_parsed"))

                save_sent(link)
                if success:
                    count += 1
                time.sleep(3)

        except Exception as e:
            print(f"❌ Feed error {feed_url}: {e}")

    return count

# ==========================================
# معالجة RSS غير المباشر
# ==========================================
def process_indirect_feeds():
    print("\n🔍 معالجة RSS غير المباشر...")
    sent = load_sent()
    count = 0

    for feed_url in RSS_INDIRECT:
        try:
            feed = feedparser.parse(feed_url)
            print(f"📡 {feed_url} — {len(feed.entries)} كورس")

            for entry in feed.entries[:8]:
                link = entry.get("link", "")
                title = entry.get("title", "")

                if not link or link in sent:
                    continue
                if not is_english_or_arabic(title):
                    continue

                # رفض الكوبونات القديمة (أكثر من ساعتين)
                if not is_coupon_fresh(entry.get("published_parsed")):
                    print(f"⏭️ Too old, skipping: {title[:40]}")
                    save_sent(link)
                    continue

                print(f"\n📘 {title[:50]}")
                print(f"🌐 Visiting: {link[:60]}")

                # استخراج رابط Udemy من صفحة الموقع
                udemy_url, is_valid = extract_udemy_link_from_page(link)

                if not is_valid or not udemy_url:
                    print(f"⏭️ Skipping: no valid Udemy link found")
                    save_sent(link)
                    continue

                category = get_category(title)
                time_str = get_time_str(entry.get("published_parsed"))

                success = build_and_send(title, udemy_url, time_str, category, entry.get("published_parsed"))

                save_sent(link)
                if success:
                    count += 1
                time.sleep(4)

        except Exception as e:
            print(f"❌ Feed error {feed_url}: {e}")

    return count

# ==========================================
# التشغيل الرئيسي
# ==========================================
def main():
    print("=" * 45)
    print("🎓 بوت كوبونات Udemy المطور")
    print(f"⏰ {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 45)

    total = 0
    total += process_direct_feeds()
    total += process_indirect_feeds()

    print(f"\n✅ تم إرسال {total} كورس جديد")
    print("=" * 45)

if __name__ == "__main__":
    main()
