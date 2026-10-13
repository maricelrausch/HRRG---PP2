# Reglas

def parametros_paciente(codigo_episodio, edad, sexo, tas, tad, frec_cardiaca, saturacion, glasgow, dolor, localizacion_dolor):
    # Validar que los parámetros estén dentro de los rangos establecidos
    # (1) Episodio
    # El codigo es generado por el sistema, no es necesario validarlo, pero se puede validar que sea un string y que no esté vacío.
    codigo_episodio = str(codigo_episodio)

    # Validar edad
    if not (0 <= edad <= 120):
        return False, "Edad fuera de rango"

    # Validar sexo    
    elif sexo not in ["M", "F"]:
        return False, "Sexo inválido"

    # (2) Motivo de consulta

    # (3) Signos vitales
    # Tensión arterial sistólica (TAS) // Rango entre  50 a 260 mmHg
    elif not (50 <= tas <= 260):
        return False, "TAS fuera de rango"

    # Tensión arterial diastólica (TAD) // Rango entre 20 y 160 mmHg
    elif not (20 <= tad <= 160):
        return False, "TAD fuera de rango"

    # Frecuencia cardíaca // Rango entre 20 y 250 bpm
    elif not (20 <= frec_cardiaca <= 250):
        return False, "Frecuencia cardíaca fuera de rango"

    # Saturación de oxígeno // Rango entre 0 y 100%
    elif not (0 <= saturacion <= 100):
        return False, "Saturación fuera de rango"



    # (4) Conciencia y dolor
    # Glasgow // Rango entre 3 y 15
    elif not (3 <= glasgow <= 15):
        return False, "Glasgow fuera de rango"
    
    # Dolor // Rango entre 0 a 10       
    elif dolor not in range(0, 11):
        return False, "Dolor inválido"

    # Localización del dolor // Validar que sea una de las opciones válidas    
    elif localizacion_dolor not in ["cabeza", "torso", "extremidades"]:
        return False, "Localización del dolor inválida"

    # (5) Banderas Rojas


    # Si todos los parámetros son válidos
    return True, "Parámetros válidos"


def manchester(parametros):
    if parametros["glasgow"] < 8:
        return "Prioridad alta"
    
    elif parametros["tas"] < 90:
        return "Prioridad media"
    
    else:
        return "Prioridad baja"

# Rojo : Hemorragia 
# Naranga: Vomitos, frecuencia muy alta
# Amarillo: Dolor, fiebre, tos
