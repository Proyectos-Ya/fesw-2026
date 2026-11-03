# Tareas HU-032 — Postular en Mercado Público desde Chiripa

**Plan**: [plan.md](./plan.md) · **Rama**: `318-hu-32-postular-mercado-publico` · **Issue**: Refs #318

**Reglas de desarrollo**:
1. TDD estricto: Primero el test y verlo fallar (Red).
2. Código mínimo para pasar el test (Green).
3. Refactorización (Refactor).
4. Tipado estricto: Prohibido el tipo `any`.
5. Solo `pnpm` para dependencias y scripts de frontend/extensión.
6. Commits atómicos: `<tipo>(<alcance>): …` con la marca `[AI Generated]`.

---

## F0 — Preparación y Documentación
- [x] **T0.1** Documentar la arquitectura en plan técnico y ADR.
- [x] **T0.2** Crear la rama de trabajo `318-hu-32-postular-mercado-publico` desde `develop`.
- [x] **T0.3** Copiar plan y tareas a `docs/plans/318-hu-32-postular-mercado-publico/` y enlazar en `docs/README.md`.
- [x] **T0.4** Redactar ADR `docs/decisions/0006-postulacion-asistida-mercado-publico.md`.
- [ ] **T0.5** Cuentas de stores preparadas (Chrome Web Store y Firefox AMO).

## F1 — Spike del Formulario de Mercado Público
- [ ] **T1.1** Recopilar HTML de páginas clave (login, ficha con botón cotizar, formulario vacío, formulario con adjuntos) sin enviar ni aceptar declaraciones juradas.
- [ ] **T1.2** Documentar en `spikes/hu-32-formulario-mp/README.md` los selectores estables y validaciones.
- [ ] **T1.3** Sanitizar datos sensibles y alojar fixtures en `extension/src/adapters/mp/__fixtures__/`.

## F2 — Endurecimiento de la Extensión (CWS / AMO Ready)
- [ ] **T2.1** Generar íconos estándar de 16, 32, 48 y 128 px en `monorepo/extension/public/icons/`.
- [ ] **T2.2** Configurar devdeps de testing DOM (`happy-dom`, `fake-indexeddb`) y `vitest.config.ts`.
- [ ] **T2.3** [Red-Green] Manifiesto limpio y dinámico (`buildManifest`), removiendo permiso `cookies`, ajustando matches de producción y agregando `gecko.id` + `data_collection_permissions`.
- [ ] **T2.4** Sincronizar versión `0.2.0` dinámicamente desde `package.json` en `background.ts`, `bridge.content.ts` y `App.tsx`.
- [ ] **T2.5** Desactivar `JobRunner` por defecto con flag hasta resolver H7.
- [ ] **T2.6** Sanitizar `mp.content.ts` eliminando `innerHTML` en favor de `textContent`.
- [ ] **T2.7** Agregar job de CI `test-extension` en `.github/workflows/ci.yml`.
- [ ] **T2.8** Documentar guía de compilación reproducible en `monorepo/extension/README.md`.

## F3 — Backend (`monorepo/backend`)
- [ ] **T3.1** [Red-Green] Configurar flag `extension_postulation_enabled` en `config.py` y reflejarlo en `get_extension_capabilities.py`.
- [ ] **T3.2** [Red-Green] Definir esquemas Pydantic `PostulationPackage` en `proposal_schema.py`.
- [ ] **T3.3** [Red-Green] Implementar `BuildPostulationPackageUseCase` con matching determinista cotización ↔ ítems licitación.
- [ ] **T3.4** [Red-Green] Exponer endpoint `GET /tenders/{tender_id}/proposal/postulation-package` en router `proposal.py`.
- [ ] **T3.5** Validar integridad con `pytest` y verificar ausencia de cabezas Alembic en conflicto.

## F4 — Extensión: Motor de Postulación
- [ ] **T4.1** [Red-Green] Esquemas Zod para mensajes y payload de postulación con validaciones estrictas.
- [ ] **T4.2** [Red-Green] Protocolo `bridge.content.ts` y `content-script-bridge.ts` para `OPEN_POSTULATION` y `CONFIRM_POSTULATION` con chunking de binarios.
- [ ] **T4.3** [Red-Green] Almacén de persistencia local `postulation-store.ts` (IndexedDB + storage.local) con TTL de 30 min.
- [ ] **T4.4** [Red-Green] Coordinador en service worker (`postulation-coordinator.ts`) para gestión de pestañas y entrega de paquetes.
- [ ] **T4.5** [Red-Green] Adaptador `mp-postulation-adapter.ts` con selectores del spike:
  - CA5: Detección pasiva en login sin tocar inputs ni contraseñas.
  - CA6: Carga de valores, datos de empresa y adjuntos con sesión activa.
  - CA7: Resaltado de campos (`filled` / `incomplete`).
  - CA8: Garantía absoluta de no envío automático.
- [ ] **T4.6** [Red-Green] Tests estáticos de seguridad (`static-guards.test.ts`) bloqueando `.submit()`, `.click()` de envío y acceso a passwords/cookies.
- [ ] **T4.7** [Red-Green] Panel de control en Shadow DOM (`postulation-panel.ts`) para asistencia al usuario.

## F5 — Frontend (`monorepo/frontend`)
- [ ] **T5.1** [Red-Green] Implementar `extensionBridge.ts` con tipado estricto (sin `any`).
- [ ] **T5.2** [Red-Green] Hook `useMercadoPublicoPostulation` gestionando estados de detección, apertura y confirmación.
- [ ] **T5.3** [Red-Green] Componente `PostularEnMercadoPublicoButton.tsx` (CA1).
- [ ] **T5.4** [Red-Green] Diálogo informativo `ExtensionRequiredDialog.tsx` (CA2).
- [ ] **T5.5** [Red-Green] Diálogo de confirmación `PostulationConfirmDialog.tsx` (CA3, CA4).
- [ ] **T5.6** [Red-Green] Página pública de política de privacidad de la extensión (`/privacidad/extension`).

## F6 — Pruebas End-to-End y Verificación
- [ ] **T6.1** Suite E2E en Playwright para flujo completo en frontend.
- [ ] **T6.2** Suite E2E en extensión cargando fixtures locales en Chromium.
- [ ] **T6.3** Verificación manual en Chrome, Edge y Firefox con Compra Ágil real (sin envío).

## F7 & F8 — Publicación y Despliegue
- [ ] **T7.1** Assets visuales y textos para Chrome Web Store y Firefox AMO.
- [ ] **T7.2** Envío a revisión en ambas tiendas.
- [ ] **T7.3** Despliegue en producción activando variables de entorno en Railway y Vercel.
