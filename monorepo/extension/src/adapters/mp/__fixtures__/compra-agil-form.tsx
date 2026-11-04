import { useState } from "react";

/**
 * Réplica saneada del formulario «Participar de la Compra Ágil» observado el 2026-11-04
 * en compra-agil.mercadopublico.cl/resumen-cotizacion/<código>. Conserva lo que importa
 * al adaptador: textos visibles, inputs controlados por React sin name ni id, subtotal
 * deshabilitado, detalle con maxlength 255 y botón de envío que se habilita con datos.
 * Sin datos reales del comprador ni del proveedor.
 */

export interface CompraAgilFixtureItem {
  productId: string;
  name: string;
  quantity: number;
}

interface Props {
  code: string;
  items: CompraAgilFixtureItem[];
}

const clp = (n: number) => n.toLocaleString("es-CL");
const digits = (v: string) => v.replace(/\D/g, "");

function ItemRow({
  item,
  value,
  onChange,
}: {
  item: CompraAgilFixtureItem;
  value: string;
  onChange: (v: string) => void;
}) {
  const unit = Number(digits(value) || 0);
  return (
    <div className="item">
      <p>{item.name}</p>
      <p>{`ID: ${item.productId}`}</p>
      <p>TEXTO</p>
      <div>
        <p>Cantidad</p>
        <p>{`${item.quantity} Unidad`}</p>
      </div>
      <div>
        <span>Valor unitario</span>
        <div>
          <span>$</span>
          <input type="text" value={value} onChange={(e) => onChange(clp(Number(digits(e.target.value) || 0)))} />
        </div>
      </div>
      <div>
        <span>Subtotal</span>
        <input type="text" disabled value={unit ? clp(unit * item.quantity) : ""} readOnly />
      </div>
    </div>
  );
}

export function CompraAgilForm({ code, items }: Props) {
  const [prices, setPrices] = useState<string[]>(items.map(() => ""));
  const [shipping, setShipping] = useState("");
  const [detail, setDetail] = useState("");
  const [validity, setValidity] = useState("04/12/2026");

  const net = items.reduce((acc, it, i) => acc + Number(digits(prices[i]) || 0) * it.quantity, 0);
  const canSend = net > 0;

  return (
    <main>
      <h2>{`Detalle de la cotización ${code}`}</h2>
      <p>Nombre</p>
      <p>TEXTO</p>
      <h3>Participar de la Compra Ágil</h3>
      <span>Primer Llamado</span>
      {items.map((item, i) => (
        <ItemRow
          key={item.productId + i}
          item={item}
          value={prices[i]}
          onChange={(v) => setPrices((prev) => prev.map((p, j) => (j === i ? v : p)))}
        />
      ))}
      <div>
        <p>Valor de despacho</p>
        <span>Despacho</span>
        <div>
          <span>$</span>
          <input type="text" value={shipping} onChange={(e) => setShipping(e.target.value)} />
        </div>
      </div>
      <div>
        <p>Monto total</p>
        <p data-testid="total">{net ? `$ ${clp(Math.round(net * 1.19))}` : ""}</p>
      </div>
      <div>
        <p>Detalle de la cotización</p>
        <span>Detalle cotización</span>
        <textarea maxLength={255} value={detail} onChange={(e) => setDetail(e.target.value)} />
        <span>{`${detail.length}/255`}</span>
      </div>
      <div>
        <span>Fecha de vigencia</span>
        <input type="text" id=":r0:" value={validity} onChange={(e) => setValidity(e.target.value)} />
      </div>
      <div>
        <p>Adjuntar archivos</p>
        <span>documento anexo (opcional)</span>
        <input type="text" readOnly value="" />
        <button type="button">Examinar</button>
        <input type="file" style={{ display: "none" }} />
      </div>
      <button type="button">Volver</button>
      <button type="button" disabled={!canSend}>
        Enviar cotización
      </button>
    </main>
  );
}
