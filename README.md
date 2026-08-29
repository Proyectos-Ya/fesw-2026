# ProyectosYA - Monorepo

Bienvenido al repositorio principal de **ProyectosYA**, una plataforma de matching y gestión de licitaciones de Mercado Público potenciada por Inteligencia Artificial.

El repositorio está organizado como un monorepo bajo el directorio `monorepo/`:
* [Frontend (Next.js)](./monorepo/frontend)
* [Backend (FastAPI)](./monorepo/backend)

---

## 📚 Documentación del Proyecto

Para obtener información detallada sobre la instalación, configuración y la arquitectura de cada módulo, puedes revisar los siguientes documentos:

* 💻 **Frontend**: Consulta el [README de Frontend](./monorepo/frontend/README.md) para conocer las dependencias, la Screaming Architecture y cómo iniciar el servidor de desarrollo de Next.js.
* 🐍 **Backend**: Consulta el [README de Backend](./monorepo/backend/README.md) para configurar el entorno virtual de Python, iniciar la base de datos PostgreSQL mediante Docker, y levantar la API con FastAPI.
* 📋 **Historias de Usuario (User Stories)**:
  - Para conocer el alcance y criterios de aceptación del producto mínimo viable, lee [Historias de Usuario - MVP](./user-story/user-stories-mvp.md).
  - Para ver el roadmap y las historias planificadas para el resto del año, revisa [Historias de Usuario - Anual](./user-story/user-stories-anual.md).

---

## Configuración de Asistentes y Agentes de IA

Si utilizas asistentes de código basados en IA (**Antigravity, Claude Code, Cursor, OpenCode, Copilot**, etc.), es **fundamental** configurarlos para que respeten las reglas y estándares de este repositorio. Esto evitará conflictos de arquitectura, commits mal estructurados o pushes no autorizados.

### ¿Cómo configurarlos con `AGENTS.md` y `SKILL.md`?

En la raíz del repositorio cuentas con dos guías críticas:
* [AGENTS.md](./ProyectosYA/AGENTS.md): Reglas de arquitectura, tecnologías y dependencias obligatorias del proyecto.
* [SKILL.md](./SKILL.md): Instrucciones operativas para agentes en Git (formato de commits de IA y prohibición estricta de push).

#### 1. Configuración en Cursor / VS Code (Cursor Rules)
Para que Cursor use estas reglas automáticamente en todos tus chats y ediciones:
* El repositorio lee las reglas de forma nativa al incluir referencias de contexto.
* Puedes configurar el asistente añadiendo las reglas a la configuración de tu área de trabajo o creando un enlace en tus instrucciones de Cursor:
  > *"Siempre lee, respeta y sigue estrictamente las directrices del archivo [AGENTS.md](./AGENTS.md) y [SKILL.md](./SKILL.md) antes de escribir código, hacer pruebas o realizar cualquier commit."*

#### 2. Configuración en Antigravity / Claude Code
Cuando inicies una conversación o un agente autónomo de Antigravity/Claude Code:
* Puedes referenciar directamente los archivos en tu prompt inicial:
  `@AGENTS.md @SKILL.md`
* También puedes configurar las instrucciones del sistema del agente en tu configuración local del espacio de trabajo para cargar siempre el contexto de estos archivos.

#### 3. Configuración en OpenCode / Copilot (Instrucciones Personalizadas de Workspace)
Puedes definir reglas en tu editor de código para que el asistente de IA las consuma por defecto.
* Crea o edita el archivo `.vscode/settings.json` en la raíz de tu workspace y añade las directrices en la sección de configuraciones personalizadas del agente de IA:
  ```json
  {
    "github.copilot.chat.codeGeneration.instructions": [
      "Lee y adhiérete estrictamente a las reglas de desarrollo de AGENTS.md y SKILL.md en la raíz del proyecto."
    ]
  }
  ```

---

## Reglas de Oro para Todos los Desarrolladores y Agentes

1. **Gestor de Dependencias**: Usa únicamente **`pnpm`** en la carpeta `monorepo/frontend` por motivos de seguridad y velocidad.
2. **Ciclo TDD**: Nunca confirmes código sin haber corrido la suite de pruebas (`pytest` en backend y `pnpm run test` en frontend).
3. **Tipado Estricto (TypeScript)**: Está estrictamente prohibido utilizar el tipo `any`. Todo código debe hacer uso de tipado fuerte (definiendo interfaces, tipos concretos o genéricos).
4. **Commits y Push**: Sigue el estándar de Conventional Commits. Si dejas que una IA haga el commit por ti, asegúrate de que incluya la etiqueta `[AI Generated]`. **Las IAs tienen prohibido hacer push directo al origen.**
