import React, { useEffect, useState } from "react";
import { CheckCircle2, AlertCircle, ExternalLink, RefreshCw } from "lucide-react";
import { ExtensionStorage } from "../../services/storage/extension-storage";
import { Capabilities } from "../../types/schemas";

export function App() {
  const [isPaired, setIsPaired] = useState<boolean>(false);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadState() {
      try {
        const creds = await ExtensionStorage.getCredentials();
        const caps = await ExtensionStorage.getCapabilities();
        setIsPaired(Boolean(creds.accessToken));
        setCapabilities(caps);
      } finally {
        setLoading(false);
      }
    }
    loadState();
  }, []);

  return (
    <div style={{ padding: "16px", backgroundColor: "var(--ch-bg-page)", color: "var(--ch-text-body)", minWidth: "300px", fontFamily: "var(--ch-font-sans)" }}>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px", borderBottom: "1px solid var(--ch-border-subtle)", paddingBottom: "12px" }}>
        <div>
          <h1 style={{ fontSize: "18px", fontWeight: "800", margin: 0, color: "var(--ch-primary-hover)", fontFamily: "var(--ch-font-display)", letterSpacing: "-0.01em" }}>Chiripa</h1>
          <p style={{ fontSize: "12px", color: "var(--ch-text-muted)", margin: 0 }}>Licitaciones Inteligentes</p>
        </div>
        <span style={{ fontSize: "11px", backgroundColor: "var(--ch-surface-inset)", border: "1px solid var(--ch-border-subtle)", padding: "2px 8px", borderRadius: "var(--ch-radius-xs)", color: "var(--ch-text-muted)" }}>
          v{chrome?.runtime?.getManifest?.()?.version ?? "0.2.0"}
        </span>
      </header>

      {loading ? (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "24px 0", color: "var(--ch-text-muted)", gap: "8px" }}>
          <RefreshCw size={16} className="animate-spin" />
          <span style={{ fontSize: "13px" }}>Cargando estado...</span>
        </div>
      ) : isPaired ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", backgroundColor: "var(--ch-success-soft)", padding: "10px 12px", borderRadius: "var(--ch-radius-md)", color: "var(--ch-success-text)" }}>
            <CheckCircle2 size={18} color="var(--ch-success)" />
            <span style={{ fontSize: "13px", fontWeight: "600" }}>Extensión vinculada a tu cuenta</span>
          </div>

          <div style={{ backgroundColor: "var(--ch-surface)", padding: "12px", borderRadius: "var(--ch-radius-md)", border: "1px solid var(--ch-border-subtle)", fontSize: "12px", boxShadow: "0 1px 2px rgba(27, 24, 20, 0.05)" }}>
            <p style={{ margin: "0 0 6px 0", color: "var(--ch-text-muted)" }}>
              <strong>Sincronizador Mercado Público:</strong> {capabilities?.mp_adapter_enabled ? "Activo" : "En espera"}
            </p>
            <p style={{ margin: 0, color: "var(--ch-text-muted)" }}>
              <strong>Extracción distribuida:</strong> {capabilities?.fetch_jobs_enabled ? "Habilitada" : "Pausada"}
            </p>
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", backgroundColor: "var(--ch-warning-soft)", padding: "10px 12px", borderRadius: "var(--ch-radius-md)", color: "var(--ch-warning-text)" }}>
            <AlertCircle size={18} color="var(--ch-warning)" />
            <span style={{ fontSize: "13px", fontWeight: "600" }}>Aún no vinculada</span>
          </div>
          <p style={{ fontSize: "12px", color: "var(--ch-text-muted)", margin: 0, lineHeight: 1.45 }}>
            Inicia sesión en Chiripa y haz clic en "Vincular Extensión" en la configuración de tu empresa.
          </p>
          <a
            href="http://localhost:3000"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px",
              backgroundColor: "var(--ch-primary)",
              color: "var(--ch-on-primary)",
              padding: "9px 14px",
              borderRadius: "var(--ch-radius-sm)",
              boxShadow: "var(--ch-shadow-teal)",
              textDecoration: "none",
              fontSize: "13px",
              fontWeight: "600",
            }}
          >
            <span>Ir a Chiripa</span>
            <ExternalLink size={14} />
          </a>
        </div>
      )}
    </div>
  );
}
