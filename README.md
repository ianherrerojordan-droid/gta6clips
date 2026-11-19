# GTA 6 Clipper

Pegas un link de YouTube y te devuelve clips verticales (9:16) listos para TikTok, Shorts y Reels:

- **Narración en español con contexto**: Gemini primero resume de qué va el vídeo entero y, para cada clip, ve la imagen y el audio y escribe una narración que empieza poniéndote en situación ("Este tío lleva 10 minutos buscando pelea en Vice City...") y luego cuenta lo que pasa (golpes, reacciones, mecánicas nuevas), traduciendo lo importante del inglés.
- **Voz en español gratis** (edge-tts). El audio original queda de fondo, más bajo.
- **Cartel de gancho arriba** (texto negro sobre amarillo, tipo "SE VAN A PEGAR").
- **Subtítulos grandes y claros**: 3 palabras a la vez, la que suena en amarillo.
- **`resumen.md`** con título, descripción, hashtags, minuto original y crédito al creador.

Todo es gratis: yt-dlp, Whisper, ffmpeg y edge-tts son libres, y Gemini tiene plan gratuito.

## Instalación en Windows (una sola vez)

1. Instala **Python 3.13** desde python.org (marca "Add python.exe to PATH").
2. Instala **ffmpeg**: abre CMD y ejecuta:
   ```
   winget install Gyan.FFmpeg
   ```
   Cierra el CMD y abre uno nuevo después.
3. Descarga este repo (botón verde **Code → Download ZIP**) y descomprímelo en `C:\clipper`.
4. Instala las librerías:
   ```
   cd C:\clipper
   py -3.13 -m pip install -r requirements.txt
   ```
5. Saca una clave gratis en **aistudio.google.com** → "Get API key", y guárdala (cambia `TU_CLAVE`):
   ```
   setx GEMINI_API_KEY TU_CLAVE
   ```
   Cierra el CMD y abre uno nuevo.

## Uso

Doble clic en **`clipear.bat`**, pega el link y pulsa Enter. Si el vídeo es largo, en la segunda pregunta pon el tramo que te interesa, por ejemplo `--desde 2:14 --hasta 20:00` (va mucho más rápido y gasta menos Gemini).

O desde CMD:
```
cd C:\clipper
py -3.13 clip.py https://www.youtube.com/watch?v=XXXX
py -3.13 clip.py https://www.youtube.com/watch?v=XXXX --desde 2:14 --hasta 20:00
```

Los clips salen en `C:\clipper\clips\ID_DEL_VIDEO\`. Si lo relanzas con el mismo vídeo, no vuelve a descargar ni a transcribir: solo elige otros momentos y rehace los clips (borra antes los MP4 viejos).

## Ajustes (con `setx NOMBRE valor` y abrir un CMD nuevo)

| Variable | Por defecto | Para qué |
|---|---|---|
| `N_CLIPS` | 5 | Clips por vídeo (baja a 3 si Gemini te da límite) |
| `VOZ` | es-ES-AlvaroNeural | Otra voz: `es-MX-JorgeNeural`, `es-ES-ElviraNeural`... |
| `VELOCIDAD` | 8 | % extra de velocidad de la voz |
| `VOL_ORIGINAL` | 0.15 | Volumen del audio original bajo la narración |
| `FUENTE` | Arial Black | Fuente de los subtítulos (`Impact`, `Arial`...) |
| `TITULO` | 1 | `0` quita el cartel de arriba |
| `NARRAR` | 1 | `0` = sin narración, subtítulos del audio original |
| `WHISPER` | small | `medium` / `large-v3` transcriben mejor (lento sin GPU) |
| `COOKIES_BROWSER` | (vacío) | `chrome`/`edge`/`firefox` si YouTube pide iniciar sesión |

## Problemas típicos

- **"Sign in to confirm you're not a bot"**: `setx COOKIES_BROWSER chrome` (con Chrome cerrado).
- **Límite de Gemini (429)**: espera unos minutos o baja `N_CLIPS`.
- **"clip X sin narracion"**: falló Gemini o la voz para ese clip; sale con subtítulos del audio original.
- Revisa cada clip antes de subirlo: Gemini puede equivocarse describiendo lo que ve.

## Importante

La narración y la traducción aportan valor propio, pero **no sustituyen el permiso del creador**. Clipea a creadores que lo permitan o en campañas de clipping, y deja el crédito que viene en `resumen.md`.
