import re

def test_wood_detection():
    """Testează logica de detectare pentru WOOD exact cum face main.py"""
    
    # Citește fișierul HTML
    with open(r'd:\github\CasehugAuto\debug_output\debug_Cont_1_available_cases_check.html', 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("=" * 100)
    print("TEST LOGICA DE DETECTARE WOOD (exact cum face main.py)")
    print("=" * 100)
    
    # Configurația case-urilor
    case_urls = {
        "discord": 'href="/free-cases/discord"',
        "steam": 'href="/free-cases/steam"',
        "wood": 'href="/free-cases/wood"'
    }
    
    case_type = "wood"
    case_url_marker = case_urls[case_type]
    
    print(f"\n📍 PAS 1: Căutare marker '{case_url_marker}'")
    
    # Găsește secțiunea case-ului după URL-ul său
    case_pos = content.find(case_url_marker)
    
    if case_pos == -1:
        print(f"   ❌ {case_type.upper()} - nu a fost găsit pe pagină")
        return
    
    print(f"   ✅ Găsit la poziția: {case_pos}")
    
    # Extrage secțiunea (500 înainte, 2000 după)
    print(f"\n📍 PAS 2: Extragere secțiune (500 înainte, 2000 după)")
    section_start = max(0, case_pos - 500)
    section_end = min(len(content), case_pos + 2000)
    case_section = content[section_start:section_end]
    case_section_lower = case_section.lower()
    
    print(f"   Secțiune: caractere {section_start} - {section_end}")
    print(f"   Lungime: {len(case_section)} caractere")
    
    # 1. Verifică dacă are TIMER BADGE (cooldown activ)
    print(f"\n📍 PAS 3: Verificare TIMER BADGE")
    has_timer = False
    if 'data-testid="badge"' in case_section and 'ri-timer-line' in case_section:
        time_pattern = re.search(r'(\d{1,2}):(\d{2}):(\d{2})', case_section)
        if time_pattern:
            time_str = time_pattern.group(0)
            print(f"   ⏰ TIMER găsit: {time_str}")
            has_timer = True
    
    if not has_timer:
        print(f"   ✅ NU are timer badge")
    
    if has_timer:
        print(f"\n❌ BLOCAT: Are timer, skip acest case")
        return
    
    # 2. Verifică dacă are LOCK ICON
    print(f"\n📍 PAS 4: Verificare LOCK ICON")
    has_lock_icon = 'si-ch-lock' in case_section
    
    if has_lock_icon:
        print(f"   🔒 LOCK ICON găsit")
    else:
        print(f"   ✅ NU are lock icon")
    
    # 3. Verifică dacă butonul este DISABLED cu text "CASE LOCKED"
    print(f"\n📍 PAS 5: Verificare DISABLED + CASE LOCKED")
    has_disabled_button = ('disabled=""' in case_section or '<button disabled' in case_section)
    is_case_locked = 'CASE LOCKED' in case_section or 'Case Locked' in case_section
    
    print(f"   has_disabled_button: {has_disabled_button}")
    print(f"   is_case_locked: {is_case_locked}")
    
    if has_lock_icon or (has_disabled_button and is_case_locked):
        print(f"\n❌ BLOCAT: Are lock sau disabled + case locked")
        return
    else:
        print(f"   ✅ NU e blocat explicit")
    
    # 4. Verifică dacă butonul este DISABLED în general
    print(f"\n📍 PAS 6: Verificare DISABLED general (fără timer)")
    if has_disabled_button and not has_timer:
        print(f"   ⚠️  Buton disabled (posibil task incomplete)")
        print(f"\n❌ BLOCAT: Buton disabled general")
        return
    else:
        print(f"   ✅ Buton NU este disabled general")
    
    # 5. Verifică dacă există buton ACTIV cu text "Open"
    print(f"\n📍 PAS 7: Verificare buton ACTIV cu text 'Open'")
    has_open_button = False
    
    # Caută textul "Open"
    if '>Open<' in case_section:
        print(f"   ✅ Găsit '>Open<' în secțiune")
        
        # Găsește toate pozițiile unde apare ">Open<"
        open_positions = []
        search_pos = 0
        while True:
            pos = case_section.find('>Open<', search_pos)
            if pos == -1:
                break
            open_positions.append(pos)
            search_pos = pos + 1
        
        print(f"   📊 Găsite {len(open_positions)} apariții de '>Open<'")
        
        # Pentru fiecare poziție, verifică dacă e în context de buton valid
        for i, open_pos in enumerate(open_positions):
            print(f"\n   🔍 Analizez apariția #{i+1} la poziția {open_pos}")
            
            # Extrage 400 caractere înainte pentru a vedea tagul <button>
            # (WOOD case necesită 309+ caractere, 300 era prea puțin)
            button_context = case_section[max(0, open_pos - 400):open_pos]
            
            print(f"      Context (ultimele 200 caractere):")
            print(f"      {'-' * 80}")
            print(f"      ...{button_context[-200:]}")
            print(f"      {'-' * 80}")
            
            # Verifică dacă există <button>
            if '<button' in button_context:
                print(f"      ✅ Găsit '<button' în context")
                
                # Extrage doar ultimul <button> tag (cel mai apropiat)
                last_button_start = button_context.rfind('<button')
                button_tag = button_context[last_button_start:]
                
                print(f"      📄 Tag buton extras:")
                print(f"      {'-' * 80}")
                print(f"      {button_tag[:200]}")
                print(f"      {'-' * 80}")
                
                # Verifică dacă acest button NU are disabled
                if 'disabled' not in button_tag:
                    print(f"      ✅✅✅ BUTON ACTIV GĂSIT! (fără 'disabled')")
                    has_open_button = True
                    break
                else:
                    print(f"      ❌ Buton are 'disabled'")
            else:
                print(f"      ⚠️  NU există '<button' în context")
    else:
        print(f"   ❌ NU există '>Open<' în secțiune")
    
    # 6. Rezultat final
    print(f"\n{'=' * 100}")
    print("REZULTAT FINAL")
    print(f"{'=' * 100}")
    
    if has_open_button:
        print(f"✅✅✅ {case_type.upper()} - DISPONIBIL (buton Open activ)")
        print(f"\nACȚIUNE: Case-ul ar trebui ADĂUGAT în available_cases")
    else:
        print(f"❌ {case_type.upper()} - NU DISPONIBIL (nu văd buton Open activ)")
        print(f"\nACȚIUNE: Case-ul NU va fi adăugat în available_cases")
    
    # Salvează secțiunea pentru debugging
    with open(r'd:\github\CasehugAuto\wood_section_debug.html', 'w', encoding='utf-8') as f:
        f.write(case_section)
    print(f"\n📄 Secțiune salvată în: wood_section_debug.html")

if __name__ == "__main__":
    test_wood_detection()
