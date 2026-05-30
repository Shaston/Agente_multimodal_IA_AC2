Se trata de un Proyecto de Agente Multimodal de tipo soporte tenico y ciberseguridad.

DESCRIPCION

El agente es capaz de analizar evidencias técnicas en distintos formatos y generar respuestas estructuradas orientadas a soporte técnico, analisis y documentación. 
La aplicacion permite cargar documentos, capturas de pantalla, logs, CSV y ficheros de texto para analizarlos mediante un modelo multimodal ejecutado en local con LMstudio.

El sistema utiliza Streamlit como interfaz web, Langchain como capa de orquestacion y un modelo local servido mediante un endpoint compatible con openai. Al tratarse de un modelo local corre con los recursos de tu maquina, en mi caso tengo 24gb de GPU y el modelo que he usado para que tenga cierto criterio usa unos 20gb~ de GPU, a continuación las siguientes especificaciones en LMstudio:

<img width="741" height="803" alt="image" src="https://github.com/user-attachments/assets/c4987e31-716b-4a38-87bb-5097df025050" />


Antes de entrar en mas materia, voy a explicar la instalación.

INSTALACIÓN
Lo primero seria clonar el repositorio, si es desde una terminal o consola de comandos:

git clone https://github.com/Shaston/Agente_multimodal_IA_AC2.git cd Agente_multimodal_IA_AC2

Si quieres de manera grafica, en el desplegable de code y a download zip.

Lo siguiente es un entorno virtual, en mi caso lo hice desde pycharm ya que me da el entorno virtual y mas cosas..

python -m venv .venv

Activar el entorno creado con el comando anterior, en el caso de widnows 
.venv\Scripts\activate 

Actualizar el pip por si acaso
python -m pip install --upgrade pip

y por fin.. instalar dependencias
pip install -r requirements.txt

Ahora, por la configuración de LM Studio

Abrir LM Studio, Descargarse el modelo que soporte vuestro equipo o hardware, en mi caso use qwen3-vl-30b-a3b-instruct pero se puede usar otro que sea multimodal si tiene uso de herramientas y visión, aunque es posible que no de los mismos resultados.
Activar el servidor local desde la pestaña Developer

<img width="629" height="111" alt="image" src="https://github.com/user-attachments/assets/9b190c04-53b4-4a2f-b53d-44259ea4a1ab" />


EJECUCIÓN

Con el entorno ya activado, lanzar el comando: streamlit run main.py

<img width="825" height="148" alt="image" src="https://github.com/user-attachments/assets/949e8720-8708-4e54-8b92-7560fb5a7d2d" />


Deberia abrirse una ventana del navegador, si no es asi usar la url http://localhost:8501/

Y con eso ya podrias acceder y usar el modelo para ver sus capacidades... ahora vamos con un poco mas de explicación sobre arquitectura, modelo, escenarios, etc..

DOMINIO o orientación del agente, serian para las siguientes tareas:

-Diagnóstico de errores técnicos
-Análisis de capturas de pantalla
-Revisión de logs
-Identificación de anomalías en CSV
-Análisis de documentación técnica
-Generación de recomendaciones del tipo hardening
-Apoyo a la documentación de incidencias

FUNCIONES PRINCIPALES

-Carga de evidencias en formato PDF, CSV, imagen, TXT, LOG y Markdown
-Análisis multimodal de capturas de pantalla
-Extracción de texto de PDFs mediante PymuPDF
-Búsqueda de páginas concretas dentro de PDFs "largos"
-Resumen automático de CSVs con pandas
-Conversación contextual durante la sesión

Tres modos de respuesta:
-Respuesta breve
-Análisis técnico
-Informe completo

Exportación de la última respuesta como informe Markdown.

ARQUITECTURA GENERAL

El flujo principal seria:

1. El usuario carga una evidencia desde la interfaz de Streamlit.
2. El sistema detecta el tipo de archivo.
3. Se aplica un procesamiento específico según el formato:
   
-PDF-> extracción página a página con PyMuPDF.

-CSV-> resumen estructurado con pandas.

-Imagen-> conversión a formato base64/data URL para el modelo multimodal.

-TXT, LOG o MD: decodificación y recorte controlado de contexto.

4. LangChain construye el prompt adecuado según el tipo de entrada.
5. El modelo local servido por LM Studio genera la respuesta.
6. Streamlit muestra el análisis en una interfaz conversacional.
7. La última respuesta puede exportarse como informe Markdown.

TECNOLOGÍAS UTILIZADAS

Python =>3.10 

Streamlit

LangChain

langchain-openai

langchain-community

LM Studio
Qwen3-VL-30B-A3B-Instruct (bajado de huggingface https://huggingface.co/lmstudio-community/Qwen3-VL-30B-A3B-Instruct-GGUF)

pandas

PymuPDF

Pillow

python-dotenv

MODELO UTILIZADO


qwen3-vl-30b-a3b-instruct desde LM Studio y se expone mediante el endpoint local http://127.0.0.1:1234/v1

La aplicación espera que LM Studio esté abierto, que el servidor local esté activo y que el modelo esté cargado antes de ejecutar Streamlit.


EJEMPLOS DE USO

Vamos con 3 escenarios con ejemplos o casos de uso.

Escenario 1 análisis de captura técnica
Se facilita una imagen y se pregunta al modelo sobre ella, la cual tiene que responder, en este caso uso el modo breve de respuesta para que no explaye. 

<img width="2070" height="778" alt="image" src="https://github.com/user-attachments/assets/14a77700-fe19-4100-8957-0519d269192a" />

Con ello se puede ver que analiza la imagen y da diagnostico y algunos consejos. 


Escenario 2 análisis de CSV

Se facilita un CSV y se pide que de info y detalles.
<img width="2055" height="764" alt="image" src="https://github.com/user-attachments/assets/5e5dfa25-72e8-4624-8f3a-a75d889f8df0" />

Con esto se comprueba el procesamiento tabular, la deteccion de patrones y la generacion de recomendaciones de seguridad.

Escenario 3 análisis de PDF
Se pide que busque algo concreto dentro del pdf. 

<img width="2058" height="849" alt="image" src="https://github.com/user-attachments/assets/8c18f639-140f-480c-ba9b-850510c17f65" />

Aqui se explayo un poco mas, porque tenia el modo de respuesta de analisis técnico. 

Se comprueba la extracción de texto, busqueda por pagina y generacion de respuesta contextual basada en el documento.

EXPORTACIÓN DE INFORMES

Después de recibir una respuesta del agente, aparece un botón para descargar el último análisis en formato Markdown.

El informe exportado incluye:

Fecha de generación.
Archivo analizado.
Tipo de entrada.
Modo de respuesta.
Modelo local utilizado.
Pregunta realizada.
Respuesta generada por el agente.


DEMO DE VIDEO 



El vídeo muestra el funcionamiento básico de la aplicación con tres escenarios.

Aqui os facilito la url -> https://github.com/Shaston/Agente_multimodal_IA_AC2/releases/tag/V1demo

y por si acaso esta tambien -> https://drive.google.com/file/d/1aGXxnqLaGSu6aWeMChtMME5mUVJW_4We/view?usp=sharing



LIMITACIONES


Teniendo en cuenta el modelo, hardware y algunas técnicas, las limitaciones son las siguientes.

No implementa RAG vectorial, utiliza búsqueda simple por términos en PDF.

No realiza OCR sobre PDF escaneados.

No ejecuta acciones reales sobre sistemas externos.

La calidad del análisis visual depende del modelo multimodal cargado.

La velocidad depende del tamaño del modelo, cuantización, configuración de contexto y hardware disponible.

La exportación se realiza en Markdown, no en PDF.
