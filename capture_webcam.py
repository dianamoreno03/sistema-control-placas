# intento 1 utilizar la camara
import cv2
import os
import sys

# aqui se guardará la imagen para la prueba
OUTPUT_FILENAME = "static/test_placa_webcam.jpg"

def capture_and_save_image():
    # Intenta inicializar la cámara (casi siempre el índice 0)
    # 0 = Cámara integrada de Mac
    cap = cv2.VideoCapture(1) 

    if not cap.isOpened():
        print("Error: No se pudo abrir la cámara. Verifica permisos o si otra app la usa.")
        sys.exit(1)

    print("Cámara abierta. Presiona ESPACIO para tomar la foto. Presiona Q para salir.")

    # Asegura que la carpeta 'static' exista para guardar la imagen
    if not os.path.exists('static'):
        os.makedirs('static')

    while True:
        # Captura con la cámara
        ret, frame = cap.read()

        if not ret:
            print("Error: No se puede recibir la cámara.")
            break

        # Muestra la ventana de previsualización
        cv2.imshow('Previsualizacion - Presiona ESPACIO para tomar foto', frame)

        # Espera una tecla
        key = cv2.waitKey(1)

        # Si el usuario presiona ESPACIO, toma la foto
        if key == ord(' '):
            cv2.imwrite(OUTPUT_FILENAME, frame)
            print(f"Foto guardada como: {OUTPUT_FILENAME}")
            break
        
        # Si el usuario presiona Q, sale
        elif key == ord('q') or key == ord('Q'):
            break

    # Libera la cámara y cierra la ventana
    cap.release()
    cv2.destroyAllWindows()
    print("Captura finalizada.")

if __name__ == '__main__':
    capture_and_save_image()