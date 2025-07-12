from flask import Flask, render_template_string
import requests
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

app = Flask(__name__)

def calcular_hr(T, Td):
    T = float(T)
    Td = float(Td)
    return 100 * np.exp(
        (17.62 * Td) / (243.12 + Td) -
        (17.62 * T) / (243.12 + T)    )

def decodificar_temp(codigo):
    if pd.isna(codigo) or len(str(codigo)) != 5:
        return np.nan
    codigo = str(codigo)
    s = int(codigo[1])
    TTT = int(codigo[2:])
    temp = TTT / 10.0
    if s == 1:
        temp = -temp
    return temp

def obtener_synop():
    hoy = datetime.utcnow()
    inicio = hoy - timedelta(days=1)

    d1= inicio.day
    m1= inicio.month
    y1= inicio.year
    d2= hoy.day
    m2= hoy.month
    y2= hoy.year

    horaUTC = hoy.hour
    if hoy.minute <= 10:
        horaUTC -= 1

    url = (f"https://www.ogimet.com/display_synopsc2.php?estado=Arg&tipo=ALL&ord=REV&nil=SI&fmt=txt"
           f"&ano={y1}&mes={m1}&day={d1}&hora={horaUTC}&anof={y2}&mesf={m2}&dayf={d2}&horaf={horaUTC}&enviar=Ver")

    response = requests.get(url)
    response.raise_for_status()
    text = response.text

    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "87344" in line:
            start_idx = i + 2
            break
    else:
        return []

    synops = []
    current_synop = []
    for line in lines[start_idx:]:
        line = line.strip()
        if not line or line.startswith("#"):
            break
        current_synop.append(line)
        if line.endswith("=") or line.endswith("=="):
            synops.append(" ".join(current_synop))
            current_synop = []
            if len(synops) >= 10:
                break
    if not synops:
        return []

    synops.reverse()

    df_synop = pd.DataFrame(
        columns=["FechaHora", "Codigo Estación", "Visibilidad", "Viento", "Temperatura", "Td", "Resto"]
    )

    salida = []

    for synop in synops:
        tokens = synop.split()
        tokens = tokens[2:]

        fecha_hora = tokens[0]
        codigo_estacion = tokens[1]
        visibilidad = tokens[2]
        viento = tokens[3]
        temperatura = tokens[4]
        td = tokens[5]
        resto = " ".join(tokens[6:])

        df_synop.loc[len(df_synop)] = [
            fecha_hora,
            codigo_estacion,
            visibilidad,
            viento,
            temperatura,
            td,
            resto,
        ]

        synop_clean = " ".join(tokens)
        salida.append(synop_clean)

    df_synop["T_C"] = df_synop["Temperatura"].apply(decodificar_temp)
    df_synop["Td_C"] = df_synop["Td"].apply(decodificar_temp)
    df_synop["HR"] = df_synop.apply(lambda row: calcular_hr(row["T_C"], row["Td_C"]), axis=1)

    hr_list = [int(round(hr)) for hr in df_synop["HR"]]

    return salida, hr_list

@app.route("/")
def index():
    synops, hr_list = obtener_synop()

    html = "<h2>Últimos 10 SYNOP para estación 87344</h2><ul>"
    for idx, (synop, hr) in enumerate(zip(synops, hr_list), 1):
        html += f"<li>{synop} | HR={hr}%</li>"
    html += "</ul>"

    return render_template_string(html)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)