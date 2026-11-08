import time
import streamlit as st
from sqlalchemy import text

from ais_api import zoek_schepen, haal_posities_op
from database import (
    engine,
    controleer_schip,
    sla_schip_op,
    sla_posities_op,
)

st.title("AIS Scheepsbeheer")
st.write("Zoek een schip en beheer de AIS-positiegegevens.")

# 1. Schip zoeken
naam = st.text_input("Scheepsnaam")

if st.button("Zoek schip"):
    if naam.strip():
        try:
            with st.spinner("Zoeken in AIS-database..."):
                st.session_state["schepen"] = zoek_schepen(naam.strip())
        except Exception as e:
            st.error(f"Zoeken mislukt: {e}")
    else:
        st.warning("Vul een scheepsnaam in.")

# 2. Schip selecteren
if "schepen" in st.session_state:
    schepen = st.session_state["schepen"]

    if not schepen:
        st.info("Geen schepen gevonden.")
        st.stop()

    opties = {
        f"{s['name']} ({s['mmsi']})": s
        for s in schepen
    }

    keuze = st.selectbox("Selecteer schip", list(opties))
    schip = opties[keuze]
    mmsi = schip["mmsi"]

    # 3. Lokale gegevens controleren
    lokaal = controleer_schip(mmsi)

    st.subheader("Beschikbare gegevens")
    st.write("Schip:", schip["name"])
    st.write("MMSI:", mmsi)

    if lokaal:
        st.success("Schip staat in eigen database.")
        st.write("Aantal posities:", lokaal["aantal"])
        st.write("Eerste positie:", lokaal["eerste"])
        st.write("Laatste positie:", lokaal["laatste"])
    else:
        st.warning("Schip staat nog niet in eigen database.")

    # 4. Verwijderen uit de eigen database (niet uit de AIS API)
    if lokaal:
        st.subheader("Schip verwijderen")
        st.caption("Verwijdert het schip en alle bijbehorende AIS-posities uit de lokale database.")

        bevestigen = st.checkbox(
            f"Ik wil {schip['name']} ({mmsi}) en alle lokale AIS-posities verwijderen",
            key=f"bevestig_verwijderen_{mmsi}",
        )

        if st.button(
            "🗑️ Verwijder schip en AIS-posities",
            disabled=not bevestigen,
            type="secondary",
            key=f"verwijder_{mmsi}",
        ):
            try:
                # Eén transactie: bij een fout wordt alles teruggedraaid.
                with engine.begin() as conn:
                    verwijderd = conn.execute(
                        text("DELETE FROM position WHERE mmsi = :mmsi"),
                        {"mmsi": mmsi},
                    ).rowcount
                    conn.execute(
                        text("DELETE FROM ship WHERE mmsi = :mmsi"),
                        {"mmsi": mmsi},
                    )

                st.session_state["verwijdermelding"] = (
                    f"Schip {schip['name']} ({mmsi}) verwijderd, "
                    f"inclusief {verwijderd} AIS-posities."
                )
                st.rerun()
            except Exception as e:
                st.error(f"Verwijderen mislukt: {e}")

    if "verwijdermelding" in st.session_state:
        st.success(st.session_state.pop("verwijdermelding"))

    # 5. Importeren
    if st.button("Importeer ontbrekende AIS-posities"):
        start = time.perf_counter()
        offset = 0
        batch_grootte = 1000
        toegevoegd = 0
        verwerkt = 0
        compleet = False

        voortgang = st.empty()

        try:
            # Eerst het schip opslaan
            sla_schip_op(schip)

            # Daarna de posities ophalen
            while True:
                posities = haal_posities_op(
                    mmsi,
                    offset=offset,
                    limit=batch_grootte,
                )

                if not posities:
                    compleet = True
                    break

                nieuw = sla_posities_op(posities)
                toegevoegd += nieuw
                verwerkt += len(posities)
                offset += len(posities)

                voortgang.info(
                    f"{verwerkt} posities verwerkt, "
                    f"{toegevoegd} nieuw toegevoegd."
                )

                if len(posities) < batch_grootte:
                    compleet = True
                    break

            duur = time.perf_counter() - start

            if compleet:
                st.success("Import voltooid!")

            st.write("Verwerkte posities:", verwerkt)
            st.write("Nieuw toegevoegd:", toegevoegd)
            st.write("Al aanwezig:", verwerkt - toegevoegd)
            st.write("Verstreken tijd:", round(duur, 2), "seconden")

            st.subheader("Bijgewerkte database")
            resultaat = controleer_schip(mmsi)
            st.write("Totaal lokaal:", resultaat["aantal"])

        except Exception as e:
            st.error(f"Import onderbroken: {e}")
            st.warning(
                "Eerder opgeslagen batches blijven bewaard. "
                "Je kunt de import opnieuw starten."
            )
