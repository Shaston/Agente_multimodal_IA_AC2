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





