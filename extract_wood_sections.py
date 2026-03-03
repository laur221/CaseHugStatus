import re
import json

# Citește fișierul HTML
with open(r'd:\github\CasehugAuto\debug_output\debug_Cont_1_available_cases_check.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

# Găsește toate aparițiile cuvântului "wood" (case-insensitive)
pattern = re.compile(r'wood', re.IGNORECASE)
matches = list(pattern.finditer(html_content))

print(f"Număr total de apariții găsite: {len(matches)}\n")
print("="*100)

# Extrage contextul pentru fiecare apariție
for idx, match in enumerate(matches, 1):
    start_pos = match.start()
    end_pos = match.end()
    
    # Extrage 1000 caractere înainte și după
    context_start = max(0, start_pos - 1000)
    context_end = min(len(html_content), end_pos + 1000)
    
    context = html_content[context_start:context_end]
    
    print(f"\n\n{'='*100}")
    print(f"APARIȚIE #{idx} LA POZIȚIA {start_pos}")
    print(f"{'='*100}")
    print(context)
    print(f"\n{'='*100}")

# Caută special pentru secțiunea JSON cu informații despre case
print("\n\n" + "="*100)
print("CĂUTARE SPECIALĂ: Secțiune JSON cu detalii case WOOD")
print("="*100)

# Caută pattern-ul JSON pentru rankCases
json_pattern = re.compile(r'"rankCases":\[.*?"title":"WOOD".*?\}(?=,\{"id"|\])', re.IGNORECASE)
json_match = json_pattern.search(html_content)

if json_match:
    json_text = json_match.group(0)
    # Extinde pentru a captura tot obiectul
    start = json_match.start()
    # Găsește sfârșitul obiectului WOOD
    brace_count = 0
    in_string = False
    escape_next = False
    end = start
    
    for i in range(start, len(html_content)):
        char = html_content[i]
        
        if escape_next:
            escape_next = False
            continue
            
        if char == '\\':
            escape_next = True
            continue
            
        if char == '"' and not escape_next:
            in_string = not in_string
            
        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and i > start + 100:
                    end = i + 1
                    break
    
    wood_json = html_content[start:end]
    print("\nJSON complet pentru case-ul WOOD:")
    print(wood_json)
    
    # Încearcă să parseze JSON-ul
    try:
        # Extrage doar obiectul WOOD
        wood_obj_match = re.search(r'\{"id":\d+,"title":"WOOD".*?\}(?=,\{|\])', html_content, re.IGNORECASE)
        if wood_obj_match:
            # Găsește închiderea corectă a obiectului
            obj_start = wood_obj_match.start()
            obj_text = ""
            brace_count = 0
            in_string = False
            
            for i in range(obj_start, len(html_content)):
                char = html_content[i]
                obj_text += char
                
                if char == '"' and (i == obj_start or html_content[i-1] != '\\'):
                    in_string = not in_string
                    
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            break
            
            print("\n\nObiect JSON WOOD parsat:")
            wood_obj = json.loads(obj_text)
            print(json.dumps(wood_obj, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"\nEroare la parsarea JSON: {e}")

print("\n\nScript finalizat!")
