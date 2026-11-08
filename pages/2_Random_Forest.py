from login import controleer_login
controleer_login()

import numpy as np
import pandas as pd
import streamlit as st
from sqlalchemy import text
from sklearn.ensemble import RandomForestRegressor
from database import engine
from functies import afstand_meter, great_circle, laad_vaarwegnetwerk, hybride_voorspelling

@st.cache_data(ttl=300)
def zoek_schepen_lokaal(naam):
    with engine.connect() as conn:
        return pd.read_sql(text("""
            SELECT s.mmsi, s.name, COUNT(*) AS aantal
            FROM ship s JOIN position p ON s.mmsi = p.mmsi
            WHERE s.name ILIKE :naam
            GROUP BY s.mmsi, s.name ORDER BY aantal DESC LIMIT 30
        """), conn, params={"naam": f"%{naam}%"})

@st.cache_data(ttl=300)
def laad_posities(mmsi, limiet):
    with engine.connect() as conn:
        df = pd.read_sql(text("""
            SELECT time, latitude, longitude, sog, cog FROM position
            WHERE mmsi = :mmsi AND time IS NOT NULL
              AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180
              AND sog > 0 AND sog <= 60 AND cog >= 0 AND cog < 360
            ORDER BY time ASC LIMIT :limiet
        """), conn, params={"mmsi": int(mmsi), "limiet": int(limiet)})
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df.sort_values("time").drop_duplicates("time").reset_index(drop=True)

# Koppel elke startmeting aan een echte meting rond t + minuten.
def maak_dataset(posities, minuten, tolerantie_minuten):
    bron = posities.copy()
    bron["doeltijd"] = bron["time"] + pd.Timedelta(minutes=minuten)
    toekomst = posities[["time", "latitude", "longitude"]].rename(
        columns={"time": "werkelijke_tijd", "latitude": "doel_lat", "longitude": "doel_lon"}
    )
    # merge_asof vereist gesorteerde tijdkolommen
    data = pd.merge_asof(
        bron.sort_values("doeltijd"),
        toekomst.sort_values("werkelijke_tijd"),
        left_on="doeltijd",
        right_on="werkelijke_tijd",
        direction="nearest",
        tolerance=pd.Timedelta(minutes=tolerantie_minuten),
    )
    data = data.dropna(subset=["doel_lat", "doel_lon"])
    data = data[(data["werkelijke_tijd"] > data["time"]) & (data["sog"] > 0)]
    data = data.sort_values("time").reset_index(drop=True)
    data["koers_sin"] = np.sin(np.radians(data["cog"]))
    data["koers_cos"] = np.cos(np.radians(data["cog"]))
    return data

# 1. Kies het schip en de voorspeltijd.
st.title("Random Forest – AIS-positie voorspellen")
naam = st.text_input("Scheepsnaam")
if not naam:
    st.stop()
schepen = zoek_schepen_lokaal(naam)
if schepen.empty:
    st.warning("Geen schip gevonden")
    st.stop()

opties = {f"{r['name']} ({r['mmsi']}) – {r['aantal']} posities": int(r['mmsi'])
          for _, r in schepen.iterrows()}
mmsi = opties[st.selectbox("Schip", list(opties))]
minuten = st.selectbox("Minuten vooruit", [5, 10, 15, 30, 60])
limiet = 5000
tolerantie = 2
instellingen = (mmsi, minuten, limiet, tolerantie)

# 2. Train op de oudste 80%; test op de nieuwste 20%.
if st.button("Train en test Random Forest"):
    posities = laad_posities(mmsi, limiet)
    dataset = maak_dataset(posities, minuten, tolerantie)
    if len(dataset) < 100:
        st.warning("Te weinig start- en vervolgmetingen. Kies meer data of een andere tijd.")
        st.stop()

    split = int(len(dataset) * 0.8)
    train, test = dataset.iloc[:split].copy(), dataset.iloc[split:].copy()
    # Geen trainingsdoelposities uit de testperiode gebruiken.
    train = train[train["werkelijke_tijd"] < test["time"].min()].copy()
    if train.empty:
        st.warning("Geen bruikbare trainingsmetingen")
        st.stop()

    # Model leert verplaatsing naar noord en oost in meters.
    meter_per_graad = 111_320
    train["noord"] = (train["doel_lat"] - train["latitude"]) * meter_per_graad
    train["oost"] = (train["doel_lon"] - train["longitude"]) * meter_per_graad * np.cos(np.radians(train["latitude"]))
    kenmerken = ["latitude", "longitude", "sog", "koers_sin", "koers_cos"]
    model = RandomForestRegressor(n_estimators=150, min_samples_leaf=3,
                                  random_state=42, n_jobs=-1)
    model.fit(train[kenmerken], train[["noord", "oost"]])
    verplaatsing = model.predict(test[kenmerken])

    rf_lat = test["latitude"].to_numpy() + verplaatsing[:, 0] / meter_per_graad
    rf_lon = test["longitude"].to_numpy() + verplaatsing[:, 1] / (meter_per_graad * np.cos(np.radians(test["latitude"].to_numpy())))



    gc_lat, gc_lon = great_circle(test["latitude"].to_numpy(), test["longitude"].to_numpy(),
                                  test["sog"].to_numpy(), test["cog"].to_numpy(), minuten)
    werk_lat, werk_lon = test["doel_lat"].to_numpy(), test["doel_lon"].to_numpy()
    rf_fout = afstand_meter(rf_lat, rf_lon, werk_lat, werk_lon)
    gc_fout = afstand_meter(gc_lat, gc_lon, werk_lat, werk_lon)

    # Hybride: volg de vaarweg; RF helpt bij een splitsing.
    with st.spinner("Vaarwegen volgen..."):
        wegen, knopen = laad_vaarwegnetwerk()
        hybride = [hybride_voorspelling(wegen, knopen, float(r.latitude), float(r.longitude),
                    float(r.sog), float(r.cog), float(rf_lat[i]), float(rf_lon[i]), minuten)
                    for i, r in enumerate(test.itertuples(index=False))]
    hybride_fout = np.array([afstand_meter(h["lat"], h["lon"], werk_lat[i], werk_lon[i])
                             if h else np.nan for i, h in enumerate(hybride)])
    geldig = np.isfinite(hybride_fout)

    # Bewaren zodat een ander testtijdstip niet opnieuw traint.
    st.session_state["rf_resultaten"] = dict(
        instellingen=instellingen, posities=posities, dataset=dataset, train=train, test=test,
        rf_lat=rf_lat, rf_lon=rf_lon, gc_lat=gc_lat, gc_lon=gc_lon,
        werk_lat=werk_lat, werk_lon=werk_lon, rf_fout=rf_fout, gc_fout=gc_fout,
        hybride=hybride, hybride_fout=hybride_fout, geldig=geldig)

# 3. Resultaten en kaart.
r = st.session_state.get("rf_resultaten")
if r is None or r["instellingen"] != instellingen:
    st.info("Klik op Train en test Random Forest")
    st.stop()

st.subheader("Resultaten")
st.write(f"Training: {len(r['train'])} metingen | Test: {len(r['test'])} metingen")
a, b, c = st.columns(3)
a.metric("Random Forest", f"{np.mean(r['rf_fout']):.0f} m")
b.metric("Great-circle", f"{np.mean(r['gc_fout']):.0f} m")
c.metric("Hybride", f"{np.mean(r['hybride_fout'][r['geldig']]):.0f} m" if r['geldig'].any() else "Geen route")
st.caption("Gemiddelde afstand tot de werkelijke AIS-positie. Hybride alleen waar een route gevonden is.")

labels = [f"{i:04d} | {t:%Y-%m-%d %H:%M:%S}" for i, t in enumerate(r["test"]["time"])]
keuze = st.selectbox("AIS-starttijd", labels)
i = int(keuze.split(" | ")[0])
meting = r["test"].iloc[i]
st.write(f"Voorspelling voor {minuten} minuten later | SOG: {meting['sog']:.1f} kn | COG: {meting['cog']:.1f}°")

punten = [
    {"latitude": meting["latitude"], "longitude": meting["longitude"], "kleur": "#2196F3"},
    {"latitude": r["rf_lat"][i], "longitude": r["rf_lon"][i], "kleur": "#9C27B0"},
    {"latitude": r["gc_lat"][i], "longitude": r["gc_lon"][i], "kleur": "#FF9800"},
    {"latitude": r["werk_lat"][i], "longitude": r["werk_lon"][i], "kleur": "#4CAF50"},
]
if r["hybride"][i]:
    h = r["hybride"][i]
    punten.append({"latitude": h["lat"], "longitude": h["lon"], "kleur": "#00BCD4"})
st.map(pd.DataFrame(punten), latitude="latitude", longitude="longitude", color="kleur", size=100)
st.caption("🔵 Start · 🟣 Random Forest · 🟠 Great-circle · 🟢 Werkelijk · 🩵 Hybride")

st.write("Trainingsperiode:", train["time"].min(), "t/m", train["time"].max())
st.write("Testperiode:", test["time"].min(), "t/m", test["time"].max())