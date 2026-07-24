import csv
from datetime import datetime
from database import get_db


# ============================================================
# CONFIGURATION
# ============================================================

CSV_FILE = "signals_export (7).csv"


# ============================================================
# FONCTIONS DE CONVERSION
# ============================================================

def clean_value(value):
    """
    Transforme une valeur vide en None.
    """
    if value is None:
        return None

    value = value.strip()

    if value == "":
        return None

    return value


def parse_float(value):
    """
    Convertit une valeur en float.
    Exemple :
    '1.25' -> 1.25
    ''     -> None
    """
    value = clean_value(value)

    if value is None:
        return None

    # Remplace une éventuelle virgule décimale par un point
    value = value.replace(",", ".")

    try:
        return float(value)
    except ValueError:
        print(f"⚠️ Impossible de convertir en nombre : {value}")
        return None


def parse_int(value):
    """
    Convertit une valeur en entier.
    """
    value = clean_value(value)

    if value is None:
        return None

    try:
        return int(float(value))
    except ValueError:
        print(f"⚠️ Impossible de convertir en entier : {value}")
        return None


def parse_datetime(value):
    """
    Convertit les dates du CSV en datetime Python.

    Formats attendus :
    2026-06-20 14:30
    2026-06-20 14:30:00
    """
    value = clean_value(value)

    if value is None:
        return None

    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
    ]

    for date_format in formats:
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            continue

    print(f"⚠️ Date impossible à lire : {value}")
    return None


# ============================================================
# IMPORTATION
# ============================================================

def main():

    print("🔌 Connexion à PostgreSQL...")

    conn = None
    cur = None

    imported = 0
    skipped = 0
    errors = 0

    try:

        # Connexion à PostgreSQL
        conn = get_db()
        cur = conn._conn.cursor()

        print("✅ Connexion réussie\n")

        # Ouverture du CSV
        with open(
            CSV_FILE,
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as csv_file:

            reader = csv.DictReader(csv_file)

            print("📄 Lecture du CSV...\n")

            for row_number, row in enumerate(reader, start=2):

                signal_id = clean_value(row.get("ID"))

                if not signal_id:
                    print(
                        f"⚠️ Ligne {row_number} ignorée : "
                        "ID manquant"
                    )
                    errors += 1
                    continue

                try:

                    # SAVEPOINT : permet d'annuler UNIQUEMENT
                    # l'insertion en cours en cas d'erreur, sans
                    # perdre les signaux déjà importés dans la
                    # même transaction.
                    cur.execute("SAVEPOINT sp_import")

                    # ------------------------------------------------
                    # VÉRIFICATION DES DOUBLONS
                    # ------------------------------------------------

                    cur.execute(
                        """
                        SELECT id
                        FROM signals
                        WHERE id = %s
                        """,
                        (signal_id,)
                    )

                    if cur.fetchone():

                        print(
                            f"⏭️ Signal {signal_id} "
                            "existe déjà, ignoré"
                        )

                        skipped += 1
                        continue

                    # ------------------------------------------------
                    # INSERTION DU SIGNAL
                    # ------------------------------------------------

                    cur.execute(
                        """
                        INSERT INTO signals (

                            id,
                            user_id,
                            symbol,
                            direction,
                            entry_price,
                            sl,
                            tp,
                            score,

                            status,

                            validation_status,
                            validation_reason,
                            rejection_reason,

                            result_price,
                            result_pct,
                            pnl,

                            capital_before,
                            capital_after,

                            timeframe,
                            signal_type,
                            rr_ratio,
                            asset_class,
                            params_used,

                            created_at,
                            closed_at

                        )
                        VALUES (

                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,

                            %s,

                            %s,
                            %s,
                            %s,

                            %s,
                            %s,
                            %s,

                            %s,
                            %s,

                            %s,
                            %s,
                            %s,
                            %s,
                            %s,

                            %s,
                            %s

                        )
                        """,

                        (

                            # ID
                            signal_id,

                            # user_id
                            None,

                            # Informations du signal
                            clean_value(row.get("Symbole")),
                            clean_value(row.get("Direction")),

                            parse_float(row.get("Entree")),
                            parse_float(row.get("SL")),
                            parse_float(row.get("TP")),
                            parse_int(row.get("Score")),

                            # Statut
                            clean_value(row.get("Statut")),

                            # Validation
                            clean_value(
                                row.get("Validation")
                            ),

                            clean_value(
                                row.get("Raison validation")
                            ),

                            clean_value(
                                row.get("Raison rejet")
                            ),

                            # Résultat
                            parse_float(
                                row.get("Prix resultat")
                            ),

                            parse_float(
                                row.get("PnL%")
                            ),

                            parse_float(
                                row.get("PnL")
                            ),

                            # Capital
                            parse_float(
                                row.get("Capital avant")
                            ),

                            parse_float(
                                row.get("Capital apres")
                            ),

                            # Configuration
                            clean_value(
                                row.get("Timeframe")
                            ),

                            # Signaux provenant du CSV historique
                            "historical_import",

                            parse_float(
                                row.get("RR")
                            ),

                            clean_value(
                                row.get("Classe actif")
                            ),

                            clean_value(
                                row.get("Parametres")
                            ),

                            # Dates
                            parse_datetime(
                                row.get("Ouvert")
                            ),

                            parse_datetime(
                                row.get("Ferme")
                            )

                        )
                    )

                    imported += 1

                    print(
                        f"✅ Signal {signal_id} importé"
                    )

                except Exception as error:

                    errors += 1

                    print(
                        f"❌ Erreur avec le signal "
                        f"{signal_id} : {error}"
                    )

                    # N'annule QUE l'insertion de cette ligne
                    # (revient au SAVEPOINT), sans toucher aux
                    # signaux déjà importés dans cette transaction.
                    cur.execute("ROLLBACK TO SAVEPOINT sp_import")

        # Validation finale
        conn.commit()

        print("\n" + "=" * 60)
        print("📊 IMPORT TERMINÉ")
        print("=" * 60)

        print(
            f"✅ Signaux importés : {imported}"
        )

        print(
            f"⏭️ Signaux déjà présents : {skipped}"
        )

        print(
            f"❌ Erreurs : {errors}"
        )

        print("=" * 60)

    except FileNotFoundError:

        print(
            f"❌ Fichier introuvable : {CSV_FILE}"
        )

        print(
            "Vérifie que le CSV se trouve dans "
            "le même dossier que ce script."
        )

    except Exception as error:

        if conn:
            conn.rollback()

        print(
            f"❌ Erreur générale : {error}"
        )

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()

        print("\n🔒 Connexion PostgreSQL fermée.")


# ============================================================
# LANCEMENT
# ============================================================

if __name__ == "__main__":
    main()
