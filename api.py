from flask import Flask, request, jsonify
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import swisseph as swe
from datetime import datetime
import unicodedata

app = Flask(__name__)

# ============================================================
# FUNÇÕES ÚTEIS
# ============================================================

def remover_acentos(txt):
    if not isinstance(txt, str):
        return txt
    return ''.join(c for c in unicodedata.normalize('NFD', txt)
                   if unicodedata.category(c) != 'Mn')


def corrigir_cidade(raw_city):
    """
    Tenta corrigir automaticamente a cidade digitada.
    Remove acentos, tenta diferentes formatos e retorna
    coordenadas se possível.
    """
    geolocator = Nominatim(user_agent="astrology_app", timeout=10)
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

    city = remover_acentos(raw_city).strip()

    tentativas = [
        city,
        city + ", Brasil",
        city + ", Brazil",
        city.replace(" ", ""),
        city.split("-")[0],
        city.split(",")[0],
    ]

    for tentativa in tentativas:
        try:
            loc = geocode(tentativa)
            if loc:
                return loc.latitude, loc.longitude
        except:
            pass

    return None, None


def signo_from_grau(grau):
    signos = [
        "Áries", "Touro", "Gêmeos", "Câncer",
        "Leão", "Virgem", "Libra", "Escorpião",
        "Sagitário", "Capricórnio", "Aquário", "Peixes"
    ]
    index = int(grau // 30)
    return signos[index]


def calcular_aspectos(planetas_dict):
    """
    Calcula aspectos entre planetas usando orbes recomendados.
    """
    aspectos_principais = {
        "conjunção": 0,
        "oposição": 180,
        "trígono": 120,
        "quadratura": 90,
        "sextil": 60
    }

    orbes = {
        "conjunção": 8,
        "oposição": 8,
        "trígono": 8,
        "quadratura": 8,
        "sextil": 6
    }

    nomes = list(planetas_dict.keys())
    resultado = []

    for i in range(len(nomes)):
        for j in range(i + 1, len(nomes)):
            p1 = nomes[i]
            p2 = nomes[j]

            g1 = planetas_dict[p1]["grau"]
            g2 = planetas_dict[p2]["grau"]

            diff = abs(g1 - g2)
            diff = min(diff, 360 - diff)

            for asp, alvo in aspectos_principais.items():
                if abs(diff - alvo) <= orbes[asp]:
                    resultado.append({
                        "planeta1": p1,
                        "planeta2": p2,
                        "tipo": asp,
                        "orb": round(abs(diff - alvo), 2)
                    })

    return resultado


# ============================================================
# ENDPOINT PRINCIPAL
# ============================================================

@app.route("/mapa", methods=["POST"])
def mapa():
    try:
        data = request.json.get("data")
        hora = request.json.get("hora")
        cidade = request.json.get("cidade")

        if not data or not hora or not cidade:
            return jsonify({"erro": "Envie data, hora e cidade."}), 400

        # Converter data e hora
        try:
            dt = datetime.strptime(f"{data} {hora}", "%Y-%m-%d %H:%M")
        except ValueError:
            return jsonify({"erro": "Formato de data/hora inválido. Use YYYY-MM-DD e HH:MM"}), 400

        # Corrigir cidade
        lat, lon = corrigir_cidade(cidade)
        if lat is None:
            return jsonify({"erro": "Cidade não encontrada. Tente novamente."}), 400

        # JULIAN DAY
        jd = swe.julday(dt.year, dt.month, dt.day,
                        dt.hour + dt.minute / 60)

        # ============================================================
        # PLANETAS
        # ============================================================
        planetas_lista = {
            "Sol": swe.SUN,
            "Lua": swe.MOON,
            "Mercúrio": swe.MERCURY,
            "Vênus": swe.VENUS,
            "Marte": swe.MARS,
            "Júpiter": swe.JUPITER,
            "Saturno": swe.SATURN,
            "Urano": swe.URANUS,
            "Netuno": swe.NEPTUNE,
            "Plutão": swe.PLUTO
        }

        planetas = {}

        for nome, planeta in planetas_lista.items():
            pos, _ = swe.calc_ut(jd, planeta)
            grau = pos[0]
            signo = signo_from_grau(grau)
            casas = swe.houses(jd, lat, lon)[0]
            casa = sum(grau >= h for h in casas) or 12

            planetas[nome] = {
                "signo": signo,
                "grau": round(grau, 2),
                "casa": casa,
                "retrógrado": pos[3] < 0
            }

        # ============================================================
        # CASAS
        # ============================================================
        casas_raw, asc_mc = swe.houses(jd, lat, lon)
        asc, mc = asc_mc[0], asc_mc[1]

        casas = {}
        for i in range(12):
            grau = casas_raw[i]
            casas[str(i + 1)] = {
                "grau": round(grau, 2),
                "signo": signo_from_grau(grau)
            }

        # ============================================================
        # ASPECTOS
        # ============================================================
        aspectos = calcular_aspectos(planetas)

        # ============================================================
        # RETORNO FINAL
        # ============================================================
        return jsonify({
            "planetas": planetas,
            "casas": casas,
            "aspectos": aspectos
        })

    except Exception as e:
        return jsonify({"erro": f"Erro interno: {str(e)}"}), 500


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":
    app.run(debug=True)
