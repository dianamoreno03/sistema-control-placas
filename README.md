# Sistema de Control de Placas y Alertas (LPR)

Este proyecto es una aplicación web desarrollada con **Flask** que combina el Reconocimiento Automático de Placas (**LPR**) mediante Visión Artificial con un sistema de gestión de acceso, bloqueo automático y envío de notificaciones por SMS.

---

## Características Principales

* **Reconocimiento de Placas (LPR):** Utiliza **OpenCV** y **Tesseract** (Sistema Experto multi-estrategia) para identificar matrículas a partir de imágenes capturadas en tiempo real (vía webcam o carga de archivos).

* **Consulta Rápida de Operador:** Interfaz para buscar la placa reconocida y verificar el estado de acceso (**Activo/Bloqueado**).

* **Gestión de Alertas y Bloqueo Automático:**
    * Registro de sanciones e incidentes.
    * **Auto-Bloqueo:** El acceso se restringe automáticamente al acumular **3 o más alertas**.

* **Notificaciones SMS:** Envío de alertas y cambios de estado (bloqueo/reactivación) a los asociados mediante el servicio **Twilio**.

* **Módulo de Administración:** Dashboard para la gestión de usuarios, vehículos y el estado de acceso manual.

## Tecnologías Utilizadas

| Componente | Tecnología | Propósito | 
| :--- | :--- | :--- | 
| **Backend** | Python, Flask | Servidor web y lógica de negocio. | 
| **Visión Artificial** | OpenCV, NumPy | Preprocesamiento de imágenes, detección de contornos (placas) y transformación de perspectiva. | 
| **OCR** | PyTesseract, Tesseract | Extracción y reconocimiento de caracteres de la placa enderezada. | 
| **Base de Datos** | SQLite3 | Almacenamiento local de la información de empleados, vehículos y el historial de alertas. | 
| **Comunicaciones** | Twilio API | Envío de notificaciones SMS a los asociados. | 

