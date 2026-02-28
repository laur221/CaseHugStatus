"""
Script pentru salvarea cookie-urilor după login manual.
Rulează acest script LOCAL (nu în Docker), loghează-te manual,
apoi cookie-urile vor fi salvate și folosite de bot în Docker.

PENTRU MULTIPLE CONTURI: Rulează scriptul de 4 ori, câte unul pentru fiecare cont Steam.
"""

import json
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

def save_cookies_for_account():
    """Deschide browser, așteaptă login manual, apoi salvează cookie-urile pentru un cont specific"""
    
    print("\n🍪 Script pentru salvare cookie-uri Steam/Casehug")
    print("═" * 60)
    
    # Verifică câte conturi au deja cookie-uri salvate
    existing_cookies = []
    for i in range(1, 5):
        cookie_file = f"cookies_cont{i}.json"
        if os.path.exists(cookie_file):
            existing_cookies.append(i)
    
    print(f"\n📊 Status cookie-uri existente:")
    for i in range(1, 5):
        if i in existing_cookies:
            print(f"   ✅ Cont {i}: cookies_cont{i}.json EXISTĂ")
        else:
            print(f"   ❌ Cont {i}: cookies_cont{i}.json LIPSĂ")
    
    print("\n" + "═" * 60)
    print("INSTRUCȚIUNI:")
    print("1. Alege pentru care cont vrei să salvezi cookie-urile (1-4)")
    print("2. Se va deschide un browser Chrome")
    print("3. Loghează-te pe casehug.com cu ACEL cont Steam specific")
    print("4. După login complet, revino aici și apasă Enter")
    print("5. Cookie-urile vor fi salvate pentru contul respectiv")
    print("═" * 60)
    print()
    
    # Întreabă pentru care cont
    while True:
        try:
            cont_nr = input("🔢 Pentru care cont salvezi cookie-uri? (1-4): ").strip()
            cont_nr = int(cont_nr)
            if 1 <= cont_nr <= 4:
                break
            else:
                print("❌ Introdu un număr între 1 și 4")
        except ValueError:
            print("❌ Introdu un număr valid")
    
    cookies_file = f"cookies_cont{cont_nr}.json"
    
    if os.path.exists(cookies_file):
        overwrite = input(f"\n⚠️  {cookies_file} există deja. Suprascrii? (da/nu): ").strip().lower()
        if overwrite not in ['da', 'yes', 'y']:
            print("❌ Anulat.")
            return
    
    # Configurare Chrome normal (cu GUI)
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # Deschide casehug.com
        print(f"\n🌐 Deschid casehug.com pentru Cont {cont_nr}...")
        driver.get("https://casehug.com")
        time.sleep(3)
        
        print(f"\n✋ ACUM: Loghează-te manual în browser cu Steam (Cont {cont_nr})!")
        print("📌 Așteaptă până când ești complet logat și vezi profilul tău")
        print()
        
        input("✅ Apasă Enter după ce te-ai logat complet... ")
        
        # Salvează cookie-urile
        cookies = driver.get_cookies()
        
        # Salvează în fișier JSON specific contului
        with open(cookies_file, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, indent=2)
        
        print(f"\n✅ Cookie-urile pentru Cont {cont_nr} au fost salvate în: {cookies_file}")
        print(f"📊 Total cookie-uri salvate: {len(cookies)}")
        
        # Verifică progresul
        saved_count = sum(1 for i in range(1, 5) if os.path.exists(f"cookies_cont{i}.json"))
        print(f"\n📈 Progres total: {saved_count}/4 conturi au cookie-uri salvate")
        
        if saved_count < 4:
            print(f"\n💡 NEXT: Rulează din nou scriptul pentru a salva cookie-urile pentru restul conturilor")
            print(f"   Lipsesc: ", end="")
            missing = [i for i in range(1, 5) if not os.path.exists(f"cookies_cont{i}.json")]
            print(", ".join([f"Cont {i}" for i in missing]))
        else:
            print(f"\n🎉 PERFECT! Toate cele 4 conturi au cookie-uri salvate!")
            print(f"\n💡 NEXT STEPS:")
            print(f"1. Pornește Docker: docker-compose up -d")
            print(f"2. Verifică logs: docker-compose logs -f")
            print(f"3. Botul va folosi aceste cookie-uri pentru bypass Cloudflare")
        
        print(f"\n⚠️  Cookie-urile expiră după câteva săptămâni - re-salvează periodic")
        print(f"📝 Explicație: Site-urile setează expirare pentru securitate (SessionID, tokens, etc.)")
        print(f"   Când expiră, pur și simplu rulezi din nou acest script pentru contul respectiv.")
        
    except Exception as e:
        print(f"\n❌ Eroare: {e}")
    finally:
        print("\n🔒 Închid browser-ul...")
        time.sleep(2)
        driver.quit()

if __name__ == "__main__":
    save_cookies_for_account()
