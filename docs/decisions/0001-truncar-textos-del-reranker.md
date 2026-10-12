# ADR-0001: Truncar en Pinecone los textos que pasan el límite del reranker

* **Fecha**: 2026-10-06
* **Estado**: Aceptado, como solución provisoria (ver §5)
* **Autores**: Equipo Chiripa, con Claude Code

---

## 1. Contexto

En producción el re-ranking corre en Pinecone (`ApiRerankerService`) con el
modelo `bge-reranker-v2-m3`. Ese modelo acepta como máximo 1024 tokens por par
consulta + documento. El parámetro `truncate` de la API vale `NONE` por
omisión, y con ese valor Pinecone rechaza con 400 la petición entera si un solo
par se pasa. Nuestro código no mandaba `truncate`.

El documento de cada licitación lo arma `TextBuilder.build_from_tender`: nombre,
descripción y todos los ítems con su descripción. El largo lo ponen los ítems.
Medido el 2026-10-06 sobre las 737 licitaciones publicadas y vigentes:

- Mediana de 621 caracteres. 16 licitaciones superan los ~3200 caracteres.
- En esas 16, la descripción nunca pasa de 500 caracteres. Los ítems suman entre
  2700 y 9600, en licitaciones de 12 a 75 ítems.
- Con el tokenizador del modelo, el español da ~3,5 caracteres por token. Una
  licitación de 4236 caracteres produce 1214 tokens sola, sin contar la
  consulta.

`RankTendersUseCase` manda hasta 50 candidatas. Si una de esas 16 cae entre
ellas, el rerank falla, `GET /tenders/recommended` responde 500 y la empresa se
queda sin recomendaciones. Le pasó el 2026-09-21 a una empresa y el 2026-10-06 a
otra recién registrada, que no recibió ninguna recomendación. El resto de las
empresas no se vio afectado porque sus candidatas no incluían ninguna de esas
licitaciones o porque leían el ranking desde la caché.

El modo local (`BgeRerankerService`, ONNX) nunca tuvo este problema porque ya
tokeniza con `truncation=True, max_length=512`.

---

## 2. Decisión tomada

`ApiRerankerService` manda `"parameters": {"truncate": "END"}`. Pinecone recorta
el par al llegar a 1024 tokens en vez de rechazarlo. En la práctica se pierden
los últimos ítems de las licitaciones largas, porque el texto termina con ellos.

Además, cuando Pinecone responde con error, el servicio registra el cuerpo de la
respuesta y los ids de las candidatas en el orden en que se enviaron. Antes el
log solo decía "400 Bad Request" y no se podía saber qué licitación lo causó.

Se eligió porque es un cambio de una línea, se despliega hoy y deja producción
igual que el modo local, que ya recortaba. Producción recorta incluso más tarde:
a los 1024 tokens, frente a los 512 del modo local.

---

## 3. Alternativas consideradas

* **Dejar las licitaciones largas fuera del rerank.** Evita el 400, pero esas
  licitaciones desaparecerían de las recomendaciones justo cuando son las más
  detalladas. Descartada.
* **Recortar el texto en nuestro código, contando caracteres.** Funciona, pero
  la cuenta de caracteres por token cambia con el texto (siglas, medidas y
  números tokenizan peor), así que habría que dejar un margen amplio y recortar
  de más. Pinecone recorta con el tokenizador real. Queda como parte de la
  investigación de §5, junto con decidir qué recortar.
* **Partir la licitación en trozos y rerankear cada uno.** Multiplica las
  llamadas y obliga a combinar puntajes. Demasiado para un arreglo urgente.
  También queda para §5.

---

## 4. Consecuencias

### Positivas
- Ninguna licitación, por larga que sea, vuelve a tumbar las recomendaciones de
  una empresa.
- Producción y local se comportan igual frente a textos largos.
- Si Pinecone vuelve a rechazar una petición, el log dice por qué y con qué
  licitación.

### Negativas / compromisos
- El recorte es ciego. Corta por el final, así que en una licitación de 75 ítems
  el reranker puede ver solo los primeros 20 o 30. Si el ítem que le interesa a
  la empresa está al final, el puntaje sale más bajo de lo que debería.
- El puntaje de compatibilidad que ve el usuario (50 % reranker) de esas
  licitaciones se calcula sobre un texto incompleto, y nada en la interfaz lo
  indica.
- No cambia el embedding. BGE-M3 acepta 8192 tokens, así que la búsqueda
  vectorial sí ve la licitación completa. El reranker y la búsqueda vectorial
  miran textos distintos.

---

## 5. Pendiente: investigar una solución de fondo

Esta decisión resuelve la caída, no la calidad del ranking en licitaciones
largas. Antes de reemplazarla hay que medir, sobre un conjunto de empresas y
licitaciones con muchos ítems, si alguna de estas opciones ordena mejor que el
recorte por el final:

1. **Un texto para el reranker con presupuesto de tokens.** Nombre y
   descripción completos, y los ítems solo con su nombre (sin la descripción
   técnica), hasta llenar el presupuesto. Los nombres de ítem suelen bastar para
   saber de qué rubro es la compra.
2. **Priorizar los ítems más parecidos al perfil** antes de recortar, en vez de
   tomarlos en el orden en que vienen.
3. **Dividir en trozos** (por ejemplo, de a N ítems), rerankear cada trozo y
   quedarse con el puntaje máximo de la licitación.
4. **Resumir los ítems** al ingestar y guardar ese resumen como texto para el
   reranker.

La opción 1 es la más barata y probablemente la primera que conviene medir.
Cualquiera que se elija debe aplicarse también al modo local, que hoy recorta a
512 tokens, para no volver a tener dos comportamientos distintos.
