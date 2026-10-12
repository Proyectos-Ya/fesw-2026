/** Lo que el backend deja visible donde falta un dato (CA2). */
const VACIO = /(\(Por favor, inserte aquí el valor [^)]*\))/;

/** Texto de un párrafo con los vacíos resaltados para que salten a la vista. */
export function HighlightedText({ text }: { text: string }) {
  return (
    <>
      {text.split(VACIO).map((trozo, i) =>
        VACIO.test(trozo) ? (
          <mark
            key={i}
            className="rounded bg-warning-soft px-1 font-semibold text-amber-700"
          >
            {trozo}
          </mark>
        ) : (
          <span key={i}>{trozo}</span>
        ),
      )}
    </>
  );
}
