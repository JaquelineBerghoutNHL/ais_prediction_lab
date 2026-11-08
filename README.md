# AIS Prediction Lab

**Data Science – resit | Verkenning voor Maritime Innovations**

## 1. Aanleiding

Dit project is een resit van mijn eerdere Data Science-project met AIS-gegevens. In plaats van het volledige oorspronkelijke project opnieuw uit te werken, heb ik bewust één onderdeel gekozen: het berekenen en voorspellen van scheepsposities.

Bij deze uitwerking heb ik de feedback Herbert meegenomen. 

Het resultaat is het AIS Prediction Lab: een Streamlit-app waarin ik een wiskundige berekening, een machinelearningmodel en een voorspelling langs vaarwegen kan onderzoeken en vergelijken.

## 2. Van berekening naar onderzoek

### Stap 1 – Great-circle

Ik ben begonnen met een berekening op basis van een bekende AIS-positie, snelheid over de grond (SOG), koers over de grond (COG) en een gekozen tijdsduur. Met de great-circle-benadering houd ik rekening met de kromming van de aarde. De snelheid in knopen reken ik om naar kilometers met 1,852 kilometer per zeemijl.

Dit is het "gewoon met het handje" berekenen ipv moeilijk met modellen. Ik heb de berekening bestudeerd aan de hand van de uitleg over een bestemmingspunt op basis van afstand en koers op [Movable Type Scripts](https://www.movable-type.co.uk/scripts/latlong.html).

### Stap 2 – Het probleem met voorspellingen op land

Bij het bekijken van de resultaten op een kaart zag ik dat een berekende positie soms op land terechtkwam. Dat is begrijpelijk: de great-circle-berekening de waterwegen niet. De berekening volgt de opgegeven koers en snelheid, maar niet een bevaarbare route.

Dit was voor mij aanleiding om verder te zoeken naar geografische gegevens die bij de voorspelling kunnen helpen.

### Stap 3 – Vaarwegen van Rijkswaterstaat

Ik heb vaarweggegevens van Rijkswaterstaat onderzocht en verwerkt. Daarvoor moest ik begrijpen hoe de geografische lijnen zijn opgeslagen en hoe coördinatenstelsels werken. AIS-posities gebruiken geografische coördinaten; voor het berekenen van afstanden tot vaarwegen is een geprojecteerd stelsel handiger. Ik heb daarom gewerkt met het Rijksdriehoeksstelsel (RD; EPSG:28992) en met omzettingen van en naar WGS 84 (EPSG:4326).

Met GeoPandas en Shapely kan ik een schip koppelen aan een nabijgelegen vaarweglijn en een voorspelde positie langs die lijn bepalen. Ook de koers van het schip speelt mee bij de keuze van de richting. Deze methode is niet foutloos: bij een splitsing of verkeerde keuze van een vaarwegvak kan de voorspelling alsnog verkeerd uitkomen.

Bronnen: [Rijkswaterstaat-vaarweggegevens via data.overheid.nl](https://data.overheid.nl/dataset/451c1e14-2ce3-4432-87fd-4bcfaa683a90), [GeoPandas – to_crs](https://geopandas.org/en/stable/docs/reference/api/geopandas.GeoDataFrame.to_crs.html) en [Shapely – Linear Referencing](https://shapely.readthedocs.io/en/stable/manual.html#linear-referencing-methods).

### Stap 4 – Random Forest

Daarna ben ik weer verder gegaan met Random Forest om de toekomstige verplaatsing kan leren uit historische AIS-metingen. Voor elk bruikbaar startpunt zoek ik een werkelijke vervolgmeting rond het gekozen voorspeltijdstip. De invoer bevat onder meer de startpositie, snelheid en koers. Het model leert de verplaatsing in noordelijke en oostelijke richting en gebruikt die om een volgende positie te voorspellen.

Ik verdeel de voorbeelden chronologisch: de oudere metingen zijn bedoeld voor training en de latere voor de test. Daarmee voorkom ik dat het model willekeurig toekomstige voorbeelden tussen de trainingsvoorbeelden krijgt. De gebruikte selectie van bijvoorbeeld de nieuwste 5.000 posities bepaalt uit welke maanden de trainings- en testgegevens komen.

In de code is `model.fit(...)` het trainen en `model.predict(...)` het voorspellen op de testgegevens. De scikit-learn-documentatie over [RandomForestRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html) is hiervan de bron.

### Stap 5 – Hybride voorspelling en vergelijking

Omdat een model dat alleen historische bewegingen leert nog steeds een positie op land kan voorspellen, heb ik ook een hybride methode gemaakt. Die combineert de uitkomst van Random Forest met informatie uit het vaarwegennet.

Ik vergelijk de methoden met de werkelijke AIS-positie en bereken de afstandsfout in meters, onder andere met de Haversine-afstand. Een lagere gemiddelde fout betekent niet dat een methode in elke afzonderlijke situatie beter is. Ook vergelijk ik waar mogelijk op dezelfde testgevallen, zodat de resultaten eerlijker naast elkaar staan.

In een van mijn tests kwam Random Forest gemiddeld ongeveer even goed uit als great-circle, terwijl de hybride methode een kleinere gemiddelde fout liet zien. Dat is een interessant resultaat: meer machinelearning is niet automatisch beter, maar aangevuld met de omgeving kan het belangrijk zijn.

## 3. Hoe de applicatie is opgebouwd

De applicatie is gemaakt in Python en Streamlit en gebruikt PostgreSQL voor schepen en AIS-posities. Via de onderhoudspagina (Maintenance) kunnen schepen worden opgezocht en kunnen AIS-posities worden ingelezen. De andere pagina's richten zich op berekenen, trainen en vergelijken.

Tijdens de ontwikkeling merkte ik dat dezelfde berekeningen en bewerkingen op meerdere pagina's terugkwamen. Daardoor ontstond dubbele code. Ik heb die logica daarom samengebracht in een apart bestand met herbruikbare functies (`functies.py`). De Streamlit-pagina's zijn daardoor korter en overzichtelijker geworden. 

Belangrijke onderdelen van de code:

- `Home.py`: introductie en doel van de resit.
- `pages/`: de Streamlit-pagina's voor berekening, Random Forest, vergelijking en onderhoud.
- `functies.py`: gedeelde berekeningen en geografische functies.
- `login.py`: eenvoudige toegangscontrole voor de online demonstratie.
- `requirements.txt`: Python-afhankelijkheden.

## 4. Afbakening en beperkingen

Ik heb bewust gekozen voor een werkend prototype in plaats van een volledig productiegeschikt systeem. Mijn aandacht ging vooral naar het vergelijken van de voorspellingen.

Daarom heb ik niet alle mogelijke foutpaden uitgewerkt met uitgebreide `try`/`except`-afhandeling. Ik heb vooral de verwachte, goed werkende routes getest: beschikbare AIS-data, geldige posities, een werkende databaseverbinding en bruikbare vaarweggegevens. Dat is een beperking van dit project. Voor gebruik door anderen of voor een operationele toepassing zijn aanvullende foutafhandeling, invoercontroles, logging, beveiliging en tests nodig.

Ook is een voorspelling op basis van AIS-data niet hetzelfde als het vaststellen van de werkelijke scheepspositie. AIS-data kunnen onvolledig, vertraagd of onjuist zijn. De vaarwegmethode kan bovendien de verkeerde tak kiezen en het model is afhankelijk van de kwaliteit en representativiteit van de trainingsdata.

## 5. Wat ik met deze resit laat zien

Met dit project wil ik laten zien dat ik Data Science niet alleen toepas door een model te trainen, maar door een volledig klein onderzoeksproces te doorlopen:

1. Een afgebakend probleem kiezen en een referentieberekening onderzoeken.
2. AIS-data selecteren, koppelen en voorbereiden.
3. Een Random Forest-model trainen op historische voorbeelden.
4. Oudere trainingsdata scheiden van latere testdata.
5. Een externe geografische databron gebruiken om voorspellingen te verbeteren.
6. Voorspellingen toetsen aan werkelijke AIS-metingen en resultaten kritisch interpreteren.
7. De code herstructureren in herbruikbare functies.

Dit zijn de activiteiten die ik in de applicatie kan demonstreren.

## 6. Mogelijk vervolg: afstuderen bij Maritime Innovations

Ik wil dit project graag als startpunt voor mijn afstuderen bespreken met Eelco en Herbert. Het huidige Prediction Lab is nog geen afstudeeronderzoek naar cybersecurity, maar biedt wel een technische basis: ik kan historische scheepsbewegingen analyseren, verwachte posities berekenen en afwijkingen tussen voorspelling en waarneming zichtbaar maken.

Voor de Master Maritime Innovations wil ik onderzoeken of die basis kan worden uitgebreid naar AIS-anomalieën, databetrouwbaarheid en cybersecurity. Een mogelijke richting is het herkennen en demonstreren van gemanipuleerde of afwijkende positiegegevens, bijvoorbeeld als onderdeel van een maritieme cybersecuritytraining of simulatie. Dat is voorlopig een idee om verder te bespreken, geen afgeronde functionaliteit.

Een belangrijke inspiratiebron is het artikel “When Ships Sail Through Airports: Using AIS to Detect and Understand GNSS Spoofing at Sea” van Dmitry Rostopshin, gepubliceerd in SWZ Maritime (september 2026). Herbert wees mij hierop Het artikel beschrijft onder meer onmogelijke scheepsbewegingen, posities op land, plotselinge sprongen en de noodzaak om AIS-data eerst te schonen voordat je afwijkingen met machinelearning probeert te analyseren. Ook maakt het onderscheid tussen foutieve data, AIS-manipulatie, GNSS-jamming en GNSS-spoofing.

Dat sluit aan op mijn mogelijke vervolgonderzoek. Mijn huidige app detecteert nog geen spoofing en kan niet vaststellen of een afwijking opzettelijk is. Een volgende stap zou zijn om eerst vast te leggen wat een normale en betrouwbare scheepsbeweging is, daarna afwijkende patronen te onderzoeken en de beperkingen van AIS als informatiebron expliciet mee te nemen.

## 7. Techniek en lokaal starten

De app gebruikt onder meer Streamlit, pandas, NumPy, scikit-learn, SQLAlchemy, PostgreSQL, GeoPandas, Shapely, PyGeodesy en Pydeck.

Installeer de afhankelijkheden vanuit de projectmap:

```bash
pip install -r requirements.txt
```

Stel de vereiste omgevingsvariabelen lokaal in, bijvoorbeeld via een niet-gecommitte `.env`:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=naam_van_je_database
DB_USER=je_gebruiker
DB_PASSWORD=je_eigen_wachtwoord
AIS_API_KEY=je_eigen_api_sleutel
APP_PASSWORD=je_eigen_app_wachtwoord
```

Start de applicatie:

```bash
streamlit run Home.py
```

De PostgreSQL-tabellen en de benodigde vaarweggegevens moeten aanwezig zijn. De voorbeeldwaarden hierboven zijn geen echte inloggegevens. 

## 8. Bronnen

- Movable Type Scripts – *Calculate distance, bearing and more between Latitude/Longitude points*: https://www.movable-type.co.uk/scripts/latlong.html
- Rijkswaterstaat-vaarweggegevens via data.overheid.nl: https://data.overheid.nl/dataset/451c1e14-2ce3-4432-87fd-4bcfaa683a90
- GeoPandas – `GeoDataFrame.to_crs`: https://geopandas.org/en/stable/docs/reference/api/geopandas.GeoDataFrame.to_crs.html
- Shapely – *Linear Referencing Methods*: https://shapely.readthedocs.io/en/stable/manual.html#linear-referencing-methods
- scikit-learn – `RandomForestRegressor`: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html
- PyGeodesy – afstandsberekeningen: https://mrjean1.github.io/PyGeodesy/docs/pygeodesy.formy-module.html
- Rostopshin, D. (2026, september). *When Ships Sail Through Airports: Using AIS to Detect and Understand GNSS Spoofing at Sea*. **SWZ Maritime**. Artikel door gebruiker aangeleverd als `SWZ spoofing.pdf`.
