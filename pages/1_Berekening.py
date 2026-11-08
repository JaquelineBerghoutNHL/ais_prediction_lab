from login import controleer_login
controleer_login()

import pandas as pd
import streamlit as st
from sqlalchemy import text
from database import engine
from functies import great_circle, afstand_meter, laad_vaarwegnetwerk, vaarweg_voorspelling

st.title('Scheepspositie voorspellen')
zoeknaam = st.text_input('Scheepsnaam')

if zoeknaam:
    with engine.connect() as conn:
        schepen = conn.execute(text('SELECT mmsi, name FROM ship WHERE name ILIKE :naam ORDER BY name LIMIT 200'), {'naam': f'%{zoeknaam}%'}).mappings().all()

    if schepen:
        opties = {f"{s['name']} ({s['mmsi']})": s['mmsi'] for s in schepen}
        mmsi = opties[st.selectbox('Schip', list(opties))]

        with engine.connect() as conn:
            posities = conn.execute(text('''
                SELECT time, latitude, longitude, sog, cog FROM position
                WHERE mmsi = :mmsi AND latitude IS NOT NULL AND longitude IS NOT NULL
                AND sog IS NOT NULL AND cog BETWEEN 0 AND 360
                ORDER BY time DESC LIMIT 100
            '''), {'mmsi': mmsi}).mappings().all()

        if posities:
            meting = st.selectbox('AIS-startmeting', posities, format_func=lambda p: str(p['time']))
            minuten = st.selectbox('Minuten vooruit', [5, 10, 15, 30, 60])
            lat, lon = float(meting['latitude']), float(meting['longitude'])
            sog, cog = float(meting['sog']), float(meting['cog'])
            afstand_km = sog * minuten / 60 * 1.852
            st.write(f'SOG: {sog} kn | COG: {cog}° | Afstand: {afstand_km:.2f} km')

            gc_lat, gc_lon = great_circle(lat, lon, sog, cog, minuten)
            wegen, knopen = laad_vaarwegnetwerk()
            rd = vaarweg_voorspelling(wegen, knopen, lat, lon, sog, cog, minuten)
            tijdstip = meting['time'] + pd.Timedelta(minutes=minuten)

            with engine.connect() as conn:
                werkelijk = conn.execute(text('''
                    SELECT time, latitude, longitude FROM position
                    WHERE mmsi = :mmsi AND time BETWEEN :tijd - INTERVAL '2 minutes'
                    AND :tijd + INTERVAL '2 minutes'
                    ORDER BY ABS(EXTRACT(EPOCH FROM (time - :tijd))) LIMIT 1
                '''), {'mmsi': mmsi, 'tijd': tijdstip}).mappings().first()

            punten = [
                {'latitude': lat, 'longitude': lon, 'kleur': '#2196F3'},
                {'latitude': gc_lat, 'longitude': gc_lon, 'kleur': '#FF9800'}
            ]
            if rd:
                punten.append({'latitude': rd[0], 'longitude': rd[1], 'kleur': '#9C27B0'})

            if werkelijk and werkelijk['latitude'] is not None and werkelijk['longitude'] is not None:
                echt_lat, echt_lon = float(werkelijk['latitude']), float(werkelijk['longitude'])
                punten.append({'latitude': echt_lat, 'longitude': echt_lon, 'kleur': '#4CAF50'})
                fout_gc = afstand_meter(gc_lat, gc_lon, echt_lat, echt_lon)
                st.metric('Fout great-circle', f'{fout_gc:.0f} meter')
                if rd:
                    fout_rd = afstand_meter(rd[0], rd[1], echt_lat, echt_lon)
                    st.metric('Fout vaarweg', f'{fout_rd:.0f} meter')
            else:
                st.info('Geen werkelijke AIS-meting binnen 2 minuten gevonden.')

            if not rd:
                st.info('Geen aansluitende vaarwegroute gevonden.')
            st.map(pd.DataFrame(punten), latitude='latitude', longitude='longitude', color='kleur', size=100)
            st.caption('🔵 Start · 🟠 Great-circle · 🟣 Vaarweg · 🟢 Werkelijk')
        else:
            st.info('Geen AIS-metingen gevonden.')
    else:
        st.info('Geen schip gevonden.')
