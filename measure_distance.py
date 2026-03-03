import re

# Citește fișierul
with open(r'd:\github\CasehugAuto\wood_section_full.html', 'r', encoding='utf-8') as f:
    section = f.read()

# Găsește poziția butonului și a textului Open
button_pos = section.find('<button class="sc-b691bd17')
open_pos = section.find('>Open<')

print(f"Poziția <button>: {button_pos}")
print(f"Poziția >Open<: {open_pos}")
print(f"Distanță: {open_pos - button_pos} caractere")

print(f"\nExtrage de la buton până la Open:")
print("=" * 100)
print(section[button_pos:open_pos + 6])
print("=" * 100)

# Testează cu 300 caractere
context_300 = section[max(0, open_pos - 300):open_pos]
has_button_300 = '<button' in context_300
print(f"\nCu 300 caractere înainte: '<button' găsit = {has_button_300}")

# Testează cu 400 caractere
context_400 = section[max(0, open_pos - 400):open_pos]
has_button_400 = '<button' in context_400
print(f"Cu 400 caractere înainte: '<button' găsit = {has_button_400}")

# Testează cu 350 caractere
context_350 = section[max(0, open_pos - 350):open_pos]
has_button_350 = '<button' in context_350
print(f"Cu 350 caractere înainte: '<button' găsit = {has_button_350}")

# Testează cu 320 caractere
context_320 = section[max(0, open_pos - 320):open_pos]
has_button_320 = '<button' in context_320
print(f"Cu 320 caractere înainte: '<button' găsit = {has_button_320}")

print(f"\n✨ MINIM NECESAR: {open_pos - button_pos} caractere")
