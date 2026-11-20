"""Clipper GTA 6: link de YouTube -> clips verticales narrados en espanol con contexto.

Uso:  py -3.13 clip.py LINK [LINK2 ...]
      py -3.13 clip.py LINK --desde 2:14 --hasta 20:00   (solo ese tramo)
"""
try:  # usar los certificados de Windows (antivirus/proxy que intercepta HTTPS)
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import os, re, sys, json, time, base64, asyncio, subprocess
from pathlib import Path

import requests

YTDLP = [sys.executable, "-m", "yt_dlp"]
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
N_CLIPS = int(os.environ.get("N_CLIPS", "5"))
WHISPER = os.environ.get("WHISPER", "small")
COOKIES = os.environ.get("COOKIES_BROWSER", "")        # ej: chrome, edge, firefox
OUT = Path(os.environ.get("OUT_DIR", "clips"))
NARRAR = os.environ.get("NARRAR", "1") == "1"          # 0 = sin narracion
IDIOMA = os.environ.get("IDIOMA", "es")                # es = canal en espanol; en = canal en ingles
SUB = "en/" if IDIOMA == "en" else ""                  # los clips en ingles van a la subcarpeta en\\
VOZ = os.environ.get("VOZ", "en-US-AndrewNeural" if IDIOMA == "en" else "es-ES-AlvaroNeural")
VELOCIDAD = int(os.environ.get("VELOCIDAD", "8"))      # % extra de velocidad de la voz (ritmo TikTok)
VOL_ORIGINAL = os.environ.get("VOL_ORIGINAL", "0.6")   # volumen del audio original (baja solo cuando habla el narrador)
FUENTE = os.environ.get("FUENTE", "Impact")            # fuente de subtitulos (Impact, Arial Black...)
TITULO = os.environ.get("TITULO", "1") == "1"          # cartel con el gancho arriba los primeros segundos
FORMATO = os.environ.get("FORMATO", "lleno")           # lleno = gameplay a pantalla completa; barras = con fondo difuminado
LOGO = os.environ.get("LOGO", "")                    # ruta a un PNG tuyo (marca de agua arriba)
TAG = os.environ.get("TAG", "")                       # prefijo de planes/zips (top_ en clipper_top)
MODO = os.environ.get("MODO", "claude")              # claude = me pasas el ZIP en el chat; gemini = automatico
CTA = os.environ.get("CTA", "Follow for a daily GTA 6 fact" if IDIOMA == "en" else "Sigueme, cada dia un dato de GTA 6")  # frase final (vacio = sin)


# ---------------------------------------------------------------- utilidades
def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout)[-600:])
    return r.stdout.strip()


def duracion(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "default=nw=1:nk=1", str(path)]))


def a_seg(t):
    """'2:14' / '1:02:03' / '134' -> segundos."""
    s = 0.0
    for p in str(t).split(":"):
        s = s * 60 + float(p)
    return s


def minuto(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def json_de(txt, patron):
    m = re.search(patron, txt, re.S)
    if not m:
        raise RuntimeError(f"Gemini no devolvio JSON valido: {txt[:200]}")
    return json.loads(m.group(0))


# ---------------------------------------------------------------- descarga
def info_video(url):
    out = run([*YTDLP, "--no-playlist", "--skip-download", "--print", "%(id)s",
               "--print", "%(title)s", "--print", "%(channel)s", url]).splitlines()
    return {"id": out[0], "titulo": out[1] if len(out) > 1 else "",
            "canal": out[2] if len(out) > 2 else ""}


def descargar(url, wd):
    src = Path(wd) / "src.mp4"
    if src.exists():
        return src
    cook = ["--cookies-from-browser", COOKIES] if COOKIES else []
    run([*YTDLP, *cook, "-f", "bv*[height<=1080]+ba/b", "--merge-output-format", "mp4",
         "--no-playlist", "-o", "src.mp4", url], cwd=wd)
    return src


def transcribir(path):
    from faster_whisper import WhisperModel
    model = WhisperModel(WHISPER, device=os.environ.get("WHISPER_DEVICE", "cpu"), compute_type="int8")
    segs, _ = model.transcribe(str(path), word_timestamps=True, vad_filter=True)
    segmentos, palabras = [], []
    for s in segs:
        segmentos.append({"start": round(s.start, 1), "end": round(s.end, 1), "text": s.text.strip()})
        for w in s.words or []:
            palabras.append((w.start, w.end, w.word.strip()))
    return segmentos, palabras


# ---------------------------------------------------------------- Gemini
MODELOS_RESERVA = [m for m in os.environ.get(
    "GEMINI_RESERVA", "gemini-flash-lite-latest,gemini-2.5-flash,gemini-2.5-flash-lite").split(",") if m]
_agotados = set()


def gemini(parts):
    """Llama a Gemini; si un modelo agota su cupo diario gratis, pasa al siguiente."""
    if not GEMINI_KEY:
        raise RuntimeError("Falta GEMINI_API_KEY (mira el README).")
    for modelo in [GEMINI_MODEL, *MODELOS_RESERVA]:
        if modelo in _agotados:
            continue
        try:
            return _gemini(parts, modelo)
        except CupoDiario:
            _agotados.add(modelo)
            print(f"   {modelo}: cupo diario gratis agotado, pruebo con otro modelo...")
    raise RuntimeError("Todos los modelos gratis de Gemini han agotado el cupo de hoy. "
                       "Se renueva cada dia (sobre las 9:00 en Espana) o usa otra clave.")


class CupoDiario(Exception):
    pass


def _gemini(parts, modelo):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    body = {"contents": [{"parts": parts}], "generationConfig": {"responseMimeType": "application/json"}}
    for intento in range(4):
        try:
            r = requests.post(url, headers={"x-goog-api-key": GEMINI_KEY}, json=body, timeout=600)
        except requests.exceptions.RequestException:
            print("   Gemini no contesta, reintentando...")
            time.sleep(5)
            continue
        if r.status_code == 429:
            txt = r.text
            if "PerDay" in txt or "per day" in txt.lower():
                raise CupoDiario()
            m = re.search(r'"retryDelay":\s*"(\d+)', txt)
            espera = int(m.group(1)) + 2 if m else 20 * (intento + 1)
            print(f"   Limite por minuto de Gemini ({modelo}), espero {espera}s...")
            time.sleep(espera)
            continue
        if r.status_code == 404:
            raise CupoDiario()  # modelo no disponible para esta clave: probar el siguiente
        if r.status_code >= 500:
            print(f"   Gemini saturado ({r.status_code}), reintento...")
            time.sleep(10 * (intento + 1))
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"Gemini {r.status_code}: {r.text[:300]}")
        try:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise RuntimeError(f"Gemini bloqueo la respuesta: {r.text[:300]}")
    raise CupoDiario()


def elegir_clips(segmentos, info, dur_video):
    texto = "\n".join(f"[{s['start']}-{s['end']}] {s['text']}" for s in segmentos)
    prompt = (
        "Eres editor de un canal de clips virales de GTA 6 y videojuegos en espanol para TikTok y "
        "YouTube Shorts. El video original puede estar en ingles.\n"
        f"Video: \"{info.get('titulo', '')}\" del canal \"{info.get('canal', '')}\".\n"
        "1) Resume en 2-3 frases de que va el video entero (quien habla, que esta pasando).\n"
        f"2) Elige los {N_CLIPS} mejores momentos de 20 a 45 segundos (maximo 60): novedades, "
        "revelaciones, peleas, persecuciones, glitches, reacciones exageradas, momentos graciosos o "
        "impactantes. Cada clip debe tener un remate natural, empezar y terminar en limites de frase "
        "y no solaparse con otros.\n"
        "Devuelve SOLO este JSON:\n"
        '{"resumen": "...", "clips": [{"start": seg, "end": seg, '
        '"gancho": "texto para el cartel de arriba, MAYUSCULAS, max 6 palabras, que de ganas de verlo", '
        '"contexto": "1-2 frases: que ha pasado antes y que hay que saber para entender el clip", '
        '"titulo": "titulo en espanol, max 60 caracteres", "descripcion": "en espanol", '
        '"hashtags": ["5-8 hashtags"], "puntuacion": 1-10, "motivo": "una linea"}]}\n\n'
        "TRANSCRIPT:\n" + texto[:300000]
    )
    d = json_de(gemini([{"text": prompt}]), r"\{.*\}")
    clips = []
    for c in sorted(d.get("clips", []), key=lambda c: -float(c.get("puntuacion", 0))):
        try:
            a, b = max(float(c["start"]), 0), min(float(c["end"]), dur_video)
        except (KeyError, TypeError, ValueError):
            continue
        if not 10 <= b - a <= 90:
            continue
        if any(a < x["end"] and b > x["start"] for x in clips):  # solapado
            continue
        c["start"], c["end"] = a, b
        c.setdefault("titulo", f"Clip {len(clips) + 1}")
        clips.append(c)
        if len(clips) == N_CLIPS:
            break
    return d.get("resumen", ""), clips


def narracion(wd, i, clip, segmentos, resumen, info):
    """Gemini ve el clip (imagen + audio) y escribe la narracion en espanol con contexto."""
    dur = clip["end"] - clip["start"]
    max_pal = int(dur * 2.6)
    prev = f"prev_{i}.mp4"
    run(["ffmpeg", "-y", "-ss", str(clip["start"]), "-t", str(dur), "-i", "src.mp4",
         "-vf", "scale=-2:360", "-c:v", "libx264", "-crf", "30", "-preset", "veryfast",
         "-c:a", "aac", "-b:a", "64k", prev], cwd=wd)
    data = base64.b64encode((Path(wd) / prev).read_bytes()).decode()
    (Path(wd) / prev).unlink(missing_ok=True)
    trozo = " ".join(s["text"] for s in segmentos
                     if s["start"] >= clip["start"] - 1 and s["end"] <= clip["end"] + 1)
    prompt = (
        "Eres el narrador de un canal de TikTok/Shorts de GTA 6 en espanol, con estilo de comentarista: "
        "energico, cercano y con gracia (tipo 'y atentos, porque aqui le mete un TOTAZO...').\n"
        f"Video original: \"{info.get('titulo', '')}\" ({info.get('canal', '')}).\n"
        f"De que va el video entero: {resumen}\n"
        f"Contexto de este clip: {clip.get('contexto', '')}\n"
        f"Gancho del clip: {clip.get('gancho', clip.get('titulo', ''))}\n"
        f"Lo que se dice (puede estar en ingles): {trozo[:1500]}\n\n"
        "Mira el clip y escribe la narracion en espanol que se locutara encima:\n"
        "1) EMPIEZA con una frase de introduccion que ponga en contexto a alguien que no ha visto nada "
        "(quien es, donde estamos, que esta a punto de pasar) y que enganche en los primeros 3 segundos.\n"
        "2) Narra lo que ocurre al ritmo de la imagen: golpes, reacciones, jugadas, mecanicas nuevas. "
        "Si alguien dice algo importante en ingles, cuentalo traducido en tus palabras.\n"
        "3) Cierra con un remate corto (opinion, pregunta al espectador o dato).\n"
        "Marca entre asteriscos las 1-2 palabras clave de cada frase (numeros, nombres, la palabra "
        "que impacta), ejemplo: 'Vuelven las *6 estrellas*, antes el maximo era *5*'.\n"
        "No inventes nada que no se vea ni se oiga. Frases cortas. Sin emojis ni hashtags.\n"
        f"El clip dura {dur:.0f} segundos: usa como MAXIMO {max_pal} palabras.\n"
        "Ademas, elige 2-4 CARTELES: textos cortos (max 3 palabras, MAYUSCULAS) con el dato clave "
        "que aparecen en pantalla cuando el narrador dice una palabra concreta de la narracion "
        "(ej: palabra 'pistolas' -> cartel '2 PISTOLAS').\n"
        'Responde SOLO con JSON: {"narracion": "...", '
        '"carteles": [{"palabra": "palabra exacta de la narracion", "texto": "CARTEL"}]}'
    )
    out = gemini([{"inline_data": {"mime_type": "video/mp4", "data": data}}, {"text": prompt}])
    d = json_de(out, r"\{.*\}")
    return d["narracion"].strip(), d.get("carteles") or []


# ---------------------------------------------------------------- voz
def voz(texto, mp3, rate):
    """Llama a la voz de Microsoft con reintentos (el servicio gratis a veces no responde)."""
    for intento in range(5):
        try:
            pal = asyncio.run(_tts(texto, mp3, rate))
            if Path(mp3).exists() and Path(mp3).stat().st_size > 1000:
                return pal
            raise RuntimeError("audio vacio")
        except Exception as e:
            if intento == 4:
                raise RuntimeError(f"la voz no responde ({str(e)[:80]})")
            time.sleep(4 * (intento + 1))


async def _tts(texto, mp3, rate):
    import edge_tts
    kw = {"rate": f"{rate:+d}%"}
    try:
        com = edge_tts.Communicate(texto, VOZ, boundary="WordBoundary", **kw)
    except TypeError:
        com = edge_tts.Communicate(texto, VOZ, **kw)
    pal = []
    with open(mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                pal.append((ch["offset"] / 1e7, (ch["offset"] + ch["duration"]) / 1e7, ch["text"]))
    return pal


def claves(texto):
    """Palabras marcadas con *asteriscos* por Gemini -> se pintan en amarillo."""
    return {norm(w) for frag in re.findall(r"\*([^*]+)\*", texto) for w in frag.split()}


def norm(w):
    return re.sub(r"[^\w]", "", w.lower())


def locutar(texto, mp3, dur_clip):
    """Genera la voz; si se pasa del clip, la acelera (hasta +35%) para que encaje."""
    texto = texto.replace("*", "")
    rate = VELOCIDAD
    pal = voz(texto, mp3, rate)
    nd = duracion(mp3)
    if nd > dur_clip + 0.5:
        rate = min(35, int((nd / dur_clip - 1) * 100) + rate + 3)
        pal = voz(texto, mp3, rate)
        nd = duracion(mp3)
    if not pal:
        pal = repartir(texto, nd)
    return pal, nd


def pista_narracion(wd, i, lineas, dur_clip):
    """Locuta cada frase en su segundo exacto. lineas = [{"t": seg_desde_inicio_clip, "texto": ...}].
    Devuelve (wav, palabras con tiempos absolutos, fin de la ultima frase)."""
    lineas = sorted([l for l in lineas if str(l.get("texto", "")).strip()], key=lambda l: float(l["t"]))
    if CTA:
        lineas.append({"t": None, "texto": CTA + "."})
    palabras, trozos, fin_prev = [], [], 0.0
    for k, l in enumerate(lineas):
        t = fin_prev + 0.25 if l["t"] is None else max(float(l["t"]), fin_prev + 0.1 if k else 0.0)
        sig = next((float(x["t"]) for x in lineas[k + 1:] if x["t"] is not None), None)
        hueco = (sig - t - 0.1) if sig is not None else max(dur_clip - t, 3.0) + 1.5
        texto = str(l["texto"]).replace("*", "")
        mp3 = str((Path(wd) / f"l{i}_{k}.mp3").resolve())
        rate = VELOCIDAD
        pal = voz(texto, mp3, rate)
        nd = duracion(mp3)
        if nd > hueco and hueco > 0.5:          # no cabe: acelerar (hasta +45%)
            rate = min(45, rate + int((nd / hueco - 1) * 100) + 4)
            pal = voz(texto, mp3, rate)
            nd = duracion(mp3)
        if not pal:
            pal = repartir(texto, nd)
        palabras += [(a + t, b + t, w) for a, b, w in pal]
        trozos.append((mp3, t))
        fin_prev = t + nd
    wav = f"n{i}.wav"
    ins, filt = [], []
    for k, (mp3, t) in enumerate(trozos):
        ins += ["-i", mp3]
        ms = int(t * 1000)
        filt.append(f"[{k}:a]aresample=48000,adelay={ms}|{ms}[a{k}]")
    filt.append("".join(f"[a{k}]" for k in range(len(trozos)))
                + f"amix=inputs={len(trozos)}:normalize=0:duration=longest[o]")
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(filt), "-map", "[o]", "-ac", "2", wav], cwd=wd)
    for mp3, _ in trozos:
        Path(mp3).unlink(missing_ok=True)
    return wav, palabras, fin_prev


def repartir(texto, dur):
    ws = texto.split()
    paso = dur / max(len(ws), 1)
    return [(k * paso, (k + 1) * paso, w) for k, w in enumerate(ws)]


# ---------------------------------------------------------------- subtitulos
def t_ass(t):
    t = max(t, 0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def cabecera():
    return ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n\n"
            "[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,"
            "BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,"
            "Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
            # subtitulos: letra gruesa en el centro, borde negro y sombra
            f"Style: Default,{FUENTE},128,&H00FFFFFF,&H00FFFFFF,&H00000000,&HA0000000,0,0,0,0,"
            "100,100,1,0,1,7,5,5,70,70,0,1\n"
            # cartel de arriba: texto negro sobre caja amarilla
            f"Style: Titulo,{FUENTE},74,&H00000000,&H00000000,&H0000D5FF,&H00000000,1,0,0,0,"
            "100,100,0,0,3,22,0,8,70,70,230,1\n"
            # carteles de dato: texto blanco sobre caja roja
            f"Style: Cartel,{FUENTE},84,&H00FFFFFF,&H00FFFFFF,&H003C14E6,&H00000000,1,0,0,0,"
            "100,100,0,0,3,18,0,8,70,70,330,1\n\n"
            "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")


def limpia(w):
    return w.upper().replace("*", "").replace("{", "").replace("}", "").replace("\\", "")


def lineas_subs(pal, clave=frozenset()):
    """2 palabras a la vez en el centro, con 'pop' al entrar; las palabras clave en amarillo."""
    lineas = []
    for g0 in range(0, len(pal), 2):
        g = pal[g0:g0 + 2]
        fin = pal[g0 + 2][0] if g0 + 2 < len(pal) else g[-1][1] + 0.4
        txt = " ".join((r"{\c&H00D5FF&}" + limpia(w) + r"{\c&HFFFFFF&}") if norm(w) in clave
                       else limpia(w) for _, _, w in g)
        pop = r"{\fscx80\fscy80\t(0,90,\fscx100\fscy100)}"
        lineas.append(f"Dialogue: 0,{t_ass(g[0][0])},{t_ass(fin)},Default,,0,0,0,,{pop}{txt}")
    return lineas


def crear_ass(pal, total, gancho, out, clave=frozenset(), carteles=()):
    lineas = []
    usados = set()
    for ct in carteles:
        if ct.get("t") is not None:
            a = float(ct["t"])
            lineas.append(f"Dialogue: 1,{t_ass(a)},{t_ass(min(a + 2.5, total))},Cartel,,0,0,0,,"
                          + r"{\fscx70\fscy70\t(0,120,\fscx100\fscy100)}" + limpia(str(ct.get("texto", ""))))
            continue
        objetivo = norm(str(ct.get("palabra", "")).split()[0]) if ct.get("palabra") else ""
        for k, (a, _, w) in enumerate(pal):
            if k not in usados and objetivo and norm(w) == objetivo and a > 3.5:
                usados.add(k)
                lineas.append(f"Dialogue: 1,{t_ass(a)},{t_ass(min(a + 2.5, total))},Cartel,,0,0,0,,"
                              + r"{\fscx70\fscy70\t(0,120,\fscx100\fscy100)}" + limpia(str(ct.get("texto", ""))))
                break
    if TITULO and gancho:
        lineas.append(f"Dialogue: 1,{t_ass(0)},{t_ass(min(3.5, total))},Titulo,,0,0,0,,"
                      + r"{\fad(150,250)}" + limpia(gancho))
    lineas += lineas_subs(pal, clave)
    Path(out).write_text(cabecera() + "\n".join(lineas) + "\n", encoding="utf-8")


def palabras_orig(palabras, ini, fin):
    return [(max(a - ini, 0), min(b, fin) - ini, w) for a, b, w in palabras if a >= ini and b <= fin + 0.3]


# ---------------------------------------------------------------- render
def nombre_salida(i, clip):
    slug = re.sub(r"[^a-z0-9]+", "-", clip["titulo"].lower()).strip("-")[:40] or "clip"
    return f"{SUB}{i:02d}_{slug}.mp4"


def render(wd, i, clip, total, mp3):
    out = nombre_salida(i, clip)
    (Path(wd) / SUB).mkdir(exist_ok=True)
    if FORMATO == "lleno":
        video = ("[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                 f"eq=brightness=-0.10:saturation=1.1,ass=s{i}.ass,format=yuv420p[v]")
    else:
        video = ("[0:v]split[a][b];"
                 "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25,"
                 "eq=brightness=-0.08[bg];"
                 "[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,"
                 f"ass=s{i}.ass,format=yuv420p[v]")
    fuente, ss = "src.mp4", clip["start"]
    if clip.get("tramos"):  # estilo top: varias escenas cortas montadas seguidas
        fuente, ss = f"tr{i}.mp4", 0
        partes, k = [], 0
        for t in clip["tramos"]:
            a, b = float(t["start"]), float(t["end"])
            partes.append(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS,fps=30,scale=1920:1080:force_original_aspect_ratio=decrease,"
                          f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1[v{k}];[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS,aresample=48000[a{k}]")
            k += 1
        cadena = ";".join(partes) + ";" + "".join(f"[v{j}][a{j}]" for j in range(k)) + f"concat=n={k}:v=1:a=1[v][a]"
        run(["ffmpeg", "-y", "-i", "src.mp4", "-filter_complex", cadena, "-map", "[v]", "-map", "[a]",
             "-c:v", "libx264", "-crf", "17", "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k", fuente], cwd=wd)
        video = video.replace("[0:v]", "[0:v]tpad=stop_mode=clone:stop_duration=8,", 1)
    entradas = []
    if LOGO and Path(LOGO).exists():
        entradas = ["-i", str(Path(LOGO).resolve())]
        video = video.replace("[v]", "[pre]") + ";[1:v]scale=360:-1[lg];[pre][lg]overlay=(W-w)/2:90[v]"
    na = len(entradas) // 2 + 1  # indice de la entrada de la narracion
    if mp3:
        # el audio original baja mientras habla el narrador y se mezcla de fondo
        # el audio original se oye normal y baja solo mientras habla el narrador
        audio = (f"[0:a]volume={VOL_ORIGINAL}[o];[{na}:a]volume=1.6,apad,asplit[n1][n2];"
                 "[o][n1]sidechaincompress=threshold=0.015:ratio=12:attack=15:release=350[d];"
                 "[d][n2]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5[a]")
        entradas += ["-i", mp3]
    else:
        audio = "[0:a]loudnorm=I=-14:TP=-1.5[a]"
    run(["ffmpeg", "-y", "-ss", str(ss), "-t", f"{total:.2f}", "-i", fuente, *entradas,
         "-filter_complex", video + ";" + audio, "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}",
         "-c:v", "libx264", "-crf", "21", "-preset", "veryfast", "-r", "30",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out], cwd=wd)
    for f in (f"s{i}.ass", mp3, f"tr{i}.mp4" if clip.get("tramos") else None):
        if f:
            (Path(wd) / f).unlink(missing_ok=True)
    return out


# ---------------------------------------------------------------- modo Claude
def preparar_paquete(wd, info, url, segmentos, dur_video, desde, hasta):
    """Crea para_claude/ID.zip con transcript + hojas de fotogramas para pasarselo a Claude."""
    import zipfile
    a, b = desde or 0, hasta or dur_video
    paso = max(4, int((b - a) / 240) + 1)              # como mucho ~240 fotogramas
    tmp = wd / "hojas"
    tmp.mkdir(exist_ok=True)
    for f in tmp.glob("*"):
        f.unlink()
    run(["ffmpeg", "-y", "-ss", str(a), "-t", str(b - a), "-i", "src.mp4",
         "-vf", f"fps=1/{paso},scale=320:180:force_original_aspect_ratio=decrease,"
                "pad=320:180:(ow-iw)/2:(oh-ih)/2,tile=4x4",
         "-q:v", "4", "hojas/hoja_%02d.jpg"], cwd=wd)
    hojas = sorted(tmp.glob("hoja_*.jpg"))
    indice = [f"Cada hoja tiene 16 fotogramas (4x4, de izquierda a derecha y de arriba abajo), "
              f"uno cada {paso} s, empezando en el segundo {a:.0f}."]
    for k, h in enumerate(hojas):
        t0 = a + k * 16 * paso
        t1 = min(t0 + 15 * paso, b)
        indice.append(f"{h.name}: del segundo {t0:.0f} ({minuto(t0)}) al {t1:.0f} ({minuto(t1)})")
    texto = "\n".join(f"[{s['start']}-{s['end']}] {s['text']}" for s in segmentos) or "(nadie habla)"
    leeme = (f"VIDEO: {info['titulo']}\nCANAL: {info['canal']}\nLINK: {url}\nID: {info['id']}\n"
             f"DURACION: {dur_video:.0f} s\nTRAMO: {a:.0f}-{b:.0f} s\nCLIPS PEDIDOS: {N_CLIPS}\n\n"
             + "\n".join(indice) + "\n\nTRANSCRIPCION (segundos):\n" + texto)
    destino = Path("para_claude")
    destino.mkdir(exist_ok=True)
    zp = destino / f"{TAG}{info['id']}.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("LEEME.txt", leeme)
        for h in hojas:
            z.write(h, h.name)
    if os.name == "nt":
        subprocess.run(["explorer", "/select,", str(zp.resolve())])
    print(f"\n>>> PASO 1 de 2. Arrastra este archivo al chat de Claude: {zp.resolve()}")
    print(f">>> Claude te devolvera {TAG}cortes_{info['id']}.json. Guardalo en Descargas")
    print(">>> y vuelve a pegar este mismo link aqui.\n")


def preparar_detalle(wd, info, url, segmentos, cortes):
    """PASO 2: un fotograma por segundo de cada clip elegido, para cuadrar la narracion al segundo."""
    import zipfile
    tmp = wd / "detalle"
    tmp.mkdir(exist_ok=True)
    for f in tmp.glob("*"):
        f.unlink()
    leeme = [f"VIDEO: {info['titulo']}\nCANAL: {info['canal']}\nLINK: {url}\nID: {info['id']}\n",
             "Cada hoja: 30 fotogramas (6 columnas x 5 filas, izquierda a derecha, arriba abajo), "
             "UNO POR SEGUNDO. El primer fotograma de la hoja N de un clip es el segundo 30*(N-1) del clip.\n"]
    for i, c in enumerate(cortes, 1):
        trozos = c.get("tramos") or [c]
        multi = len(trozos) > 1 or bool(c.get("tramos"))
        leeme.append(f"CLIP {i}: Idea: {c.get('idea', c.get('titulo', ''))}"
                     + (f" -- {len(trozos)} ESCENAS montadas seguidas" if multi else ""))
        for k, tr in enumerate(trozos, 1):
            a, b = float(tr["start"]), float(tr["end"])
            nombre = f"clip{i:02d}_escena{k}_hoja_%d.jpg" if multi else f"clip{i:02d}_hoja_%d.jpg"
            run(["ffmpeg", "-y", "-ss", str(a), "-t", str(b - a), "-i", "src.mp4",
                 "-vf", "fps=1,scale=256:144:force_original_aspect_ratio=decrease,"
                        "pad=256:144:(ow-iw)/2:(oh-ih)/2,tile=6x5",
                 "-q:v", "4", "detalle/" + nombre], cwd=wd)
            habla = "\n".join(f"  [{s['start'] - a:.1f}-{s['end'] - a:.1f}] {s['text']}" for s in segmentos
                              if s["end"] > a and s["start"] < b) or "  (nadie habla)"
            leeme.append((f"  ESCENA {k}: " if multi else "  ") + f"original {a:.0f}-{b:.0f} s ({b - a:.0f} s)\n"
                         f"  Lo que se dice (segundos desde el inicio de esta escena):\n{habla}\n")
    destino = Path("para_claude")
    destino.mkdir(exist_ok=True)
    zp = destino / f"{TAG}{info['id']}_detalle.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("LEEME.txt", "\n".join(leeme))
        for h in sorted(tmp.glob("*.jpg")):
            z.write(h, h.name)
    if os.name == "nt":
        subprocess.run(["explorer", "/select,", str(zp.resolve())])
    print(f"\n>>> PASO 2 de 2. Arrastra este archivo al chat de Claude: {zp.resolve()}")
    print(f">>> Claude te devolvera {TAG}plan_{info['id']}.json. Guardalo en Descargas")
    print(">>> y vuelve a pegar este mismo link aqui: se crearan los clips.\n")


def buscar_plan(wd, vid, tipo="plan"):
    cands = [wd / f"{tipo}.json", *Path.home().joinpath("Downloads").glob(f"{TAG}{tipo}_{vid}*.json"),
             *Path(".").glob(f"{TAG}{tipo}_{vid}*.json")]
    cands = [c for c in cands if c.exists()]
    if not cands:
        return None
    mejor = max(cands, key=lambda c: c.stat().st_mtime)
    plan = json.loads(mejor.read_text(encoding="utf-8"))
    if mejor != wd / f"{tipo}.json":
        (wd / f"{tipo}.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
        try:
            mejor.unlink()   # ya esta copiado; asi el siguiente plan no se confunde
        except OSError:
            pass
    return plan


# ---------------------------------------------------------------- flujo
def procesar(url, desde=None, hasta=None):
    info = info_video(url)
    wd = OUT / info["id"]
    wd.mkdir(parents=True, exist_ok=True)
    (wd / "info.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    print(f"[1/4] Descargando: {info['titulo'][:70]}")
    src = descargar(url, wd)
    dur_video = duracion(src)
    print(f"[2/4] Transcribiendo {minuto(dur_video)} min (lo lento, solo la primera vez)...")
    cache = wd / "transcript.json"
    if cache.exists():
        d = json.loads(cache.read_text(encoding="utf-8"))
        segmentos, palabras = d["segmentos"], d["palabras"]
        print("   (usando transcripcion guardada)")
    else:
        segmentos, palabras = transcribir(src)
        cache.write_text(json.dumps({"segmentos": segmentos, "palabras": palabras}), encoding="utf-8")
    if desde is not None or hasta is not None:
        a, b = desde or 0, hasta or dur_video
        segmentos = [s for s in segmentos if s["start"] >= a and s["end"] <= b]
        print(f"   (solo el tramo {minuto(a)} - {minuto(b)})")
    plan = buscar_plan(wd, info["id"])
    if plan and plan.get("version", 1) < 2:
        plan = None                       # plan antiguo (sin tiempos): no vale
    cortes = None if plan else buscar_plan(wd, info["id"], "cortes")
    if cortes and MODO != "gemini":
        print("[3/4] Preparando los fotogramas segundo a segundo de cada clip...")
        preparar_detalle(wd, info, url, segmentos, cortes.get("clips", []))
        return
    if plan:
        print("[3/4] Usando el plan de Claude...")
        resumen = plan.get("resumen", "")
        clips = [c for c in plan.get("clips", []) if c.get("tramos") or c.get("end", 0) > c.get("start", 0)]
        for c in clips:
            if c.get("tramos"):  # duracion = suma de las escenas
                c["start"] = float(c["tramos"][0]["start"])
                c["end"] = c["start"] + sum(float(t["end"]) - float(t["start"]) for t in c["tramos"])
            else:
                c["start"], c["end"] = float(c["start"]), min(float(c["end"]), dur_video)
            c.setdefault("titulo", "clip")
        if IDIOMA == "en":
            faltan = [k + 1 for k, c in enumerate(clips) if not c.get("en")]
            if faltan:
                raise RuntimeError(f"El plan no tiene version en ingles (clips {faltan}). Pidesela a Claude.")
            clips = [{**c, **c["en"]} for c in clips]
    elif MODO != "gemini":
        print("[3/4] Preparando la vista general para Claude...")
        preparar_paquete(wd, info, url, segmentos, dur_video, desde, hasta)
        return
    else:
        if not segmentos:
            raise RuntimeError("No hay voz en el video/tramo: nada que analizar.")
        print("[3/4] Eligiendo los mejores momentos con Gemini...")
        resumen, clips = elegir_clips(segmentos, info, dur_video)
    if not clips:
        raise RuntimeError("No hay clips validos en el plan.")
    print(f"   De que va: {resumen[:150]}")

    print(f"[4/4] Creando {len(clips)} clips" + ((" con narracion en " + ("ingles" if VOZ.startswith("en") else "espanol") + "...") if NARRAR else "..."))
    md = [f"# {info['titulo']}\n", f"- Link: {url}", f"- Canal: {info['canal']}",
          f"- De que va: {resumen}\n"]
    hechos, pendientes = 0, []
    for i, c in enumerate(clips, 1):
        dur = c["end"] - c["start"]
        if (Path(wd) / nombre_salida(i, c)).exists() and os.environ.get("REHACER") != "1":
            hechos += 1
            continue
        mp3, texto_nar, total, pal, clave, carteles = None, None, dur, None, frozenset(), []
        if NARRAR:
            try:
                if isinstance(c.get("narracion"), list):          # plan de Claude: frases con tiempo
                    lineas, carteles = c["narracion"], c.get("carteles") or []
                else:                                              # Gemini: un bloque desde el segundo 0
                    texto, carteles = narracion(wd, i, c, segmentos, resumen, info)
                    lineas = [{"t": 0, "texto": texto}]
                texto_nar = " ".join(str(l["texto"]) for l in lineas)
                clave = claves(texto_nar)
                mp3, pal, nd = pista_narracion(wd, i, lineas, dur)
                total = max(dur, nd + 0.6) if c.get("tramos") else min(max(dur, nd + 0.6), dur_video - c["start"])
            except Exception as e:
                print(f"   (clip {i} pendiente, {str(e)[:120]}. Vuelve a pegar el link luego)")
                pendientes.append(i)
                continue
        if not mp3:
            pal, total = palabras_orig(palabras, c["start"], c["end"]), dur
        crear_ass(pal, total, c.get("gancho", ""), Path(wd) / f"s{i}.ass", clave, carteles)
        f = render(wd, i, c, total, mp3)
        tags = " ".join("#" + str(h).lstrip("#") for h in c.get("hashtags", []))
        md.append(f"## {i}. {c['titulo']}  ({f})\n"
                  f"- Puntuacion: {c.get('puntuacion')}/10 - {c.get('motivo', '')}\n"
                  f"- Minuto original: {minuto(c['start'])} a {minuto(c['end'])}\n"
                  f"- Cartel: {c.get('gancho', '')}\n"
                  f"- Descripcion: {c.get('descripcion', '')} {tags}\n"
                  f"- Credito: video original de {info['canal']} ({url})\n"
                  + (f"- Narracion: {texto_nar.replace('*', '')}\n" if texto_nar else ""))
        print(f"   listo: {f}")
    if hechos:
        print(f"   ({hechos} clips ya estaban hechos, no se repiten)")
    if pendientes:
        print(f"\n!!! Faltan los clips {pendientes}: la voz no respondio. Espera 1 minuto y vuelve a pegar el link.")
    (wd / SUB / "resumen.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\nTerminado. Clips y resumen.md en: {(wd / SUB).resolve()}\n")


def main(argv):
    links, desde, hasta, k = [], None, None, 0
    while k < len(argv):
        if argv[k] == "--desde":
            desde, k = a_seg(argv[k + 1]), k + 2
        elif argv[k] == "--hasta":
            hasta, k = a_seg(argv[k + 1]), k + 2
        else:
            links.append(argv[k]); k += 1
    if not links:
        sys.exit("Uso: py -3.13 clip.py LINK [LINK2 ...] [--desde 2:14] [--hasta 20:00]")
    for u in links:
        try:
            procesar(u, desde, hasta)
        except Exception as e:
            print(f"ERROR con {u}: {e}\n")


if __name__ == "__main__":
    main(sys.argv[1:])
