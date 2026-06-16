# Documentos del centro (IES Jándula)

Coloca aquí los documentos **oficiales y curados** del centro para que el agente
los use como fuente preferente en las preguntas públicas (por delante de la web).

Se indexan en la colección `centro_info` y los consulta la tool
`consultar_info_centro`.

## Qué meter aquí
- Oferta educativa y ciclos formativos (FP Básica, Grado Medio, Grado Superior).
- Servicios: comedor, transporte, biblioteca, horarios generales.
- Trámites: secretaría, matrícula, admisión, becas, plazos.
- Cualquier información pública del centro que quieras que conteste con precisión.

## Formatos soportados
`.pdf`, `.txt`, `.md`

## Cómo activar la indexación
1. Sube los archivos a esta carpeta.
2. Pon `SEED_CENTRO=true` en las variables de entorno.
3. Redeploy. En los logs verás `🏫 [SEED:CENTRO] ...`.
4. Cuando termine, vuelve a poner `SEED_CENTRO=false`.

> ⚠️ Con embeddings de Gemini free-tier, indexar muchos PDFs grandes agota la
> cuota. Lo ideal es hacerlo con embeddings locales (Ollama). Para 1-3 documentos
> pequeños del centro no hay problema en hacerlo con Gemini.
