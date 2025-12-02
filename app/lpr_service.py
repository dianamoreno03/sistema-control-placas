import cv2 # Biblioteca OpenCV para visión artificial
import pytesseract # Wrapper de Python para Tesseract OCR
import numpy as np # Para manejo de arrays y cálculos matriciales 
import os # Para interacciones con el sistema operativo y rutas de archivos
import re # Para expresiones regulares, usado en la limpieza del texto reconocido

# --- Configuración de Tesseract ---
#ruta del ejecutable de Tesseract. 
try:                                        
    pytesseract.pytesseract.tesseract_cmd = r'/opt/homebrew/bin/tesseract' 
except:
    pass # Si falla, intenta continuar asumiendo que está en el PATH del sistema

def preprocess_image(img):
    """
    Realiza múltiples técnicas de preprocesamiento para mejorar la detección de caracteres.
    Retorna la imagen en escala de grises y una lista de imágenes preprocesadas para probar.
    """
    # Convierte la imagen a escala de grises, fundamental para muchos algoritmos de CV.
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Lista para almacenar las diferentes versiones preprocesadas de la imagen.
    methods = []
    
    # Método 1: Bilateral filter + threshold adaptativo
    # BilateralFilter: Reduce el ruido manteniendo los bordes afilados.
    blur1 = cv2.bilateralFilter(gray, 11, 17, 17)
    # Adaptive Threshold: Usa un umbral diferente para cada área, útil para iluminación desigual.
    thresh1 = cv2.adaptiveThreshold(blur1, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                     cv2.THRESH_BINARY, 11, 2)
    methods.append(thresh1)
    
    # Método 2: Gaussian blur + Otsu
    # GaussianBlur: Suaviza la imagen para eliminar ruido de alta frecuencia.
    blur2 = cv2.GaussianBlur(gray, (5, 5), 0)
    # Encuentra automáticamente un umbral global óptimo 
    _, thresh2 = cv2.threshold(blur2, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    methods.append(thresh2)
    
    # Método 3: Mejora de contraste 
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    methods.append(enhanced)
    
    # Método 4: Original con bilateral (solo reducción de ruido sin binarización fuerte)
    blur4 = cv2.bilateralFilter(gray, 13, 15, 15)
    methods.append(blur4)
    
    return gray, methods

def find_plate_contours(img, gray):
    """
    Busca contornos que puedan ser placas de matrícula mediante detección de bordes y filtrado geométrico.
    Retorna una lista con los mejores contornos candidatos.
    """
    candidates = [] # Lista para almacenar los contornos que cumplen los criterios
    
    # Estrategia 1: Canny con diferentes umbrales (multi-escala)
    for low, high in [(30, 200), (50, 150), (70, 210)]:
        # Canny: Algoritmo para la detección de bordes.
        edged = cv2.Canny(gray, low, high)
        # findContours: Encuentra los contornos (curvas que unen puntos continuos) en la imagen.
        contours, _ = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        # Ordena por área y selecciona solo los 40 contornos más grandes.
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:40]
        
        for c in contours:
            # Calcula el perímetro del contorno.
            perimeter = cv2.arcLength(c, True)
            # approxPolyDP: Aproxima el contorno a una forma poligonal (rectángulo en este caso).
            approx = cv2.approxPolyDP(c, 0.018 * perimeter, True)
            
            # Buscar rectángulos (4 lados)
            if len(approx) == 4:
                # Obtiene las coordenadas del rectángulo delimitador.
                x, y, w, h = cv2.boundingRect(approx)
                aspect_ratio = w / float(h)
                
                # Filtros geométricos:
                # 1. Ratio típico de placas: entre 1.5 y 5.5
                # 2. Tamaño mínimo para evitar ruido (w > 50, h > 15)
                if 1.5 <= aspect_ratio <= 5.5 and w > 50 and h > 15:
                    # Almacena el contorno, su área (para ordenar) y el aspect ratio.
                    candidates.append((approx, cv2.contourArea(c), aspect_ratio))
    
    # Ordenar por área para priorizar las placas más grandes/cercanas
    candidates.sort(key=lambda x: x[1], reverse=True)
    
    return [c[0] for c in candidates[:5]]  # Retorna solo los 5 contornos más prometedores

def extract_roi(gray, contour):
    """
    Extrae la Región de Interés (ROI) aplicando una Transformación de Perspectiva 
    para enderezar el contorno de la placa.
    Retorna la imagen de la placa enderezada.
    """
    try:
        # Remodela los 4 puntos del contorno para calcular la transformación.
        pts = contour.reshape(4, 2)
        # Array para los puntos ordenados: TL, TR, BR, BL
        rect = np.zeros((4, 2), dtype="float32")
        
        # Ordena los puntos (Top-Left, Bottom-Right, Top-Right, Bottom-Left)
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)] # Top-Left (mínima suma x+y)
        rect[2] = pts[np.argmax(s)] # Bottom-Right (máxima suma x+y)
        
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)] # Top-Right (mínima diff x-y)
        rect[3] = pts[np.argmax(diff)] # Bottom-Left (máxima diff x-y)
        
        (tl, tr, br, bl) = rect
        
        # Calcula la anchura y altura de la nueva imagen enderezada.
        widthA = np.linalg.norm(br - bl)
        widthB = np.linalg.norm(tr - tl)
        maxWidth = max(int(widthA), int(widthB))
        
        heightA = np.linalg.norm(tr - br)
        heightB = np.linalg.norm(tl - bl)
        maxHeight = max(int(heightA), int(heightB))
        
        # Evitar dimensiones inválidas
        if maxWidth < 20 or maxHeight < 10:
            return None
        
        # Define los puntos de destino para la transformación (un rectángulo perfecto).
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]], dtype="float32")
        
        # Calcula la matriz de transformación de perspectiva.
        M = cv2.getPerspectiveTransform(rect, dst)
        # Aplica la transformación (warping) a la imagen.
        warped = cv2.warpPerspective(gray, M, (maxWidth, maxHeight))
        
        return warped
    except:
        return None

def ocr_recognize(roi, config_set):
    """
    Aplica Tesseract sobre la Región de Interés usando múltiples configuraciones de OCR.
    Retorna una lista de los resultados de texto limpios.
    """
    results = []
    
    for config in config_set:
        try:
            # image_to_string: Función principal de Tesseract.
            # config: Opciones personalizadas para Tesseract 
            text = pytesseract.image_to_string(roi, config=config)
            cleaned = clean_plate_text(text)
            if cleaned:
                results.append(cleaned)
        except:
            continue
    
    return results

def clean_plate_text(text):
    """
    Limpia y normaliza el texto reconocido por OCR.
    """
    # Remover caracteres no alfanuméricos y convierte a mayúsculas
    text = re.sub(r'[^A-Z0-9]', '', text.upper())
    
    # Correcciones comunes de OCR (e.g., O leído como 0, I como 1, pero no implementado agresivamente)
    replacements = {
        'O': '0', 'I': '1', 'Z': '2', 'S': '5', 
        'B': '8', 'Q': '0', 'D': '0'
    }
    
    # solo se usa la limpieza RegEx
    cleaned = text
    
    # Solo retorna si la longitud del texto es razonable para una placa (mínimo 4 caracteres).
    return cleaned if len(cleaned) >= 4 else None

def recognize_plate_from_image(image_path):
    """
    Función principal 
    """
    try:
        # Verificación inicial del archivo y carga de la imagen
        if not os.path.exists(image_path):
            return None, "Error: Archivo de imagen no encontrado."

        img = cv2.imread(image_path)
        if img is None:
            return None, "Error: No se pudo cargar la imagen."

        # 1. Preprocesamiento (obtiene la imagen gris y múltiples versiones mejoradas)
        gray, processed_methods = preprocess_image(img)
        
        all_results = [] # Lista para almacenar todos los textos reconocidos de todas las pruebas
        
        # 2. Iteración sobre los métodos de preprocesamiento (la clave de la robustez)
        for idx, processed in enumerate(processed_methods):
            
            # 3. Buscar contornos candidatos en la versión preprocesada
            candidates = find_plate_contours(img, processed)
            
            # 4. Configuraciones de Tesseract a probar 
            #'tessedit_char_whitelist' mejora drásticamente la precisión.
            configs = [
                '--psm 7 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', # Trata como una sola línea
                '--psm 8 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', # Trata como una sola palabra
                '--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', # Bloque uniforme
                '--psm 11 --oem 3', # Búsqueda de texto disperso/sin orden
            ]
            
            # 5. Probar cada candidato de contorno (placa potencialmente encontrada)
            for contour in candidates:
                # Extrae y endereza el ROI
                roi = extract_roi(processed, contour)
                if roi is not None:
                    # Intenta el OCR con las diferentes configuraciones
                    results = ocr_recognize(roi, configs)
                    all_results.extend(results)
            
            # 6. También probar un ROI simple (centro de la imagen) como método de fallback
            h, w = processed.shape
            # Recorta el área central (80% de alto x 80% de ancho)
            roi_simple = processed[int(h*0.2):int(h*0.8), int(w*0.1):int(w*0.9)]
            if roi_simple.size > 0:
                results = ocr_recognize(roi_simple, configs)
                all_results.extend(results)
        
        # 7. Análisis de resultados 
        if not all_results:
            return None, "Error: No se pudo reconocer ninguna placa. Intenta con otra imagen más clara."
        
        # Encontrar el resultado más común (el texto que más se repitió entre todas las estrategias)
        from collections import Counter # Para contar la frecuencia de los resultados
        result_counts = Counter(all_results)
        best_result = result_counts.most_common(1)[0][0]
        confidence = result_counts[best_result] # Número de veces que se detectó
        
        return best_result, f"Placa reconocida: {best_result} (Confianza: {confidence} detecciones)"

    except pytesseract.TesseractNotFoundError:
        # Error específico si Tesseract no está instalado o la ruta es incorrecta.
        return None, "Error: Tesseract no se encuentra. Asegúrate de que está instalado y configurado correctamente."
    except Exception as e:
        # Captura cualquier otro error de procesamiento.
        return None, f"Error de procesamiento: {str(e)}"