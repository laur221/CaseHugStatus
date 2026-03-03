import re
import json

def analyze_wood_section():
    # Citește fișierul HTML
    with open(r'd:\github\CasehugAuto\debug_output\debug_Cont_1_available_cases_check.html', 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("=" * 100)
    print("ANALIZA SECȚIUNII WOOD")
    print("=" * 100)
    
    # 1. Găsește poziția secțiunii WOOD
    wood_pattern = r'href="/free-cases/wood"'
    wood_match = re.search(wood_pattern, content)
    
    if not wood_match:
        print("❌ Nu s-a găsit href='/free-cases/wood'")
        return
    
    wood_pos = wood_match.start()
    print(f"\n✅ Găsit href='/free-cases/wood' la poziția: {wood_pos}")
    
    # 2. Extrage context (1000 înainte, 2500 după)
    start_pos = max(0, wood_pos - 1000)
    end_pos = min(len(content), wood_pos + 2500)
    wood_section = content[start_pos:end_pos]
    
    print(f"\n📝 Secțiune extrasă: caractere {start_pos} - {end_pos}")
    print(f"   Lungime secțiune: {len(wood_section)} caractere")
    
    # Salvează secțiunea completă
    with open(r'd:\github\CasehugAuto\wood_section_full.html', 'w', encoding='utf-8') as f:
        f.write(wood_section)
    print(f"   ✅ Salvat în: wood_section_full.html")
    
    # 3. Caută toate variațiile textului "Open"
    print("\n" + "=" * 100)
    print("CĂUTARE VARIAȚII 'OPEN'")
    print("=" * 100)
    
    open_patterns = [
        (r'>Open<', 'Exact: >Open<'),
        (r'>Open</button>', 'Buton: >Open</button>'),
        (r'>Open</a>', 'Link: >Open</a>'),
        (r'>Open</span>', 'Span: >Open</span>'),
        (r'>Open</div>', 'Div: >Open</div>'),
        (r'>\s*Open\s*<', 'Cu spații: > Open <'),
        (r'[Oo]pen', 'Case insensitive: Open/open'),
    ]
    
    for pattern, description in open_patterns:
        matches = list(re.finditer(pattern, wood_section, re.IGNORECASE))
        print(f"\n🔍 {description}")
        print(f"   Găsite: {len(matches)} apariții")
        
        for i, match in enumerate(matches):
            match_pos = match.start()
            global_pos = start_pos + match_pos
            print(f"\n   Apariția #{i+1}:")
            print(f"   - Poziție în secțiune: {match_pos}")
            print(f"   - Poziție globală în fișier: {global_pos}")
            print(f"   - Text găsit: '{match.group()}'")
            
            # Extrage 300 caractere înainte pentru a vedea butonul
            context_start = max(0, match_pos - 300)
            context_end = match_pos + 50
            context = wood_section[context_start:context_end]
            
            print(f"\n   📄 Context (300 caractere înainte):")
            print("   " + "-" * 80)
            print(context)
            print("   " + "-" * 80)
            
            # Caută tagul <button> în context
            button_patterns = [
                r'<button[^>]*>',
                r'<a[^>]*>',
                r'<span[^>]*class="[^"]*button[^"]*"[^>]*>',
            ]
            
            for btn_pattern in button_patterns:
                btn_matches = list(re.finditer(btn_pattern, context, re.IGNORECASE))
                if btn_matches:
                    print(f"\n   🔘 Găsit tag potențial ({btn_pattern}):")
                    for btn_match in btn_matches:
                        tag = btn_match.group()
                        print(f"      Tag: {tag}")
                        
                        # Verifică atributul disabled
                        if 'disabled' in tag.lower():
                            print(f"      ⚠️  DISABLED DETECTAT!")
                        else:
                            print(f"      ✅ Nu are disabled")
                        
                        # Verifică alte atribute
                        if 'aria-disabled' in tag.lower():
                            print(f"      ⚠️  ARIA-DISABLED DETECTAT!")
                        
                        # Extrage class-urile
                        class_match = re.search(r'class="([^"]*)"', tag)
                        if class_match:
                            classes = class_match.group(1)
                            print(f"      Classes: {classes}")
    
    # 4. Caută specific butoane în secțiunea WOOD
    print("\n" + "=" * 100)
    print("ANALIZA BUTOANELOR ÎN SECȚIUNEA WOOD")
    print("=" * 100)
    
    button_matches = list(re.finditer(r'<button[^>]*>.*?</button>', wood_section, re.IGNORECASE | re.DOTALL))
    print(f"\n🔘 Găsite {len(button_matches)} taguri <button> complete în secțiune")
    
    for i, match in enumerate(button_matches):
        button_html = match.group()
        print(f"\n   Buton #{i+1}:")
        print(f"   Poziție: {match.start()}")
        print("   " + "-" * 80)
        print(button_html[:500])  # Primele 500 caractere
        print("   " + "-" * 80)
        
        if 'disabled' in button_html.lower():
            print(f"   ⚠️  BUTON DEZACTIVAT (disabled)")
        else:
            print(f"   ✅ Buton activ (fără disabled)")
        
        # Verifică textul din buton
        button_text = re.sub(r'<[^>]+>', '', button_html)
        print(f"   Text buton: '{button_text.strip()}'")
    
    # 5. Caută link-uri <a> care ar putea fi butoane
    print("\n" + "=" * 100)
    print("ANALIZA LINK-URILOR (care ar putea fi butoane)")
    print("=" * 100)
    
    link_matches = list(re.finditer(r'<a[^>]*>.*?</a>', wood_section, re.IGNORECASE | re.DOTALL))
    print(f"\n🔗 Găsite {len(link_matches)} taguri <a> în secțiune")
    
    for i, match in enumerate(link_matches):
        link_html = match.group()
        # Doar link-urile care par butoane (au class cu "button" sau conțin "Open")
        if 'button' in link_html.lower() or 'open' in link_html.lower():
            print(f"\n   Link #{i+1}:")
            print(f"   Poziție: {match.start()}")
            print("   " + "-" * 80)
            print(link_html[:500])
            print("   " + "-" * 80)
            
            if 'disabled' in link_html.lower() or 'aria-disabled' in link_html.lower():
                print(f"   ⚠️  LINK DEZACTIVAT")
            else:
                print(f"   ✅ Link activ")
    
    # 6. Rezumat final
    print("\n" + "=" * 100)
    print("REZUMAT FINAL")
    print("=" * 100)
    
    # Salvează rezultatele în JSON
    results = {
        'wood_position': wood_pos,
        'section_start': start_pos,
        'section_end': end_pos,
        'section_length': len(wood_section),
        'open_text_found': len(list(re.finditer(r'open', wood_section, re.IGNORECASE))),
        'buttons_found': len(button_matches),
        'links_found': len([m for m in link_matches if 'open' in m.group().lower()]),
    }
    
    with open(r'd:\github\CasehugAuto\wood_analysis_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📊 Statistici:")
    print(f"   - Apariții 'Open' (case insensitive): {results['open_text_found']}")
    print(f"   - Butoane găsite: {results['buttons_found']}")
    print(f"   - Link-uri cu 'Open': {results['links_found']}")
    print(f"\n✅ Rezultate salvate în: wood_analysis_results.json")
    print(f"✅ Secțiune HTML salvată în: wood_section_full.html")

if __name__ == "__main__":
    analyze_wood_section()
