import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy import text

load_dotenv()


engine = create_engine(
    f"postgresql+psycopg2://"
    f"{os.getenv('DB_USER')}:"
    f"{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:"
    f"{os.getenv('DB_PORT')}/"
    f"{os.getenv('DB_NAME')}",
    pool_pre_ping=True
)


def controleer_schip(mmsi):
    with engine.connect() as conn:
        return conn.execute(
            text("""
                SELECT
                    s.name,
                    COUNT(p.time) AS aantal,
                    MIN(p.time) AS eerste,
                    MAX(p.time) AS laatste
                FROM ship s
                LEFT JOIN position p ON s.mmsi = p.mmsi
                WHERE s.mmsi = :mmsi
                GROUP BY s.mmsi, s.name
            """),
            {"mmsi": mmsi}
        ).mappings().first()


def sla_schip_op(schip):
    velden = [
        "mmsi", "imo", "name", "type",
        "flagcountry", "callsign",
        "dim_a", "dim_b", "dim_c", "dim_d"
    ]

    gegevens = {veld: schip.get(veld) for veld in velden}

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO ship (
                    mmsi, imo, name, type, flagcountry,
                    callsign, dim_a, dim_b, dim_c, dim_d
                )
                VALUES (
                    :mmsi, :imo, :name, :type, :flagcountry,
                    :callsign, :dim_a, :dim_b, :dim_c, :dim_d
                )
                ON CONFLICT (mmsi) DO NOTHING
            """),
            gegevens
        )


def sla_posities_op(posities):
    if not posities:
        return 0

    velden = [
        "mmsi", "time", "longitude", "latitude",
        "cog", "sog", "heading", "rot",
        "pac", "navstat", "draught",
        "destination", "eta"
    ]

    gegevens = [
        {veld: positie.get(veld) for veld in velden}
        for positie in posities
    ]

    for positie in gegevens:
        if positie["pac"] is not None:
            positie["pac"] = bool(positie["pac"])

    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO position (
                    mmsi, time, longitude, latitude,
                    cog, sog, heading, rot, pac,
                    navstat, draught, destination, eta
                )
                VALUES (
                    :mmsi, :time, :longitude, :latitude,
                    :cog, :sog, :heading, :rot, :pac,
                    :navstat, :draught, :destination, :eta
                )
                ON CONFLICT DO NOTHING
            """),
            gegevens
        )

        return result.rowcount
