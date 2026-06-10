---
name: proyectosya-design
description: Use this skill to generate well-branded interfaces and assets for ProyectosYa (Chilean MiPyme / ChileCompra · Compra Ágil matching startup), either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping.
user-invocable: true
---

Read the `readme.md` file within this skill, and explore the other available files (`tokens/`, `components/`, `ui_kits/`, `assets/`, `guidelines/`).

If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and create static HTML files for the user to view — link `styles.css` for tokens/fonts, load Lucide for icons, and either reuse the React components (see `ui_kits/app/index.html` for the load pattern) or write plain HTML that uses the CSS custom properties. If working on production code, copy the assets and read the rules here to become an expert in designing with this brand.

Core brand cues to honor every time:
- Warm off-white background (`--bg-page`), warm near-black ink (`--warm-900`). Never pure black/white.
- Primary **teal** (`--primary #0E8580`) for trust/actions; **coral** accent (`--accent #E0552F`) used sparingly for high-energy "Ya" CTAs.
- Fonts: Bricolage Grotesque (display), Hanken Grotesk (text/UI), Spline Sans Mono (data/IDs).
- Soft radii, warm-tinted soft shadows, gentle motion, hover darkens / press shrinks.
- Spanish (Chile), tuteo, sentence case, no emoji. Tagline: "Menos papeleo. Más proyectos ganados."
- `MatchMeter` (compatibility ring) is the signature component.

If the user invokes this skill without any other guidance, ask them what they want to build or design, ask some questions, and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.
