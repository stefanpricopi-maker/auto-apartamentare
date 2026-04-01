🟢 Faza 1: Infrastructură și Configurare (Setup)
[x] Creare folder proiect: Inițializarea structurii de fișiere în Cursor.

[x] Fișier requirements.txt: Adăugarea librăriilor (ezdxf, streamlit, shapely, pandas, openpyxl).

[x] Instalare mediu: Rularea comenzii pip install -r requirements.txt în terminal.

[x] Interfața de bază: Crearea fișierului app.py cu zona de upload și input pentru layer-ul de contur.

🟡 Faza 2: "Creierul" Geometriei (Core Logic)
[ ] Identificare Contururi: Funcție care scanează fișierul DXF și găsește toate poliliniile închise de pe layer-ul CONTUR_APARTAMENT.

[ ] Integrare Shapely: Conversia poliliniilor DXF în poligoane Shapely pentru calcule matematice.

[ ] Algoritmul de Selecție (Criteriul Spațial):

[ ] Implementarea regulii: Elementul este în interior?

[ ] Implementarea regulii: Elementul intersectează conturul? (pentru pereții comuni).

[ ] Filtrare Layer-e: Logică de ignorare a elementelor de mobilier sau a altor layere nedorite.

🔵 Faza 3: Extracția de Date și Excel
[ ] Căutare Text: Identificarea entităților de tip TEXT sau MTEXT din interiorul fiecărui apartament.

[ ] Parsare Date: Folosirea Regex (Regular Expressions) pentru a extrage denumirea camerei și suprafața (ex: din "Dormitor 12.50 mp" să extragă separat numele și cifra).

[ ] Generare Tabel: Crearea unui DataFrame Pandas care să centralizeze datele per apartament.

[ ] Export Excel: Funcția de salvare a tabelului în format .xlsx.

🔴 Faza 4: Export DXF și Finalizare UI
[ ] Creare DXF-uri individuale: Generarea unui nou fișier DXF pentru fiecare apartament detectat.

[ ] Sistem de denumire: Automatizarea numelui fișierului (ex: Ap_1_Vasile_Alecsandri.dxf).

[ ] Împachetare ZIP: Funcție care ia toate DXF-urile și Excel-ul și le pune într-o arhivă pentru descărcare.

[ ] Feedback vizual: Adăugarea de mesaje de succes sau eroare în interfața Streamlit.

⚪ Faza 5: Testare și Rafinare (Real World)
[ ] Testare cu plan real: Încărcarea unui fișier de la soția ta pentru a vedea cum se comportă pereții comuni.

[ ] Tratare excepții: Ce se întâmplă dacă un text este fix pe linie? Ce se întâmplă dacă polilinia de contur nu este perfect închisă?