"""
Testare 6 metode separate de bypass Cloudflare
Sursa: https://roundproxies.com/blog/bypass-cloudflare/

Fiecare metodă va fi testată individual pe casehug.com/free-cases/discord
Screenshot-uri si HTML salvate în debug_output/ cu nume descriptive
"""

import asyncio
import os
import time
import requests
from datetime import datetime

# Folder pentru rezultate
DEBUG_DIR = "debug_output"
os.makedirs(DEBUG_DIR, exist_ok=True)

TARGET_URL = "https://casehug.com/free-cases/discord"
TEST_RESULTS = []

def save_result(method_name, success, error_msg="", duration=0):
    """Salvează rezultatul unui test"""
    result = {
        "method": method_name,
        "success": success,
        "error": error_msg,
        "duration_seconds": duration,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    TEST_RESULTS.append(result)
    
    status_icon = "✅" if success else "❌"
    print(f"\n{status_icon} {method_name}: {'SUCCESS' if success else 'FAILED'}")
    if error_msg:
        print(f"   Eroare: {error_msg}")
    print(f"   Durată: {duration:.2f}s")

# ============================================================================
# METODA 1: NODRIVER (Successor la undetected-chromedriver)
# ============================================================================

async def test_nodriver():
    """Metoda 1: Nodriver - stealth browser automation"""
    method_name = "METODA_1_NODRIVER"
    print(f"\n{'='*70}")
    print(f"🧪 Testez: {method_name}")
    print(f"   Descriere: Successor la undetected-chromedriver, comunică via DevTools Protocol")
    print(f"{'='*70}")
    
    start_time = time.time()
    
    try:
        # Verifică dacă nodriver este instalat
        try:
            import nodriver as uc
        except ImportError:
            print(f"📥 Instalez nodriver...")
            os.system("pip install nodriver")
            import nodriver as uc
        
        print(f"🌐 Lansez browser Nodriver...")
        browser = await uc.start(headless=False)
        
        print(f"🔗 Navighez la: {TARGET_URL}")
        page = await browser.get(TARGET_URL)
        
        print(f"⏳ Aștept 10 secunde pentru Cloudflare auto-resolve...")
        await page.sleep(10)
        
        # Salvează screenshot și HTML
        content = await page.get_content()
        timestamp = int(time.time())
        
        html_file = os.path.join(DEBUG_DIR, f"{method_name}_{timestamp}.html")
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Verifică dacă Cloudflare este prezent
        content_lower = content.lower()
        has_cloudflare = any(indicator in content_lower for indicator in [
            'cloudflare', 'just a moment', 'checking your browser', 'turnstile'
        ])
        
        if not has_cloudflare:
            print(f"✅ Cloudflare TRECUT!")
            save_result(method_name, True, duration=time.time() - start_time)
        else:
            print(f"❌ Cloudflare ÎNC ă PREZENT")
            save_result(method_name, False, "Cloudflare challenge nu a fost trecut", time.time() - start_time)
        
        await browser.stop()
        
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ Eroare: {e}")
        save_result(method_name, False, str(e), duration)

# ============================================================================
# METODA 2: SELENIUMBASE UC MODE
# ============================================================================

async def test_seleniumbase():
    """Metoda 2: SeleniumBase UC Mode - undetected-chromedriver integrat"""
    method_name = "METODA_2_SELENIUMBASE"
    print(f"\n{'='*70}")
    print(f"🧪 Testez: {method_name}")
    print(f"   Descriere: SeleniumBase cu UC mode și uc_gui_click_captcha()")
    print(f"{'='*70}")
    
    start_time = time.time()
    
    try:
        # Verifică instalare
        try:
            from seleniumbase import SB
        except ImportError:
            print(f"📥 Instalez seleniumbase...")
            os.system("pip install seleniumbase")
            from seleniumbase import SB
        
        print(f"🌐 Lansez browser SeleniumBase UC...")
        with SB(uc=True, headless=False) as sb:
            print(f"🔗 Navighez la: {TARGET_URL}")
            sb.uc_open_with_reconnect(TARGET_URL, 5)
            
            print(f"⏳ Aștept 5 secunde...")
            sb.sleep(5)
            
            # Încearcă să rezolve Turnstile dacă apare
            try:
                print(f"🎯 Încerc uc_gui_click_captcha()...")
                sb.uc_gui_click_captcha()
                sb.sleep(3)
            except:
                print(f"   (Nu s-a detectat Turnstile sau deja rezolvat)")
            
            # Salvează rezultate
            html = sb.get_page_source()
            timestamp = int(time.time())
            
            html_file = os.path.join(DEBUG_DIR, f"{method_name}_{timestamp}.html")
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html)
            
            # Verifică Cloudflare
            has_cloudflare = any(indicator in html.lower() for indicator in [
                'cloudflare', 'just a moment', 'checking your browser', 'turnstile'
            ])
            
            if not has_cloudflare:
                print(f"✅ Cloudflare TRECUT!")
                save_result(method_name, True, duration=time.time() - start_time)
            else:
                print(f"❌ Cloudflare ÎNCĂ PREZENT")
                save_result(method_name, False, "Cloudflare challenge nu a fost trecut", time.time() - start_time)
    
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ Eroare: {e}")
        save_result(method_name, False, str(e), duration)

# ============================================================================
# METODA 3: CAMOUFOX (Firefox-based anti-detect)
# ============================================================================

async def test_camoufox():
    """Metoda 3: Camoufox - Firefox-based anti-detect browser"""
    method_name = "METODA_3_CAMOUFOX"
    print(f"\n{'='*70}")
    print(f"🧪 Testez: {method_name}")
    print(f"   Descriere: Anti-detect browser bazat pe Firefox (alternativă la Chrome)")
    print(f"{'='*70}")
    
    start_time = time.time()
    
    try:
        # Verifică instalare
        try:
            from camoufox.sync_api import Camoufox
        except ImportError:
            print(f"📥 Instalez camoufox...")
            os.system("pip install camoufox[geoip]")
            os.system("python -m camoufox fetch")
            from camoufox.sync_api import Camoufox
        
        print(f"🌐 Lansez browser Camoufox...")
        with Camoufox(headless=False, humanize=True) as browser:
            page = browser.new_page()
            
            print(f"🔗 Navighez la: {TARGET_URL}")
            page.goto(TARGET_URL)
            
            print(f"⏳ Aștept network idle...")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(5000)
            
            # Salvează rezultate
            content = page.content()
            timestamp = int(time.time())
            
            html_file = os.path.join(DEBUG_DIR, f"{method_name}_{timestamp}.html")
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Verifică Cloudflare
            has_cloudflare = any(indicator in content.lower() for indicator in [
                'cloudflare', 'just a moment', 'checking your browser', 'turnstile'
            ])
            
            if not has_cloudflare:
                print(f"✅ Cloudflare TRECUT!")
                save_result(method_name, True, duration=time.time() - start_time)
            else:
                print(f"❌ Cloudflare ÎNCĂ PREZENT")
                save_result(method_name, False, "Cloudflare challenge nu a fost trecut", time.time() - start_time)
    
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ Eroare: {e}")
        save_result(method_name, False, str(e), duration)

# ============================================================================
# METODA 4: CURL-IMPERSONATE (curl_cffi - TLS fingerprint spoofing)
# ============================================================================

def test_curl_impersonate():
    """Metoda 4: Curl-Impersonate - HTTP-level bypass cu TLS spoofing"""
    method_name = "METODA_4_CURL_IMPERSONATE"
    print(f"\n{'='*70}")
    print(f"🧪 Testez: {method_name}")
    print(f"   Descriere: Patch TLS și HTTP fingerprints pentru a imita Chrome real")
    print(f"{'='*70}")
    
    start_time = time.time()
    
    try:
        # Verifică instalare
        try:
            from curl_cffi import requests as curl_requests
        except ImportError:
            print(f"📥 Instalez curl_cffi...")
            os.system("pip install curl_cffi")
            from curl_cffi import requests as curl_requests
        
        print(f"🔗 Fac request cu impersonate='chrome120'...")
        response = curl_requests.get(
            TARGET_URL,
            impersonate="chrome120",
            timeout=30
        )
        
        # Salvează rezultate
        timestamp = int(time.time())
        html_file = os.path.join(DEBUG_DIR, f"{method_name}_{timestamp}.html")
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        # Verifică Cloudflare
        has_cloudflare = any(indicator in response.text.lower() for indicator in [
            'cloudflare', 'just a moment', 'checking your browser', 'turnstile'
        ])
        
        if not has_cloudflare:
            print(f"✅ Cloudflare TRECUT! (HTTP {response.status_code})")
            save_result(method_name, True, duration=time.time() - start_time)
        else:
            print(f"❌ Cloudflare ÎNCĂ PREZENT (HTTP {response.status_code})")
            save_result(method_name, False, "Cloudflare challenge nu a fost trecut", time.time() - start_time)
    
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ Eroare: {e}")
        save_result(method_name, False, str(e), duration)

# ============================================================================
# METODA 5: CLOUDSCRAPER (Rezolvă JS challenges automat)
# ============================================================================

def test_cloudscraper():
    """Metoda 5: Cloudscraper - Auto-solve JS challenges"""
    method_name = "METODA_5_CLOUDSCRAPER"
    print(f"\n{'='*70}")
    print(f"🧪 Testez: {method_name}")
    print(f"   Descriere: Rezolvă JS challenges Cloudflare automat, gestionează cookies")
    print(f"{'='*70}")
    
    start_time = time.time()
    
    try:
        # Verifică instalare
        try:
            import cloudscraper
        except ImportError:
            print(f"📥 Instalez cloudscraper...")
            os.system("pip install cloudscraper")
            import cloudscraper
        
        print(f"🔗 Creez scraper și fac request...")
        scraper = cloudscraper.create_scraper()
        response = scraper.get(TARGET_URL, timeout=30)
        
        # Salvează rezultate
        timestamp = int(time.time())
        html_file = os.path.join(DEBUG_DIR, f"{method_name}_{timestamp}.html")
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        # Verifică Cloudflare
        has_cloudflare = any(indicator in response.text.lower() for indicator in [
            'cloudflare', 'just a moment', 'checking your browser', 'turnstile'
        ])
        
        if not has_cloudflare:
            print(f"✅ Cloudflare TRECUT! (HTTP {response.status_code})")
            save_result(method_name, True, duration=time.time() - start_time)
        else:
            print(f"❌ Cloudflare ÎNCĂ PREZENT (HTTP {response.status_code})")
            save_result(method_name, False, "Cloudflare challenge nu a fost trecut", time.time() - start_time)
    
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ Eroare: {e}")
        save_result(method_name, False, str(e), duration)

# ============================================================================
# METODA 6: FLARESOLVERR (Deja implementat în main.py)
# ============================================================================

def test_flaresolverr():
    """Metoda 6: FlareSolverr - Self-hosted proxy server"""
    method_name = "METODA_6_FLARESOLVERR"
    print(f"\n{'='*70}")
    print(f"🧪 Testez: {method_name}")
    print(f"   Descriere: Self-hosted proxy server cu Selenium + undetected-chromedriver")
    print(f"   📝 DEJA IMPLEMENTAT ÎN main.py! (Vezi test anterior)")
    print(f"{'='*70}")
    
    start_time = time.time()
    
    try:
        # Test FlareSolverr API
        print(f"🔗 Trimit request la FlareSolverr API...")
        payload = {
            "cmd": "request.get",
            "url": TARGET_URL,
            "maxTimeout": 60000
        }
        
        response = requests.post(
            "http://localhost:8191/v1",
            json=payload,
            timeout=65
        )
        
        if response.status_code != 200:
            save_result(method_name, False, f"HTTP {response.status_code}", time.time() - start_time)
            return
        
        result = response.json()
        
        if result.get('status') != 'ok':
            save_result(method_name, False, result.get('message', 'Unknown error'), time.time() - start_time)
            return
        
        solution = result.get('solution', {})
        html = solution.get('response', '')
        
        # Salvează rezultate
        timestamp = int(time.time())
        html_file = os.path.join(DEBUG_DIR, f"{method_name}_{timestamp}.html")
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html)
        
        # Verifică Cloudflare
        has_cloudflare = any(indicator in html.lower() for indicator in [
            'cloudflare', 'just a moment', 'checking your browser', 'turnstile'
        ])
        
        if not has_cloudflare:
            print(f"✅ Cloudflare TRECUT!")
            save_result(method_name, True, duration=time.time() - start_time)
        else:
            print(f"❌ Cloudflare ÎNCĂ PREZENT")
            save_result(method_name, False, "Cloudflare challenge nu a fost trecut", time.time() - start_time)
    
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ Eroare: {e}")
        save_result(method_name, False, str(e), duration)

# ============================================================================
# MAIN - Rulează toate testele
# ============================================================================

async def main():
    print(f"""
{'='*70}
🧪 TESTARE 6 METODE DE BYPASS CLOUDFLARE
{'='*70}
Target: {TARGET_URL}
Rezultate: {DEBUG_DIR}/
Sursa: https://roundproxies.com/blog/bypass-cloudflare/
{'='*70}

⚠️  IMPORTANT: 
   - Fiecare metodă va rula separat
   - Screenshot-urile vechi au fost șterse
   - Când te întorci, uită-te în {DEBUG_DIR}/ la fișierele HTML
   - Numele fișierelor conțin numele metodei (ex: METODA_1_NODRIVER_*.html)

{'='*70}
""")
    
    # Testează fiecare metodă
    print(f"\n🚀 START TESTARE...\n")
    
    # Metoda 6 - FlareSolverr (fără async)
    test_flaresolverr()
    
    # Metoda 5 - Cloudscraper (fără async)
    test_cloudscraper()
    
    # Metoda 4 - Curl-Impersonate (fără async)
    test_curl_impersonate()
    
    # Metoda 3 - Camoufox (sync API, fără async)
    await test_camoufox()
    
    # Metoda 2 - SeleniumBase (are asyncio intern dar poate rula în async context)
    await test_seleniumbase()
    
    # Metoda 1 - Nodriver (async)
    await test_nodriver()
    
    # Raport final
    print(f"\n{'='*70}")
    print(f"📊 RAPORT FINAL - TESTE CLOUDFLARE BYPASS")
    print(f"{'='*70}\n")
    
    for result in TEST_RESULTS:
        status_icon = "✅" if result['success'] else "❌"
        print(f"{status_icon} {result['method']:<30} | {result['duration_seconds']:.2f}s | {result['timestamp']}")
        if not result['success'] and result['error']:
            print(f"   └─ Eroare: {result['error']}")
    
    # Rezumat
    total = len(TEST_RESULTS)
    success_count = sum(1 for r in TEST_RESULTS if r['success'])
    
    print(f"\n{'='*70}")
    print(f"📈 SUCCESS RATE: {success_count}/{total} ({success_count/total*100:.1f}%)")
    print(f"{'='*70}")
    print(f"\n✅ Rezultatele sunt salvate în: {DEBUG_DIR}/")
    print(f"   Caută fișiere cu pattern: METODA_X_NUME_*.html")
    print(f"\n💡 Metoda cu SUCCESS poate fi integrată în main.py!")

if __name__ == "__main__":
    asyncio.run(main())
