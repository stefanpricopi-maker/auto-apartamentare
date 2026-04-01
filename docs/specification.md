Specificație Software: "AutoApartamentare" v1.1

1. Scopul Aplicației
Separarea automată a unui plan de etaj tip .dxf în relevee individuale per apartament și generarea unui tabel centralizator cu suprafețe.

2. Premise și Input (Cerințe Desen)
Fișier Sursă: Format .dxf.

Strat de Separare (Layer): Utilizatorul va trasa manual o polilinie închisă (LWPOLYLINE) în jurul fiecărui apartament pe un layer dedicat numit CONTUR_APARTAMENT.

Elemente Incluse: Pereți, uși, ferestre, cote și texte (denumire încăpere + suprafață).

Elemente Excluse: Mobila (se va ignora layer-ul de mobilier dacă există).

3. Fluxul de Lucru al Aplicației
Încărcare: Utilizatorul încarcă fișierul .dxf în interfața Streamlit.

Identificare: Scriptul caută toate poliliniile de pe layer-ul CONTUR_APARTAMENT.

Extracție (Clipping): * Pentru fiecare contur găsit, se creează un nou obiect DXF.

Se copiază în noul fișier doar entitățile care se află geometric în interiorul conturului respectiv.

Se ignoră layer-ul de mobilier (hardcoded sau selectabil).

Procesare Date:

Scriptul citește textele din interiorul fiecărui contur pentru a extrage automat denumirile camerelor și valorile suprafețelor (folosind Regex/căutare după model).

Export:

DXF-uri individuale: Câte un fișier pentru fiecare apartament (ex: Apartament_1.dxf).

Excel: Un fișier .xlsx cu tabelul de suprafețe centralizat.

4. Specificații Tehnice Detaliate
4.1. Motorul Geometrie (Python)
Librărie CAD: ezdxf pentru citire și scriere.

Librărie Geometrie: Shapely pentru a verifica dacă o linie sau un punct este within() (în interiorul) poliliniei de contur.

Coordonate: Se păstrează coordonatele locale din fișierul original (fără translatare în origine, pentru a menține precizia).

4.2. Output Așteptat
Arhivă ZIP: Conține toate DXF-urile rezultate.

Tabel Excel: Coloane: Nr. Apartament, Încăpere, Suprafață Utilă (mp), Total Suprafață Apartament.

5. Interfața Utilizator (Mockup)
Zona 1: Upload fișier .dxf.

Zona 2 (Setări): Câmp text pentru confirmarea layer-ului de contur (default: CONTUR_APARTAMENT).

Zona 3 (Acțiune): Buton "Procesează și Generează".

Zona 4 (Rezultat): Link download Rezultate_Apartamentare.zip.