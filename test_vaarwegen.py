import geopandas as gpd
from shapely.geometry import Point
import streamlit as st
import pandas as pd
import math



@st.cache_data
def laad_vaarwegen():
    return gpd.read_file(
        "vaarwegvakken/vaarwegvakkenLine.shp"
    )

vaarwegen = laad_vaarwegen()


print("Aantal vaarwegvakken:", len(vaarwegen))
print("Coördinatenstelsel:", vaarwegen.crs)
print("Kolommen:", vaarwegen.columns.tolist())


# AIS-positie van ISAIAH
latitude = 51.798100
longitude = 4.840340

# Zet AIS-coördinaten om naar RD
punt = gpd.GeoSeries(
    [Point(longitude, latitude)],
    crs="EPSG:4326"
).to_crs(vaarwegen.crs).iloc[0]

# Bereken afstand tot iedere vaarweg
vaarwegen["afstand"] = vaarwegen.geometry.distance(punt)

# Zoek de dichtstbijzijnde vaarweg
dichtstbij = vaarwegen.loc[
    vaarwegen["afstand"].idxmin()
]

print("Dichtstbijzijnde vaarweg:", dichtstbij["vwg_naam"])
print("Afstand tot vaarweg:", round(dichtstbij["afstand"], 1), "meter")
print("Vaarwegvak ID:", dichtstbij["vwk_id"])



# Positie van het schip op de vaarweglijn
lijn = dichtstbij["geometry"]

afstand_op_lijn = lijn.project(punt)
punt_op_lijn = lijn.interpolate(afstand_op_lijn)

print("Lengte vaarwegvak:", round(lijn.length), "meter")
print("Afstand vanaf begin lijn:", round(afstand_op_lijn), "meter")
print("Afstand tot einde lijn:",
      round(lijn.length - afstand_op_lijn), "meter")

print("Type geometrie:", lijn.geom_type)



import math

# Koers van ISAIAH
koers_schip = 262.2

# Twee punten op de vaarweglijn, 50 meter uit elkaar
voor = lijn.interpolate(
    min(afstand_op_lijn + 25, lijn.length)
)

achter = lijn.interpolate(
    max(afstand_op_lijn - 25, 0)
)

# Richting van de lijn berekenen
dx = voor.x - achter.x
dy = voor.y - achter.y

richting_lijn = (
    math.degrees(math.atan2(dx, dy)) + 360
) % 360

# Verschil tussen scheepskoers en lijnrichting
verschil = (
    (koers_schip - richting_lijn + 180) % 360
) - 180

if abs(verschil) <= 90:
    richting = "vooruit"
else:
    richting = "achteruit"

print("Richting vaarweglijn:", round(richting_lijn, 1))
print("Koers schip:", koers_schip)
print("Schip volgt de lijn:", richting)


# Voorspelling langs de vaarweg
snelheid = 7.4
minuten = 10

# Afstand in meters
afstand_meters = snelheid * (minuten / 60) * 1852

# Nieuwe positie op de vaarweglijn
if richting == "vooruit":
    nieuwe_afstand = afstand_op_lijn + afstand_meters
else:
    nieuwe_afstand = afstand_op_lijn - afstand_meters

# Controleren of de voorspelling binnen het vaarwegvak blijft
if 0 <= nieuwe_afstand <= lijn.length:
    voorspeld_punt = lijn.interpolate(nieuwe_afstand)

    # Omzetten naar GPS-coördinaten
    voorspelling = gpd.GeoSeries(
        [voorspeld_punt],
        crs=vaarwegen.crs
    ).to_crs("EPSG:4326").iloc[0]

    print("Voorspelde latitude:", round(voorspelling.y, 6))
    print("Voorspelde longitude:", round(voorspelling.x, 6))
    print("Afstand langs vaarweg:", round(afstand_meters), "meter")
else:
    print("Voorspelling valt buiten dit vaarwegvak.")



# Oorspronkelijke voorspelling (great-circle)
lat1 = math.radians(latitude)
lon1 = math.radians(longitude)
koers = math.radians(koers_schip)

R = 6371000
d = afstand_meters / R

lat2 = math.asin(
    math.sin(lat1) * math.cos(d)
    + math.cos(lat1) * math.sin(d) * math.cos(koers)
)

lon2 = lon1 + math.atan2(
    math.sin(koers) * math.sin(d) * math.cos(lat1),
    math.cos(d) - math.sin(lat1) * math.sin(lat2)
)

print("Great-circle latitude:", round(math.degrees(lat2), 6))
print("Great-circle longitude:", round(math.degrees(lon2), 6))
