"""Convierte la salida de Claude (modo rapido) en top_plan_ID.json + filas para la web.
Uso: python3 agregar.py SALIDA.json VIDEO_ID PREFIJO [indices_a_quitar,...]
Numera los titulos en serie ("GTA 6 Secrets #N: ...") y asigna los siguientes huecos libres."""
import json, re, sys, datetime, pathlib
RAIZ = pathlib.Path(__file__).resolve().parent.parent
ESTADO = RAIZ / "planes_top" / "agenda.json"
HORAS = [("15:00", 0), ("18:00", 0), ("21:00", 0), ("00:00", 1), ("03:00", 1), ("06:00", 1)]  # 6 al dia (hora de Espana)

def huecos(desde_orden, n):
    d = datetime.date(int(str(desde_orden)[:4]), int(str(desde_orden)[4:6]), int(str(desde_orden)[6:8])) - datetime.timedelta(1)
    out = []
    while len(out) < n:
        for h, off in HORAS:
            dd = d + datetime.timedelta(off)
            o = int(dd.strftime("%Y%m%d")) * 10000 + int(h.replace(":", ""))
            if o > desde_orden:
                out.append((dd, h, o))
        d += datetime.timedelta(1)
    return sorted(out, key=lambda x: x[2])[:n]

salida, vid, pref = sys.argv[1], sys.argv[2], sys.argv[3]
quitar = {int(x) for x in sys.argv[4].split(",")} if len(sys.argv) > 4 and sys.argv[4] else set()
estado = json.loads(ESTADO.read_text()) if ESTADO.exists() else {"serie": 0, "ultimo_orden": 0}
items = [x for k, x in enumerate(json.load(open(salida, encoding="utf-8")), 1) if k not in quitar]
items.sort(key=lambda x: -x.get("puntuacion", 0))
clips = []
for x in items:
    estado["serie"] += 1
    x["titulo"] = f"GTA 6 Secrets #{estado['serie']}: {x.pop('hook_title')}"
    clips.append(x)
json.dump({"version": 2, "resumen": vid, "clips": clips},
          open(RAIZ / "planes_top" / f"top_plan_{vid}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
filas = []
for i, (c, (dd, h, o)) in enumerate(zip(clips, huecos(estado["ultimo_orden"], len(clips))), 1):
    slug = re.sub(r"[^a-z0-9]+", "-", c["titulo"].lower()).strip("-")[:40] or "clip"
    filas.append({"id": f"top-{pref}-{i:02d}", "canal": "en", "video": vid, "carpeta": f"C:\\clipper_top\\clips\\{vid}\\",
                  "archivo": f"{i:02d}_{slug}.mp4", "titulo": c["titulo"], "descripcion": c["descripcion"],
                  "comentario": c["comentario"], "puntuacion": c["puntuacion"], "programado": False,
                  "fecha": dd.isoformat(), "hora": h, "orden": o})
    estado["ultimo_orden"] = o
ESTADO.write_text(json.dumps(estado))
print(json.dumps(filas, ensure_ascii=False))
