# Egyetemi RFID/NFC jelenlétkezelő rendszer

Ez a projekt egyetemi jelenléti és épületbelépési események kezelésére készült. A hallgató NFC-kártyájának UID-je alapján a rendszer azonosítja a felhasználót, ellenőrzi az aktív kurzusfelvételt és a kurzusalkalom időablakát, majd rögzíti az órai jelenlétet. Az épületbe történő belépést és kilépést ettől külön kezeli.

## Felépítés

- A Python és Tkinter alapú asztali alkalmazás a PC/SC-kompatibilis olvasóval kezeli a kártyaolvasást, a belépési és kilépési eseményeket, valamint az automatikus órai jelenlétet.
- A Flask webalkalmazás REST API-t és adminisztrációs felületet biztosít. Az adminisztrátor felhasználókat, kártyákat, kurzusokat és oktatói hozzárendeléseket kezelhet. Az oktatók a saját kurzusaikat és azok jelenléti adatait érhetik el.
- A MySQL-kompatibilis adatbázis tárolja a felhasználókat, kártyákat, kurzusokat, kurzusalkalmakat, jelenléteket, előzményeket és eseménynaplókat.

## Fő funkciók

- NFC UID beolvasása és egységesítése PC/SC-kompatibilis olvasóval.
- Belépési és kilépési események naplózása.
- Jelenlét és késés rögzítése az aktív kurzusfelvétel és az alkalom időablaka alapján.
- Ismételt jelenlét, ismeretlen kártya, hiányzó kurzusfelvétel és több lehetséges kurzusalkalom kezelése.
- Hallgatók, oktatók, kártyák, kurzusok és kurzusalkalmak adminisztrációja.
- Hallgatói CSV/XLSX-import, jelenléti CSV-import, valamint CSV-, XLSX- és naptárexport.
- Jelenléti és állapotváltozási előzmények, audit események és összesítések megtekintése.

## Követelmények és tesztkörnyezet

A projekt Python 3.11 vagy újabb verzióval és a `requirements.txt` fájlban felsorolt csomagokkal futtatható. NFC-olvasáshoz PC/SC-kompatibilis olvasó, annak illesztőprogramja és működő PC/SC szolgáltatás szükséges.

A szakdolgozatban dokumentált tesztkörnyezet Windows, Python 3.13.0, MariaDB 10.4.32 és MySQL Connector/Python 9.6.0 volt. A fizikai olvasási próbához egy GHI NC001 0 olvasót és két kártyát használtam.

## Telepítés és indítás

1. Hozz létre és aktiválj egy virtuális környezetet, majd telepítsd a függőségeket:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

2. Hozz létre egy MySQL/MariaDB adatbázist, majd futtasd a `database/database.sql` sémát. Az alkalmazás adatbázis-felhasználójának beállításához használd a `database/grant_app_user.sql` fájlt, és állíts be saját, erős jelszót.

3. Állítsd be a környezeti változókat. A `.env.example` fájl a szükséges változók mintáját tartalmazza; az alkalmazás közvetlenül a folyamat környezeti változóit olvassa:

   - `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
   - `SECRET_KEY`, `API_HOST`, `API_PORT`
   - `ACCESS_COOLDOWN_SECONDS`, `LOG_LEVEL`

   A `SECRET_KEY` értékéhez adj meg egy hosszú, véletlenszerű értéket. A forráskódban szereplő fejlesztői alapérték nem megfelelő éles használatra.

4. Hozd létre az első adminisztrátori fiókot. A parancs bekéri az e-mail-címet, a nevet és a jelszót; a jelszó bcrypt hashként kerül az adatbázisba:

   ```powershell
   python -m utils.create_admin
   ```

5. Indítsd el a kívánt alkalmazást:

   ```powershell
   python main.py
   python main.py --web
   ```

   A webes felület alapértelmezett címe `http://127.0.0.1:5000`. Az asztali NFC-olvasó és a webalkalmazás külön folyamatként fut.

## Használat

Az adminisztrátor a webes felületen hozhat létre oktatói és hallgatói rekordokat, rendelhet kártyát a hallgatókhoz, és kezelheti a kurzusokat. A hallgatói fiókokkal nem lehet webes felületre bejelentkezni. Az oktatói fiókok jelszavas belépést használnak, és csak a hozzájuk rendelt kurzusokhoz férnek hozzá.

Hallgatói importnál a fájlnak `Név` és `Neptun-kód` oszlopot kell tartalmaznia; az e-mail-cím opcionális. Az importálás előtt az előnézet ellenőrzi az adatokat. A dokumentált próbák között szerepelt a helyes fájl előnézete, valamint a fejléc nélküli, hibás Neptun-kódot tartalmazó és érvénytelen e-mail-című fájl elutasítása.

## Adminisztrációs és fejlesztői parancsok

- Adatbázis-környezet ellenőrzése: `python -m utils.diagnostics`
- Fiktív bemutatóadatok létrehozása: `python -m utils.seed_demo --students 24 --confirm`
- API kliens súgója: `python -m utils.attendance_cli --help`
- Egy megnyitott alkalomhoz kötött NFC-olvasó: `python -m nfc.session_reader <session_id>`
- OpenAPI specifikáció: `http://127.0.0.1:5000/api/docs/openapi.json`

## Tesztelési korlátok

A szakdolgozatban a fizikai olvasási próbát egy olvasóval és két kártyával végeztem. Az egyidejűleg aktív kurzusalkalmak tesztelésekor különböző hallgatók jelenléte a megfelelő kurzushoz került; azt az esetet, amikor ugyanaz a hallgató több egyidejű alkalomra is fel van véve, nem vizsgáltam külön. A felületeket manuálisan ellenőriztem, automatizált felületi és terheléses teszt nem készült. A kártya UID-je technikai azonosító, önmagában nem bizonyítja teljes bizonyossággal a kártyabirtokos személyazonosságát.
