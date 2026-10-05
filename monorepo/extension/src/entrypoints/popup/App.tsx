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
    <div style={{ padding: "16px", backgroundColor: "#ffffff", color: "#1e293b", minWidth: "300px" }}>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px", borderBottom: "1px solid #e2e8f0", paddingBottom: "12px" }}>
        <div>
          <h1 style={{ fontSize: "16px", fontWeight: "700", margin: 0, color: "#0f172a" }}>Chiripa</h1>
          <p style={{ fontSize: "12px", color: "#64748b", margin: 0 }}>Licitaciones Inteligentes</p>
        </div>
        <span style={{ fontSize: "11px", backgroundColor: "#f1f5f9", padding: "2px 6px", borderRadius: "4px", color: "#475569" }}>v0.1.0</span>
      </header>

      {loading ? (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "24px 0", color: "#64748b", gap: "8px" }}>
          <RefreshCw size={16} className="animate-spin" />
          <span style={{ fontSize: "13px" }}>Cargando estado...</span>
        </div>
      ) : isPaired ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", backgroundColor: "#ecfdf5", padding: "10px 12px", borderRadius: "8px", color: "#065f46" }}>
            <CheckCircle2 size={18} color="#059669" />
            <span style={{ fontSize: "13px", fontWeight: "500" }}>Extensión vinculada a tu cuenta</span>
          </div>

          <div style={{ backgroundColor: "#f8fafc", padding: "12px", borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "12px" }}>
            <p style={{ margin: "0 0 6px 0", color: "#475569" }}>
              <strong>Sincronizador Mercado Público:</strong> {capabilities?.mp_adapter_enabled ? "Activo" : "En espera"}
            </p>
            <p style={{ margin: 0, color: "#475569" }}>
              <strong>Extracción distribuida:</strong> {capabilities?.fetch_jobs_enabled ? "Habilitada" : "Pausada"}
            </p>
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", backgroundColor: "#fffbeb", padding: "10px 12px", borderRadius: "8px", color: "#92400e" }}>
            <AlertCircle size={18} color="#d97706" />
            <span style={{ fontSize: "13px", fontWeight: "500" }}>Aún no vinculada</span>
          </div>
          <p style={{ fontSize: "12px", color: "#64748b", margin: 0, lineHeight: 1.4 }}>
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
              backgroundColor: "#2563eb",
              color: "#ffffff",
              padding: "8px 12px",
              borderRadius: "6px",
              textDecoration: "none",
              fontSize: "13px",
              fontWeight: "500",
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
