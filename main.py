import base64
import io
import os
import re
from datetime import datetime
from typing import Optional

import pymupdf as fitz  # PyMuPDF
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

#si existe un .env lo carga
load_dotenv()
#expone endpoint de lmstudio, usa el tipicolocalhost
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", "qwen3-vl-30b-a3b-instruct")
#limites internos para que no tarde de mas, antes tenia puesto el contexto maximo y tardaba de mas..
MAX_CONTEXT_CHARS = 9000
MAX_HISTORY_CHARS = 6000

#prompt de sistema para definir el comportamiento, en principio defensivo a no ser que seas explicito.
SYSTEM_PROMPT = """
Eres un agente multimodal local experto en soporte técnico y ciberseguridad.

Tu función es analizar documentos, capturas, logs, csvs y preguntas del usuario para
generar respuestas útiles y estructuradas. Debes actuar siempre desde un
enfoque defensivo: diagnóstico, análisis de evidencias, priorización, mitigación,
hardening, documentación y mejora operativa.

No inventes datos que no aparezcan en la entrada. Si algo no está claro, indícalo.
Si propones comandos o acciones técnicas, deben ser seguros, reversibles cuando sea
posible y explicados. No proporciones instrucciones ofensivas ni explotación activa a no ser que se indiquen explicitamente.

Formato de salida por defecto:
1º Resumen ejecutivo breve
2º Evidencias clave
3º Diagnóstico o interpretación
4º Acciones recomendadas
5º Limitaciones

Reglas de longitud:
Responde de forma completa pero concisa.
No desarrolles subapartados largos salvo que el usuario pida un informe completo.
Si el usuario pide una respuesta breve, responde en 1-3 frases.
Si el usuario pide un análisis completo, puedes extenderte más.
""".strip()

# 3 modos bastante explicativos.. el corto, el "normal" y el completo.
MODE_INSTRUCTIONS = {
    "Respuesta breve": "Responde en formato breve. Máximo 1-3 párrafos o 5 viñetas.",
    "Análisis técnico": "Responde con análisis estructurado en 4-5 apartados. Sé claro y operativo.",
    "Informe completo": "Genera un informe amplio con evidencias, interpretación, riesgos, acciones y limitaciones.",
}

#especifico para cuando usa pdfs..
PROMPTS = {
    "pdf": """
Analiza el siguiente contenido extraído de un PDF técnico.

IMPORTANTE:
-El contexto puede ser una página concreta o varias páginas candidatas localizadas automáticamente.
-Responde usando únicamente el contenido proporcionado.
-Si aparecen páginas candidatas, prioriza las que tengan coincidencias claras con la pregunta.
-Si el contexto no contiene la respuesta, dilo claramente.

Modo de respuesta:
{response_mode}

Documento:
{doc_context}

Historial de conversación:
{history}

Pregunta del usuario:
{user_question}

Genera una respuesta estructurada, clara y directa. Si la pregunta pide una lista concreta,
responde primero con la lista y después añade una breve explicación.
""".strip(),
    "csv": """
Analiza el siguiente resumen de un CSV.

Modo de respuesta:
{response_mode}

Resumen del CSV:
{doc_context}

Historial de conversación:
{history}

Pregunta del usuario:
{user_question}

Genera una respuesta estructurada y concisa. Busca patrones, columnas relevantes,
posibles anomalías, eventos sospechosos, valores atípicos, concentraciones por
categoría, errores de formato y conclusiones operativas.

No redactes un informe largo salvo que el usuario lo pida explícitamente.
Prioriza los hallazgos más importantes.
""".strip(),
    "text": """
Analiza el siguiente texto o log técnico.

Modo de respuesta:
{response_mode}

Contenido:
{doc_context}

Historial de conversación:
{history}

Pregunta del usuario:
{user_question}

Genera una respuesta estructurada. Si son logs, identifica errores, warnings,
secuencia temporal, causa probable, impacto y pasos de resolución.
""".strip(),
    "generic": """
Responde a la pregunta del usuario usando el contexto disponible.

Modo de respuesta:
{response_mode}

Contexto:
{doc_context}

Historial de conversación:
{history}

Pregunta del usuario:
{user_question}
""".strip(),
}

#cachea conexion para no recrear en cada rerun de streamlit
@st.cache_resource
def get_llm() -> ChatOpenAI:
    """Crea una conexión reutilizable con el modelo local servido por LM Studio."""
    return ChatOpenAI(
        base_url=LMSTUDIO_BASE_URL,
        api_key="lm-studio",
        model=LMSTUDIO_MODEL,
        temperature=0.2,
        max_tokens=1600,
    )

#recorta contexto antes de enviarlo, sale si es demasiado largo o extenso, ya tuve que modificar varias veces los max tokens
def truncate_text(text: str, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """Recorta textos largos para evitar prompts excesivos."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[Texto recortado por longitud para mantener la respuesta operativa.]"

#detecta el tipo de fichero y decide que usar segun la extensión.
def detect_file_type(filename: str) -> str:
    """Detecta el tipo de archivo según su extensión."""
    ext = filename.lower().split(".")[-1]

    if ext in {"png", "jpg", "jpeg", "webp"}:
        return "image"
    if ext == "pdf":
        return "pdf"
    if ext == "csv":
        return "csv"
    if ext in {"txt", "log", "md"}:
        return "text"

    return "unknown"


def decode_text_file(file_bytes: bytes) -> str:
    """Decodifica archivos de texto intentando UTF-8 y después Latin-1."""
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("latin-1", errors="replace")


def extract_pdf_pages(file_bytes: bytes) -> list[str]:
    """Extrae el texto de cada página del PDF y lo conserva por separado."""
    document = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []

    for page_number, page in enumerate(document, start=1):
        text = page.get_text("text", sort=True)
        pages.append(f"--- Página {page_number} ---\n{text}")

    return pages

#tube que retocar esto varias veces porque en los pdf largos se recortaba. extrae y conserva cada pagina por separado
def extract_requested_page_number(question: str) -> Optional[int]:
    """Detecta si el usuario pregunta por una página concreta."""
    patterns = [
        r"p[aá]gina\s+(\d+)",
        r"pag\.?\s*(\d+)",
        r"page\s+(\d+)",
    ]

    question_lower = question.lower()

    for pattern in patterns:
        match = re.search(pattern, question_lower)
        if match:
            return int(match.group(1))

    return None

#busqueda sin rag, selecciona paginas por coincidencia..
def search_relevant_pdf_pages(user_question: str, top_k: int = 3) -> str:
    """
    Busca páginas relevantes del PDF cuando el usuario no indica página concreta.
    Es una búsqueda simple por términos, sin montar RAG.
    """
    pdf_pages = st.session_state.get("pdf_pages", [])

    if not pdf_pages:
        return st.session_state.get("document_context", "No hay contexto PDF disponible.")

    stopwords = {
        "el", "la", "los", "las", "un", "una", "unos", "unas",
        "de", "del", "en", "y", "o", "que", "cual", "cuales",
        "cuáles", "son", "segun", "según", "pdf", "documento",
        "dime", "explica", "sobre", "al", "por", "para", "con", "como",
        "qué", "cuales", "cuáles", "tiene", "tienen", "segun", "según"
    }

    terms = re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ0-9_]+", user_question.lower())
    terms = [term for term in terms if len(term) > 2 and term not in stopwords]

    if not terms:
        return st.session_state.get("document_context", "No hay contexto PDF disponible.")

    scored_pages = []

    for index, page_text in enumerate(pdf_pages, start=1):
        page_lower = page_text.lower()
        score = 0

        for term in terms:
            score += page_lower.count(term)

        if score > 0:
            scored_pages.append((score, index, page_text))

    if not scored_pages:
        return (
            "No se encontraron páginas claramente relacionadas con la pregunta. "
            "Vista previa disponible:\n\n"
            + st.session_state.get("document_context", "")
        )

    scored_pages.sort(reverse=True, key=lambda item: item[0])
    selected_pages = scored_pages[:top_k]

    context_parts = [
        f"[Página candidata {page_number} | coincidencias: {score}]\n{page_text}"
        for score, page_number, page_text in selected_pages
    ]

    return truncate_text("\n\n".join(context_parts), max_chars=MAX_CONTEXT_CHARS)


def build_pdf_context_for_question(user_question: str) -> str:
    """
    Construye contexto PDF inteligente.
    Si el usuario menciona una página concreta, usa esa página.
    Si no, busca páginas relevantes por términos de la pregunta.
    """
    pdf_pages = st.session_state.get("pdf_pages", [])
    requested_page = extract_requested_page_number(user_question)

    if requested_page and pdf_pages:
        if 1 <= requested_page <= len(pdf_pages):
            return pdf_pages[requested_page - 1]

        return (
            f"El usuario ha pedido la página {requested_page}, "
            f"pero el PDF solo tiene {len(pdf_pages)} páginas."
        )

    return search_relevant_pdf_pages(user_question, top_k=3)


def extract_pdf_text(file_bytes: bytes) -> str:
    """Extrae texto del PDF, guarda páginas y genera una vista previa manejable."""
    pages = extract_pdf_pages(file_bytes)

    st.session_state["pdf_pages"] = pages
    st.session_state["pdf_total_pages"] = len(pages)

    preview = "\n\n".join(pages[:5])

    if len(pages) > 5:
        preview += (
            f"\n\n[Vista previa limitada a las 5 primeras páginas. "
            f"PDF completo cargado con {len(pages)} páginas. "
            f"Puedes preguntar por una página concreta o por un término del documento.]"
        )

    return truncate_text(preview)

#resumen del csv de las columnas, tipos, nulos, estadisticas.
def summarize_csv(file_bytes: bytes) -> str:
    """Carga un CSV y genera un resumen textual útil para el modelo."""
    df = pd.read_csv(io.BytesIO(file_bytes), sep=None, engine="python")

    buffer = [
        f"Filas: {df.shape[0]}",
        f"Columnas: {df.shape[1]}",
        "\nColumnas detectadas:",
        ", ".join(df.columns.astype(str).tolist()),
        "\nTipos de datos:",
        df.dtypes.astype(str).to_string(),
        "\nValores nulos por columna:",
        df.isna().sum().to_string(),
        "\nPrimeras filas:",
        df.head(10).to_string(index=False),
    ]

    numeric_df = df.select_dtypes(include="number")
    if not numeric_df.empty:
        buffer.append("\nEstadísticas numéricas:")
        buffer.append(numeric_df.describe().to_string())

    categorical_df = df.select_dtypes(exclude="number")
    if not categorical_df.empty:
        buffer.append("\nValores frecuentes en columnas categóricas principales:")
        for column in categorical_df.columns[:8]:
            buffer.append(f"\nColumna: {column}")
            buffer.append(categorical_df[column].astype(str).value_counts(dropna=False).head(10).to_string())

    st.session_state["csv_rows"] = df.shape[0]
    st.session_state["csv_columns"] = df.shape[1]

    return truncate_text("\n".join(buffer))

#convierte la imagen y la envia al vlm usando el formato multimodal
def image_to_data_url(file_bytes: bytes, mime_type: Optional[str]) -> str:
    """Convierte una imagen subida a data URL para enviarla al modelo multimodal."""
    mime = mime_type or "image/png"
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def build_history_text() -> str:
    """Convierte el historial de chat en texto compacto para mantener contexto."""
    history = st.session_state.get("chat_history", [])
    if not history:
        return "Sin historial previo."

    lines = []
    for item in history[-8:]:
        role = item["role"]
        content = item["content"]
        lines.append(f"{role.upper()}: {content}")

    return truncate_text("\n".join(lines), max_chars=MAX_HISTORY_CHARS)


#al final una vez procesado el informe, que se pueda descargar en formato markdown con metadatos
def build_markdown_report() -> str:
    """Genera un informe Markdown descargable con metadatos y la última respuesta del agente."""
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    filename = st.session_state.get("uploaded_filename") or "Sin archivo"
    file_type = st.session_state.get("file_type") or "Sin tipo"
    response_mode = st.session_state.get("response_mode", "Análisis técnico")
    last_question = st.session_state.get("last_question") or "Sin pregunta registrada"
    last_answer = st.session_state.get("last_answer") or "Sin respuesta registrada"

    report = f"""# Informe del Agente Multimodal

**Fecha de generación:** {generated_at}  
**Archivo analizado:** {filename}  
**Tipo de entrada:** {file_type}  
**Modo de respuesta:** {response_mode}  
**Modelo local:** {LMSTUDIO_MODEL}  
**Servidor LM Studio:** {LMSTUDIO_BASE_URL}

---

## Pregunta realizada

{last_question}

---

## Respuesta del agente

{last_answer}

---

## Nota técnica

Este informe ha sido generado por una aplicación local desarrollada con Streamlit,
LangChain y un modelo multimodal servido desde LM Studio.
"""

    return report

#invoca langchain para pdf,csv,txt,log, md o preguntas
def invoke_text_agent(file_type: str, user_question: str) -> str:
    """Ejecuta una chain de LangChain para documentos de texto, PDF o CSV."""
    llm = get_llm()
    history = build_history_text()
    response_mode = MODE_INSTRUCTIONS.get(
        st.session_state.get("response_mode", "Análisis técnico"),
        MODE_INSTRUCTIONS["Análisis técnico"],
    )

    if file_type == "pdf":
        doc_context = build_pdf_context_for_question(user_question)
    else:
        doc_context = st.session_state.get("document_context", "No hay documento cargado.")

    selected_prompt = PROMPTS.get(file_type, PROMPTS["generic"])

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", selected_prompt),
        ]
    )

    chain = prompt | llm

    response = chain.invoke(
        {
            "doc_context": doc_context,
            "history": history,
            "user_question": user_question,
            "response_mode": response_mode,
        }
    )

    return response.content

#parte del modelo multimodal para enviar texto y imagen al modelo local.
def invoke_image_agent(user_question: str) -> str:
    """Envía una imagen y una pregunta al modelo multimodal usando LangChain."""
    llm = get_llm()
    image_data_url = st.session_state.get("image_data_url")
    history = build_history_text()
    response_mode = MODE_INSTRUCTIONS.get(
        st.session_state.get("response_mode", "Análisis técnico"),
        MODE_INSTRUCTIONS["Análisis técnico"],
    )

    if not image_data_url:
        return "No hay imagen cargada para analizar."

    user_prompt = f"""
Analiza la imagen adjunta como captura técnica o evidencia visual.

Modo de respuesta:
{response_mode}

Historial de conversación:
{history}

Pregunta del usuario:
{user_question}

Devuelve una respuesta estructurada orientada a soporte técnico y ciberseguridad defensiva.
Si ves errores, paneles, logs, alertas, rutas, servicios, configuraciones o indicadores
visuales relevantes, descríbelos con precisión.
""".strip()

    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=[
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ]
            ),
        ]
    )

    return response.content

# limpieza de contexto para empezar de nuevo
def reset_document_state() -> None:
    """Limpia el contexto del documento actual."""
    st.session_state["uploaded_filename"] = None
    st.session_state["file_type"] = None
    st.session_state["document_context"] = ""
    st.session_state["image_data_url"] = None
    st.session_state["pdf_pages"] = []
    st.session_state["pdf_total_pages"] = 0
    st.session_state["csv_rows"] = None
    st.session_state["csv_columns"] = None


def process_uploaded_file(uploaded_file) -> None:
    """Procesa el archivo subido y guarda su contexto en session_state."""
    file_bytes = uploaded_file.getvalue()
    file_type = detect_file_type(uploaded_file.name)

    reset_document_state()

    st.session_state["uploaded_filename"] = uploaded_file.name
    st.session_state["file_type"] = file_type

    if file_type == "pdf":
        st.session_state["document_context"] = extract_pdf_text(file_bytes)

    elif file_type == "csv":
        st.session_state["document_context"] = summarize_csv(file_bytes)

    elif file_type == "text":
        st.session_state["document_context"] = truncate_text(decode_text_file(file_bytes))

    elif file_type == "image":
        st.session_state["image_data_url"] = image_to_data_url(file_bytes, uploaded_file.type)
        st.session_state["document_context"] = (
            "Imagen cargada correctamente. El análisis se hará mediante el modelo multimodal."
        )

    else:
        st.session_state["document_context"] = "Tipo de archivo no soportado todavía."

#para que tenga un estado permanente de streamlit y no tenga que perder el historial y contexto con cada iteración
def initialize_state() -> None:
    """Inicializa variables persistentes de Streamlit."""
    defaults = {
        "chat_history": [],
        "uploaded_filename": None,
        "file_type": None,
        "document_context": "",
        "image_data_url": None,
        "pdf_pages": [],
        "pdf_total_pages": 0,
        "csv_rows": None,
        "csv_columns": None,
        "last_uploaded_signature": None,
        "last_answer": "",
        "last_question": "",
        "response_mode": "Análisis técnico",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

#zona izquierda del panel archivo, tipo, tipo, filas y columnas..
def render_document_panel() -> None:
    """Muestra información del documento procesado."""
    st.subheader("Documento actual")

    if not st.session_state["uploaded_filename"]:
        st.info("Sube un PDF, CSV, imagen, TXT o LOG desde el panel lateral.")
        return

    st.write(f"Archivo: **{st.session_state['uploaded_filename']}**")
    st.write(f"Tipo detectado: **{st.session_state['file_type']}**")

    if st.session_state["file_type"] == "pdf":
        st.write(f"Páginas detectadas: **{st.session_state.get('pdf_total_pages', 0)}**")

    if st.session_state["file_type"] == "csv":
        st.write(f"Filas detectadas: **{st.session_state.get('csv_rows')}**")
        st.write(f"Columnas detectadas: **{st.session_state.get('csv_columns')}**")

    if st.session_state["file_type"] == "image" and st.session_state["image_data_url"]:
        st.image(st.session_state["image_data_url"], caption="Imagen cargada", use_container_width=True)
    else:
        with st.expander("Ver contexto extraído"):
            st.text_area(
                "Contenido procesado",
                value=st.session_state["document_context"],
                height=400,
                disabled=True,
            )
#zona derecha del panel con historico, usuario y asistente una vez hablas.
def render_chat_panel() -> None:
    """Muestra la conversación y ejecuta consultas contra el agente."""
    st.subheader("Conversación")

    for message in st.session_state["chat_history"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_question = st.chat_input("Haz una pregunta sobre el documento o la evidencia cargada...")

    if not user_question:
        return

    st.session_state["chat_history"].append({"role": "user", "content": user_question})

    with st.chat_message("user"):
        st.markdown(user_question)

    with st.chat_message("assistant"):
        with st.spinner("Analizando con el modelo local..."):
            try:
                current_type = st.session_state.get("file_type")

                if current_type == "image":
                    answer = invoke_image_agent(user_question)
                else:
                    answer = invoke_text_agent(current_type or "generic", user_question)

                st.markdown(answer)

            except Exception as exc:
                answer = f"Error durante la llamada al modelo local: `{exc}`"
                st.error(answer)

    st.session_state["last_answer"] = answer
    st.session_state["last_question"] = user_question
    st.session_state["chat_history"].append({"role": "assistant", "content": answer})

# panel de exportación separado para poder pintarlo después de generar la respuesta.
# esto evita el problema que vimos: la sidebar se dibujaba antes de guardar last_answer,
# y el botón solo aparecía al forzar un rerun cambiando el modo de respuesta.
def render_export_panel() -> None:
    """Muestra el botón de descarga del informe cuando ya existe una respuesta."""
    if not st.session_state.get("last_answer"):
        return

    st.divider()
    st.write("Exportación")

    report_md = build_markdown_report()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    st.download_button(
        label="Descargar informe (.md)",
        data=report_md,
        file_name=f"informe_agente_multimodal_{timestamp}.md",
        mime="text/markdown",
        use_container_width=True,
    )

#titulo general de la pagina y el icono con alusion a la seguridad.
def main() -> None:
    st.set_page_config(
        page_title="Agente Multimodal de Soporte Técnico y Ciberseguridad",
        page_icon="🛡️",
        layout="wide",
    )

    initialize_state()

    st.title("🛡️ Agente Multimodal de Soporte Técnico y Ciberseguridad Defensiva")
    st.caption("Modelo local en LMStudio, LangChain y Streamlit")

    with st.sidebar:
        st.header("Configuración")

        st.write("Servidor LM Studio:")
        st.code(LMSTUDIO_BASE_URL)

        st.write("Modelo:")
        st.code(LMSTUDIO_MODEL)

        st.session_state["response_mode"] = st.selectbox(
            "Modo de respuesta",
            ["Respuesta breve", "Análisis técnico", "Informe completo"],
            index=["Respuesta breve", "Análisis técnico", "Informe completo"].index(
                st.session_state.get("response_mode", "Análisis técnico")
            ),
        )

        uploaded_file = st.file_uploader(
            "Sube una evidencia o documento",
            type=["png", "jpg", "jpeg", "webp", "pdf", "csv", "txt", "log", "md"],
        )

        if uploaded_file is not None:
            signature = f"{uploaded_file.name}-{uploaded_file.size}"
            if signature != st.session_state.get("last_uploaded_signature"):
                try:
                    process_uploaded_file(uploaded_file)
                    st.session_state["last_uploaded_signature"] = signature
                    st.success(f"Archivo procesado: {uploaded_file.name}")
                except Exception as exc:
                    st.error(f"Error procesando el archivo: {exc}")

        if st.button("Limpiar conversación"):
            st.session_state["chat_history"] = []
            st.session_state["last_answer"] = ""
            st.session_state["last_question"] = ""
            st.success("Historial limpiado.")

    col1, col2 = st.columns([1, 1])

    with col1:
        render_document_panel()
    with col2:
        render_chat_panel()

    with st.sidebar:
        render_export_panel()

if __name__ == "__main__":
    main()
