# app/lpr_service.py
import cv2
import pytesseract
import numpy as np
import os
import re

# --- para leer los archivos /prox camara 
try:                                        
    pytesseract.pytesseract.tesseract_cmd = r'/opt/homebrew/bin/tesseract' 
except:
    pass 

def preprocess_image(img):
    """
    Preprocesamiento múltiple para la detección
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # metodos utilizados para la deteccion
    methods = []
    
    # Método 1: Bilateral filter + threshold adaptativo
    blur1 = cv2.bilateralFilter(gray, 11, 17, 17)
    thresh1 = cv2.adaptiveThreshold(blur1, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                     cv2.THRESH_BINARY, 11, 2)
    methods.append(thresh1)
    
    # Método 2: Gaussian blur + Otsu
    blur2 = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh2 = cv2.threshold(blur2, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    methods.append(thresh2)
    
    # Método 3: Mejora de contraste
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    methods.append(enhanced)
    
    # Método 4: Original con bilateral
    blur4 = cv2.bilateralFilter(gray, 13, 15, 15)
    methods.append(blur4)
    
    return gray, methods

def find_plate_contours(img, gray):
    """
    Búsqueda de contornos con múltiples estrategias
    """
    candidates = []
    
    # Estrategia 1: Canny con diferentes umbrales
    for low, high in [(30, 200), (50, 150), (70, 210)]:
        edged = cv2.Canny(gray, low, high)
        contours, _ = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:40]
        
        for c in contours:
            perimeter = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.018 * perimeter, True)
            
            # Buscar rectángulos (4 lados)
            if len(approx) == 4:
                x, y, w, h = cv2.boundingRect(approx)
                aspect_ratio = w / float(h)
                
                # Ratio típico de placas: entre 1.5 y 5
                if 1.5 <= aspect_ratio <= 5.5 and w > 50 and h > 15:
                    candidates.append((approx, cv2.contourArea(c), aspect_ratio))
    
    # Ordenar por área
    candidates.sort(key=lambda x: x[1], reverse=True)
    
    return [c[0] for c in candidates[:5]]  # Top 5 candidatos

def extract_roi(gray, contour):
    """
    Extrae la región de interés con transformación de perspectiva
    """
    try:
        pts = contour.reshape(4, 2)
        rect = np.zeros((4, 2), dtype="float32")
        
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        
        (tl, tr, br, bl) = rect
        widthA = np.linalg.norm(br - bl)
        widthB = np.linalg.norm(tr - tl)
        maxWidth = max(int(widthA), int(widthB))
        
        heightA = np.linalg.norm(tr - br)
        heightB = np.linalg.norm(tl - bl)
        maxHeight = max(int(heightA), int(heightB))
        
        # Evitar dimensiones inválidas
        if maxWidth < 20 or maxHeight < 10:
            return None
        
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]], dtype="float32")
        
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(gray, M, (maxWidth, maxHeight))
        
        return warped
    except:
        return None

def ocr_recognize(roi, config_set):
    """
    Intenta OCR con múltiples configuraciones
    """
    results = []
    
    for config in config_set:
        try:
            text = pytesseract.image_to_string(roi, config=config)
            cleaned = clean_plate_text(text)
            if cleaned:
                results.append(cleaned)
        except:
            continue
    
    return results

def clean_plate_text(text):
    """
    Limpieza del texto reconocido
    """
    # Remover caracteres no alfanuméricos
    text = re.sub(r'[^A-Z0-9]', '', text.upper())
    
    # Correcciones comunes de OCR
    replacements = {
        'O': '0', 'I': '1', 'Z': '2', 'S': '5', 
        'B': '8', 'Q': '0', 'D': '0'
    }
    
    # Solo aplicar si tiene sentido (letras en posiciones numéricas)
    cleaned = text
    
    return cleaned if len(cleaned) >= 4 else None

def recognize_plate_from_image(image_path):
    """
    Sistema LPR  - Multi-estrategia
    """
    try:
        if not os.path.exists(image_path):
            return None, "Error: Archivo de imagen no encontrado."

        img = cv2.imread(image_path)
        if img is None:
            return None, "Error: No se pudo cargar la imagen."

        # Preprocesamiento
        gray, processed_methods = preprocess_image(img)
        
        all_results = []
        
        # Probar cada método de preprocesamiento
        for idx, processed in enumerate(processed_methods):
            # Buscar contornos candidatos
            candidates = find_plate_contours(img, processed)
            
            # Configuraciones de Tesseract a probar
            configs = [
                '--psm 7 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                '--psm 8 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                '--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                '--psm 11 --oem 3',
            ]
            
            # Probar cada candidato de contorno
            for contour in candidates:
                roi = extract_roi(processed, contour)
                if roi is not None:
                    results = ocr_recognize(roi, configs)
                    all_results.extend(results)
            
            # También probar ROI simple 
            h, w = processed.shape
            roi_simple = processed[int(h*0.2):int(h*0.8), int(w*0.1):int(w*0.9)]
            if roi_simple.size > 0:
                results = ocr_recognize(roi_simple, configs)
                all_results.extend(results)
        
        # Análisis de resultados
        if not all_results:
            return None, "Error: No se pudo reconocer ninguna placa. Intenta con otra imagen más clara."
        
        # Encontrar el resultado más común (más confiable)
        from collections import Counter
        result_counts = Counter(all_results)
        best_result = result_counts.most_common(1)[0][0]
        confidence = result_counts[best_result]
        
        return best_result, f"Placa reconocida: {best_result} (Confianza: {confidence} detecciones)"

    except pytesseract.TesseractNotFoundError:
        return None, "Error: no se puede leer"
    except Exception as e:
        return None, f"Error de procesamiento: {str(e)}"