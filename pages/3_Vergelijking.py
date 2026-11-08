from login import controleer_login
controleer_login()

import numpy as np
import pandas as pd
import streamlit as st
from functies import afstand_meter, laad_vaarwegnetwerk, vaarweg_voorspelling

st.title('Vergelijking – AIS-positievoorspellingen')
st.write('Vergelijk vier methoden op dezelfde, chronologisch gescheiden testgegevens.')

resultaat = st.session_state.get('rf_resultaten')
if resultaat is None:
    st.info('Open eerst **Random Forest**, kies een schip en klik op **Train en test Random Forest**. Ga daarna terug naar Vergelijking. De resultaten blijven binnen dezelfde Streamlit-sessie beschikbaar.')
    st.stop()

# De vergelijking gebruikt exact de testset en voorspellingen van pagina 2.
test = resultaat['test'].reset_index(drop=True)
rf_lat = np.asarray(resultaat['rf_lat'], dtype=float)
rf_lon = np.asarray(resultaat['rf_lon'], dtype=float)
gc_lat = np.asarray(resultaat['gc_lat'], dtype=float)
gc_lon = np.asarray(resultaat['gc_lon'], dtype=float)
werk_lat = np.asarray(resultaat['werk_lat'], dtype=float)
werk_lon = np.asarray(resultaat['werk_lon'], dtype=float)
rf_fout = np.asarray(resultaat['rf_fout'], dtype=float)
gc_fout = np.asarray(resultaat['gc_fout'], dtype=float)
hybride = resultaat['hybride']
hyb_fout = np.asarray(resultaat['hybride_fout'], dtype=float)

if not len(test):
    st.warning('Geen testmetingen beschikbaar.')
    st.stop()


@st.cache_data(show_spinner=False)
def bereken_rd(startdata, minuten):
    wegen, knopen = laad_vaarwegnetwerk()
    return [vaarweg_voorspelling(wegen, knopen, lat, lon, sog, cog, minuten)
            for lat, lon, sog, cog in startdata]

mmsi, minuten, limiet, tolerantie = resultaat['instellingen']
st.caption(f'Schip MMSI {mmsi} · {minuten} minuten vooruit · {len(test)} testmetingen · SOG > 0')
startdata = tuple((float(r.latitude), float(r.longitude), float(r.sog), float(r.cog)) for r in test.itertuples(index=False))
try:
    with st.spinner('Zelfstandige vaarwegvoorspellingen berekenen (alleen de eerste keer)...'):
        rd = bereken_rd(startdata, int(minuten))
except Exception as exc:
    st.error(f'Vaarweggegevens konden niet worden verwerkt: {exc}')
    st.stop()

rd_fout = np.array([
    afstand_meter(p[0], p[1], werk_lat[i], werk_lon[i]) if p is not None else np.nan
    for i, p in enumerate(rd)
])

methoden = {
    'Great-circle': gc_fout,
    'Random Forest': rf_fout,
    'Vaarweg (RD)': rd_fout,
    'Hybride RF + RD': hyb_fout,
}

st.subheader('1. Resultaten van alle methoden')
rijen = []
for naam, fouten in methoden.items():
    geldig = np.isfinite(fouten)
    rijen.append({
        'Methode': naam,
        'Beschikbaar': f'{geldig.sum()} / {len(test)}',
        'Gemiddelde fout (m)': round(float(np.mean(fouten[geldig])), 1) if geldig.any() else np.nan,
        'Mediane fout (m)': round(float(np.median(fouten[geldig])), 1) if geldig.any() else np.nan,
    })
st.dataframe(pd.DataFrame(rijen), hide_index=True, use_container_width=True)
st.caption('Let op: de bovenstaande gemiddelden zijn per methode berekend op alle beschikbare voorspellingen. De aantallen kunnen verschillen.')

st.subheader('2. Eerlijke vergelijking op dezelfde testmetingen')
alle_geldig = np.logical_and.reduce([np.isfinite(f) for f in methoden.values()])
st.write(f'Voor **{int(alle_geldig.sum())} van de {len(test)}** testmetingen zijn alle vier voorspellingen beschikbaar.')
if alle_geldig.any():
    gelijk = pd.DataFrame({
        'Methode': list(methoden),
        'Gemiddelde fout (m)': [round(float(np.mean(f[alle_geldig])), 1) for f in methoden.values()],
        'Mediane fout (m)': [round(float(np.median(f[alle_geldig])), 1) for f in methoden.values()],
    })
    st.dataframe(gelijk, hide_index=True, use_container_width=True)
    st.bar_chart(gelijk.set_index('Methode')['Gemiddelde fout (m)'])
    beste = gelijk.loc[gelijk['Gemiddelde fout (m)'].idxmin(), 'Methode']
    st.success(f'Op deze gemeenschappelijke testset heeft **{beste}** de kleinste gemiddelde fout.')
else:
    st.warning('Er zijn geen testmetingen waarop alle vier methoden beschikbaar zijn.')

st.subheader('3. Bekijk één AIS-testmeting')
keuzes = list(range(len(test)))
nummer = st.selectbox(
    'Kies een AIS-starttijd', keuzes,
    format_func=lambda i: str(test.iloc[i]['time']),
)
rij = test.iloc[nummer]
st.write(f"Starttijd: **{rij['time']}** · Werkelijke vervolgmeting: **{rij['werkelijke_tijd']}**")
st.write(f"SOG: **{float(rij['sog']):.1f} kn** · COG: **{float(rij['cog']):.1f}°**")

punten = [
    {'latitude': float(rij['latitude']), 'longitude': float(rij['longitude']), 'kleur': '#2196F3', 'type': 'Startpositie'},
    {'latitude': float(werk_lat[nummer]), 'longitude': float(werk_lon[nummer]), 'kleur': '#4CAF50', 'type': 'Werkelijke positie'},
]
opties = [
    ('Great-circle', gc_lat[nummer], gc_lon[nummer], '#FF9800'),
    ('Random Forest', rf_lat[nummer], rf_lon[nummer], '#9C27B0'),
    ('Vaarweg (RD)', rd[nummer][0] if rd[nummer] else None, rd[nummer][1] if rd[nummer] else None, '#00A884'),
    ('Hybride RF + RD', hybride[nummer]['lat'] if hybride[nummer] else None, hybride[nummer]['lon'] if hybride[nummer] else None, '#00BFFF'),
]

zichtbaar = st.multiselect('Toon voorspellingen op de kaart', [x[0] for x in opties], default=[x[0] for x in opties])
for naam, lat, lon, kleur in opties:
    if naam in zichtbaar and lat is not None and lon is not None:
        punten.append({'latitude': float(lat), 'longitude': float(lon), 'kleur': kleur, 'type': naam})

st.map(pd.DataFrame(punten), latitude='latitude', longitude='longitude', color='kleur', size=100)
st.caption('🔵 Start · 🟢 Werkelijk · 🟠 Great-circle · 🟣 Random Forest · 🟩 Vaarweg (RD) · 🩵 Hybride')

st.markdown('**Afwijking bij deze meting**')
for naam, fouten in methoden.items():
    fout = fouten[nummer]
    st.write(f'{naam}: **{fout:.0f} meter**' if np.isfinite(fout) else f'{naam}: geen voorspelling beschikbaar')

