from flask import Flask, request, jsonify
import swisseph as swe
from datetime import datetime
import unicodedata

app = Flask(__name__)

# ==========================================
# CONFIGURAÇÃO
# ==========================================

swe.set_ephe_path('.')  # ajuste se usar arquivos ephemeris externos

# Base simples de cidades (adicione mais conforme necessário)
CIDADES = {
    "Florianopolis": (-27.5954, -48.5480),
    "Sao Paulo": (-23.5505, -46.6333),
    "Rio de Janeiro": (-22.9068, -43.1729),
    "Curitiba": (-25.4284, -49.2733),
    "Porto Alegre": (-30.0346, -51.2177),
    "Brasilia": (-15.7942, -47.8822)
}

# ==========================================
# UTILITÁRIOS
# ==========================================

def remover_acentos(txt):
    return ''.join(
        c for c in unicodedata.normalize('NFD', txt)
        if unicodedata.category(c) != 'Mn'
    )

def buscar_cidade(nome):
    nome = remover_acentos(nome).strip()
    return CIDADES.get(nome)

def signo_from_grau(grau):
    signos = [
        "Áries", "Touro", "Gêmeos", "Câncer",
        "Leão", "Virgem", "Libra", "Escorpião",
        "Sagitário", "Capricórnio", "Aquário", "Peixes"
    ]
    return signos[int(grau // 30)]

def calcular_aspectos(planetas):
    aspectos_base = {
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

    nomes = list(planetas.keys())
    resultado = []

    for i in range(len(nomes)):
        for j in range(i + 1, len(nomes)):
            p1 = nomes[i]
            p2 = nomes[j]

            g1 = planetas[p1]["grau"]
            g2 = planetas[p2]["grau"]

            diff = abs(g1 - g2)
            diff = min(diff, 360 - diff)

            for nome, grau_alvo in aspectos_base.items():
                if abs(diff - grau_alvo) <= orbes[nome]:
                    resultado.append({
                        "planeta1": p1,
                        "planeta2": p2,
                        "tipo": nome,
                        "orb": round(abs(diff - grau_alvo), 2)
                    })

    return resultado

# ==========================================
# ROTA PRINCIPAL
# ==========================================

@app.route("/mapa", methods=["POST"])
def mapa():

    try:
        dados = request.json

        data = dados.get("data")
        hora = dados.get("hora")
        latitude = dados.get("latitude")
        longitude = dados.get("longitude")
        cidade = dados.get("cidade")

        if not data or not hora:
            return jsonify({"erro": "Envie data e hora."}), 400

        # Conversão data/hora
        try:
            dt = datetime.strptime(f"{data} {hora}", "%Y-%m-%d %H:%M")
        except:
            return jsonify({"erro": "Formato inválido. Use YYYY-MM-DD e HH:MM"}), 400

        # Coordenadas
        if latitude and longitude:
            lat = float(latitude)
            lon = float(longitude)

        elif cidade:
            coords = buscar_cidade(cidade)
            if not coords:
                return jsonify({"erro": "Cidade não encontrada na base local."}), 400
            lat, lon = coords

        else:
            return jsonify({"erro": "Envie latitude/longitude ou cidade."}), 400

        # Julian Day
        jd = swe.julday(dt.year, dt.month, dt.day,
                        dt.hour + dt.minute / 60)

        # Casas
        casas_raw, asc_mc = swe.houses(jd, lat, lon)

        casas = {}
        for i in range(12):
            grau = casas_raw[i]
            casas[str(i + 1)] = {
                "grau": round(grau, 2),
                "signo": signo_from_grau(grau)
            }

        # Planetas
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

            planetas[nome] = {
                "grau": round(grau, 2),
                "signo": signo_from_grau(grau),
                "retrógrado": pos[3] < 0
            }

        aspectos = calcular_aspectos(planetas)

        return jsonify({
            "latitude": lat,
            "longitude": lon,
            "planetas": planetas,
            "casas": casas,
            "aspectos": aspectos
        })

    except Exception as e:
        return jsonify({"erro": str(e)}), 500


if __name__ == "__main__":
    app.run()
