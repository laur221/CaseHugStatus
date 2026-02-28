"""
Script de test pentru verificarea configurației Telegram
"""
import json
import requests
import sys
import os

def test_telegram():
    """Testează configurația Telegram din config.json"""
    
    print("🧪 Test Configurație Telegram")
    print("="*50)
    
    # Verifică dacă config.json există
    if not os.path.exists("config.json"):
        print("❌ config.json nu există!")
        print("💡 Copiază config.example.json la config.json și editează-l")
        return False
    
    # Citește configurația
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Eroare la citirea config.json: {e}")
        return False
    
    # Verifică token și chat ID
    token = config.get("telegram_bot_token", "")
    chat_id = config.get("telegram_chat_id", "")
    
    if not token or token == "YOUR_BOT_TOKEN_HERE":
        print("❌ Telegram bot token nu este configurat!")
        print("💡 Editează config.json și adaugă tokenul de la @BotFather")
        print("📚 Citește TELEGRAM_SETUP.md pentru instrucțiuni")
        return False
    
    if not chat_id or chat_id == "YOUR_CHAT_ID_HERE":
        print("❌ Telegram chat ID nu este configurat!")
        print("💡 Editează config.json și adaugă chat ID-ul tău")
        print("📚 Citește TELEGRAM_SETUP.md pentru instrucțiuni")
        return False
    
    print(f"✅ Token găsit: {token[:20]}...")
    print(f"✅ Chat ID găsit: {chat_id}")
    print("\n🔄 Trimit mesaj de test...\n")
    
    # Trimite mesaj de test
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": "✅ <b>CasehugAuto Bot - Test Reușit!</b>\n\n"
                "🎉 Telegram este configurat corect!\n"
                "📊 Acum poți rula botul cu: <code>python main.py</code>\n\n"
                "💡 Vei primi rapoarte aici după fiecare rulare.",
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, data=data)
        result = response.json()
        
        if response.status_code == 200 and result.get("ok"):
            print("✅ SUCCES! Mesaj trimis pe Telegram!")
            print("📱 Verifică aplicația Telegram pentru mesajul de test.")
            print("\n" + "="*50)
            print("🎯 Configurația este completă!")
            print("🚀 Poți rula acum: python main.py")
            print("="*50)
            return True
        else:
            print(f"❌ Eroare de la Telegram API:")
            print(f"   Status: {response.status_code}")
            print(f"   Răspuns: {result}")
            
            # Mesaje de ajutor pentru erori comune
            if "Unauthorized" in str(result):
                print("\n💡 Token-ul este greșit. Verifică-l la @BotFather")
            elif "chat not found" in str(result).lower():
                print("\n💡 Chat ID greșit sau nu ai trimis niciun mesaj botului")
                print("   1. Caută botul pe Telegram")
                print("   2. Click pe 'Start'")
                print("   3. Trimite un mesaj")
                print("   4. Obține chat ID-ul din nou")
            
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Eroare de rețea: {e}")
        print("💡 Verifică conexiunea la internet")
        return False
    except Exception as e:
        print(f"❌ Eroare neașteptată: {e}")
        return False

if __name__ == "__main__":
    print()
    success = test_telegram()
    print()
    
    if not success:
        print("📚 Citește TELEGRAM_SETUP.md pentru instrucțiuni detaliate")
        print("🔧 Sau TROUBLESHOOTING.md pentru rezolvarea problemelor")
        sys.exit(1)
    
    sys.exit(0)
