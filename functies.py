import math
import numpy as np
import pandas as pd
import geopandas as gpd
import streamlit as st
from shapely.geometry import Point
from pygeodesy import haversine

def afstand_meter(lat1, lon1, lat2, lon2):
    if np.isscalar(lat1):
        return haversine(float(lat1), float(lon1), float(lat2), float(lon2), radius=6371000)
    return np.array([haversine(a, b, c, d, radius=6371000)
                     for a, b, c, d in zip(lat1, lon1, lat2, lon2)])

def great_circle(lat, lon, sog, cog, minuten):
    lat1, lon1 = np.radians(lat), np.radians(lon)
    bearing = np.radians(cog)
    hoek = (sog * minuten / 60 * 1.852) / 6371.0
    lat2 = np.arcsin(np.sin(lat1) * np.cos(hoek) + np.cos(lat1) * np.sin(hoek) * np.cos(bearing))
    lon2 = lon1 + np.arctan2(np.sin(bearing) * np.sin(hoek) * np.cos(lat1), np.cos(hoek) - np.sin(lat1) * np.sin(lat2))
    return np.degrees(lat2), (np.degrees(lon2) + 180) % 360 - 180


@st.cache_resource
def laad_vaarwegnetwerk():
    wegen = gpd.read_file("vaarwegvakken/vaarwegvakkenLine.shp")
    if wegen.crs is None:
        raise ValueError("De vaarwegdataset heeft geen coördinatenstelsel.")
    wegen = wegen.to_crs("EPSG:28992")
    wegen = wegen[wegen.geometry.geom_type == "LineString"].copy()
    knopen = {}
    for idx, vak in wegen.iterrows():
        for veld, richting in (("vwj_id_beg", 1), ("vwj_id_end", -1)):
            knoop = vak[veld]
            if pd.notna(knoop):
                knopen.setdefault(knoop, []).append((idx, richting))
    return wegen, knopen


def richting_koers(lijn, afstand, richting):
    a = lijn.interpolate(max(0, afstand - 15))
    b = lijn.interpolate(min(lijn.length, afstand + 15))
    dx, dy = (b.x - a.x) * richting, (b.y - a.y) * richting
    return (math.degrees(math.atan2(dx, dy)) + 360) % 360


def hoekverschil(a, b):
    return abs((a - b + 180) % 360 - 180)

def vaarweg_voorspelling(wegen, knopen, lat, lon, sog, cog, minuten):
    """Onafhankelijke RD-voorspelling: koersgestuurde takkeuze, zonder RF."""
    if sog <= 0:
        return None
    start = gpd.GeoSeries([Point(float(lon), float(lat))], crs='EPSG:4326').to_crs(wegen.crs).iloc[0]
    afstanden = wegen.geometry.distance(start)
    idx = afstanden.idxmin()
    if float(afstanden.loc[idx]) > 250:
        return None
    vak = wegen.loc[idx]
    positie = vak.geometry.project(start)
    richting = 1 if hoekverschil(cog, richting_koers(vak.geometry, positie, 1)) <= 90 else -1
    resterend = sog * minuten / 60 * 1852
    bezocht = set()
    for _ in range(30):
        lijn = vak.geometry
        beschikbaar = lijn.length - positie if richting == 1 else positie
        if resterend <= beschikbaar:
            punt = lijn.interpolate(positie + richting * resterend)
            gps = gpd.GeoSeries([punt], crs=wegen.crs).to_crs('EPSG:4326').iloc[0]
            return (float(gps.y), float(gps.x))
        resterend -= beschikbaar
        bezocht.add(idx)
        einde = lijn.interpolate(lijn.length if richting == 1 else 0)
        vorige_koers = richting_koers(lijn, lijn.length if richting == 1 else 0, richting)
        knoop = vak['vwj_id_end'] if richting == 1 else vak['vwj_id_beg']
        if pd.isna(knoop):
            return None
        opties = []
        for nieuw_idx, nieuw_richting in knopen.get(knoop, []):
            if nieuw_idx in bezocht:
                continue
            nieuw_lijn = wegen.loc[nieuw_idx].geometry
            begin = nieuw_lijn.interpolate(0 if nieuw_richting == 1 else nieuw_lijn.length)
            if einde.distance(begin) > 30:
                continue
            nieuwe_koers = richting_koers(nieuw_lijn, 0 if nieuw_richting == 1 else nieuw_lijn.length, nieuw_richting)
            bocht = hoekverschil(vorige_koers, nieuwe_koers)
            if bocht <= 100:
                opties.append((bocht, nieuw_idx, nieuw_richting))
        if not opties:
            return None
        _, idx, richting = min(opties)
        vak = wegen.loc[idx]
        positie = 0 if richting == 1 else vak.geometry.length
    return None


def hybride_voorspelling(wegen, knopen, lat, lon, sog, cog,
                         rf_lat, rf_lon, minuten, max_startafstand=250):
    """
    RF kiest bij splitsingen de richting die het beste naar zijn voorspelde
    eindpunt wijst. De afgelegde afstand blijft bepaald door AIS-SOG.
    Retourneert None als geen betrouwbare aansluiting wordt gevonden.
    """
    begin = gpd.GeoSeries([Point(float(lon), float(lat))], crs="EPSG:4326").to_crs(wegen.crs).iloc[0]
    doel = gpd.GeoSeries([Point(float(rf_lon), float(rf_lat))], crs="EPSG:4326").to_crs(wegen.crs).iloc[0]
    afstanden = wegen.geometry.distance(begin)
    idx = afstanden.idxmin()
    startafstand = float(afstanden.loc[idx])
    if startafstand > max_startafstand:
        return None
    vak = wegen.loc[idx]
    lijn = vak.geometry
    positie = lijn.project(begin)
    koers_vooruit = richting_koers(lijn, positie, 1)
    richting = 1 if hoekverschil(cog, koers_vooruit) <= 90 else -1
    resterend = float(sog) * minuten / 60 * 1852
    bezocht = set()
    aantal_vakken = 1

    for _ in range(30):
        lijn = vak.geometry
        beschikbaar = lijn.length - positie if richting == 1 else positie
        if resterend <= beschikbaar:
            punt = lijn.interpolate(positie + richting * resterend)
            gps = gpd.GeoSeries([punt], crs=wegen.crs).to_crs("EPSG:4326").iloc[0]
            return {"lat": gps.y, "lon": gps.x, "vakken": aantal_vakken,
                    "startafstand": startafstand, "rf_afstand_tot_route": punt.distance(doel)}
        resterend -= beschikbaar
        bezocht.add(idx)
        einde = lijn.interpolate(lijn.length if richting == 1 else 0)
        vorige_koers = richting_koers(lijn, lijn.length if richting == 1 else 0, richting)
        knoop = vak["vwj_id_end"] if richting == 1 else vak["vwj_id_beg"]
        if pd.isna(knoop):
            return None
        opties = []
        for nieuw_idx, nieuw_richting in knopen.get(knoop, []):
            if nieuw_idx in bezocht:
                continue
            nieuw = wegen.loc[nieuw_idx]
            nieuw_lijn = nieuw.geometry
            nieuw_begin = nieuw_lijn.interpolate(0 if nieuw_richting == 1 else nieuw_lijn.length)
            if einde.distance(nieuw_begin) > 30:
                continue
            nieuwe_koers = richting_koers(nieuw_lijn, 0 if nieuw_richting == 1 else nieuw_lijn.length, nieuw_richting)
            bocht = hoekverschil(vorige_koers, nieuwe_koers)
            if bocht > 100:
                continue
            # RF is een aanwijzing bij splitsingen, geen directe snap naar land/ander water.
            kijkafstand = min(resterend, nieuw_lijn.length)
            vooruit = nieuw_lijn.interpolate((kijkafstand if nieuw_richting == 1 else nieuw_lijn.length - kijkafstand))
            score = vooruit.distance(doel) + 4 * bocht
            opties.append((score, nieuw_idx, nieuw_richting))
        if not opties:
            return None
        _, idx, richting = min(opties)
        vak = wegen.loc[idx]
        positie = 0 if richting == 1 else vak.geometry.length
        aantal_vakken += 1
    return None


