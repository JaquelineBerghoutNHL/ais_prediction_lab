import streamlit as st
from login import controleer_login

controleer_login()

st.title("AIS Prediction Lab")
st.subheader("Data Science – Resit")

st.write("""
Dit project is een herkansing van mijn eerdere Data Science-project,
waarin ik werkte met AIS-gegevens van schepen.

Voor deze herkansing heb ik bewust een klein onderdeel gekozen:
het berekenen en voorspellen van scheepsposities.

Ik heb de feedback Herbert meegenomen en dit onderdeel
verder onderzocht, verbeterd en getest.
""")

st.subheader("Wat heb ik gedaan?")

st.write("""
**1. Berekening**
Ik bereken een toekomstige scheepspositie met de great-circle-methode,
waarbij rekening wordt gehouden met de kromming van de aarde.

**2. Random Forest**
Ik train een machinelearningmodel met historische AIS-metingen
om toekomstige scheepsposities te voorspellen.

**3. Vaarwegen**
Omdat voorspellingen soms op het land terechtkomen,
gebruik ik ook de vaarweggegevens van Rijkswaterstaat.

**4. Vergelijking**
Ik vergelijk de verschillende methoden met werkelijke AIS-posities
en bereken de voorspellingsfouten in meters.
""")

st.subheader("Wat toon ik hiermee aan?")

st.write("""
- Ik kan AIS-data selecteren en voorbereiden voor analyse.
- Ik kan een wiskundige voorspellingsmethode toepassen.
- Ik kan een Random Forest-model trainen en testen.
- Ik kan aanvullende geografische gegevens gebruiken.
- Ik kan methoden vergelijken en de resultaten kritisch beoordelen.

Het doel is niet alleen een zo nauwkeurig mogelijke voorspelling,
maar ook begrijpen waarom een methode wel of niet goed werkt.
""")