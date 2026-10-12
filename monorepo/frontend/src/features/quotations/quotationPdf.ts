import { jsPDF } from "jspdf";
import { autoTable } from "jspdf-autotable";
import { type Quotation, subtotal, total, validate, formatInteger } from "./quotation";

/** Se carga solo al descargar; los datos nunca salen del navegador. */
export function quotationPdf(quotation: Quotation, tenderCode: string): Blob {
  const errors = validate(quotation.items);
  if (errors.length) throw new Error(errors[0]);
  if (quotation.currency !== "CLP") throw new Error("La cotización debe estar en CLP.");
  const doc = new jsPDF({ orientation: "landscape", unit: "mm", format: "a4" });
  doc.setProperties({ title: `Cotización ${tenderCode}`, author: "Chiripa" });
  const date = new Date(quotation.updated_at).toLocaleDateString("es-CL", { timeZone: "America/Santiago" });
  autoTable(doc, {
    head: [["Descripción", "Unidad", "Cantidad", "Precio unitario (CLP)", "Subtotal (CLP)"]],
    body: quotation.items.map(item => [item.description.trim(), item.unit.trim(), formatInteger(item.quantity), formatInteger(item.unit_price), formatInteger(subtotal(item))]),
    foot: [[{ content: "Total cotización", colSpan: 4 }, `${formatInteger(total(quotation.items))} CLP`]],
    theme: "striped",
    margin: { top: 48, bottom: 20, left: 14, right: 14 },
    styles: { font: "helvetica", fontSize: 9, cellPadding: 3, overflow: "linebreak", valign: "top" },
    headStyles: { fillColor: [15, 91, 85], textColor: 255 },
    footStyles: { fillColor: [15, 91, 85], textColor: 255, halign: "right" },
    columnStyles: {
      0: { cellWidth: 100 },
      1: { cellWidth: 30 },
      2: { cellWidth: 28, halign: "right" },
      3: { cellWidth: 45, halign: "right" },
      4: { cellWidth: 66, halign: "right" },
    },
    showHead: "everyPage",
    showFoot: "lastPage",
    rowPageBreak: "avoid",
    willDrawPage: () => {
      doc.setTextColor(15, 91, 85);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(19);
      doc.text("Chiripa | Cotización de materiales", 14, 16);
      doc.setTextColor(45);
      doc.setFont("helvetica", "normal");
      doc.setFontSize(10);
      doc.text(`Licitación: ${tenderCode}`, 14, 25);
      doc.text(`Empresa (ID): ${quotation.supplier_id}`, 14, 32);
      doc.text(`Fecha de guardado: ${date} | Moneda: CLP`, 14, 39);
    },
  });
  const pages = doc.getNumberOfPages();
  for (let page = 1; page <= pages; page++) {
    doc.setPage(page);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    doc.setTextColor(90);
    doc.text("Estimación de materiales. Total sin impuestos ni recargos.", 14, 199);
    doc.text(`Página ${page} de ${pages}`, 283, 199, { align: "right" });
  }
  return doc.output("blob");
}
