from pathlib import Path

import torch
from torch.utils.data import Dataset

from transformers import (
    AutoTokenizer,
    AutoModelForTokenClassification,
    Trainer,
    TrainingArguments,
    DataCollatorForTokenClassification,
)

from datos_entrenamiento import ejemplos


# ==================================================
# 1. CONFIGURACIÓN
# ==================================================

MODELO_BASE = "dccuchile/bert-base-spanish-wwm-cased"

# Guarda el modelo en Empresa/modelo_medico_entrenado
RUTA_MODELO = (
    Path(__file__).resolve().parents[2]
    / "modelo_medico_entrenado"
)

ETIQUETAS_ENTIDADES = [
    "CODIGO_EPISODIO",
    "EDAD",
    "SEXO",
    "MOTIVO_CONSULTA",
    "TAS",
    "TAD",
    "PAM",
    "FREC_CARDIACA",
    "FREC_RESPIRATORIA",
    "SATURACION",
    "TEMPERATURA",
    "GLASGOW",
    "DOLOR",
    "LOCALIZACION_DOLOR",
]

etiquetas = ["O"]

for nombre in ETIQUETAS_ENTIDADES:
    etiquetas.append(f"B-{nombre}")
    etiquetas.append(f"I-{nombre}")

etiqueta_a_id = {
    etiqueta: indice
    for indice, etiqueta in enumerate(etiquetas)
}

id_a_etiqueta = {
    indice: etiqueta
    for etiqueta, indice in etiqueta_a_id.items()
}


# ==================================================
# 2. VALIDAR LOS EJEMPLOS
# ==================================================

def obtener_entidades(texto, entidades):
    posiciones = []

    for entidad in entidades:
        valor = entidad["texto"]
        etiqueta = entidad["etiqueta"]

        if etiqueta not in ETIQUETAS_ENTIDADES:
            raise ValueError(
                f"Etiqueta desconocida: {etiqueta}"
            )

        inicio = texto.find(valor)

        if inicio == -1:
            raise ValueError(
                f"No se encontró '{valor}' en el texto: {texto}"
            )

        fin = inicio + len(valor)

        posiciones.append({
            "inicio": inicio,
            "fin": fin,
            "etiqueta": etiqueta,
            "texto": valor,
        })

    posiciones.sort(key=lambda entidad: entidad["inicio"])

    for anterior, actual in zip(
        posiciones, posiciones[1:]
    ):
        if actual["inicio"] < anterior["fin"]:
            raise ValueError(
                "Hay entidades superpuestas: "
                f"'{anterior['texto']}' y '{actual['texto']}' "
                f"en el texto: {texto}"
            )

    return posiciones


# ==================================================
# 3. CREAR EL DATASET
# ==================================================

class DatosMedicos(Dataset):

    def __init__(self, ejemplos, tokenizador):
        self.datos = []

        for ejemplo in ejemplos:
            texto = ejemplo["texto"]

            entidades = obtener_entidades(
                texto,
                ejemplo["entidades"],
            )

            resultado = tokenizador(
                texto,
                return_offsets_mapping=True,
                truncation=True,
                max_length=128,
            )

            etiquetas_tokens = []

            for inicio, fin in resultado["offset_mapping"]:

                # Ignorar tokens especiales
                if inicio == fin:
                    etiquetas_tokens.append(-100)
                    continue

                etiqueta_token = "O"

                for entidad in entidades:
                    if (
                        inicio >= entidad["inicio"]
                        and fin <= entidad["fin"]
                    ):
                        if inicio == entidad["inicio"]:
                            etiqueta_token = (
                                "B-" + entidad["etiqueta"]
                            )
                        else:
                            etiqueta_token = (
                                "I-" + entidad["etiqueta"]
                            )
                        break

                etiquetas_tokens.append(
                    etiqueta_a_id[etiqueta_token]
                )

            self.datos.append({
                "input_ids": resultado["input_ids"],
                "attention_mask": resultado["attention_mask"],
                "labels": etiquetas_tokens,
            })

    def __len__(self):
        return len(self.datos)

    def __getitem__(self, indice):
        return {
            clave: torch.tensor(valor)
            for clave, valor in self.datos[indice].items()
        }


# ==================================================
# 4. CARGAR EL TOKENIZADOR
# ==================================================

print("Cargando tokenizador BETO...")

tokenizador = AutoTokenizer.from_pretrained(MODELO_BASE)

print("Cantidad de ejemplos:", len(ejemplos))
print("Cantidad de etiquetas:", len(etiquetas))


# ==================================================
# 5. PREPARAR LOS DATOS
# ==================================================

dataset = DatosMedicos(
    ejemplos,
    tokenizador,
)

print("Dataset preparado correctamente.")
print("Cantidad de registros:", len(dataset))


# ==================================================
# 6. CARGAR EL MODELO BASE
# ==================================================

print("Cargando modelo base...")

modelo = AutoModelForTokenClassification.from_pretrained(
    MODELO_BASE,
    num_labels=len(etiquetas),
    label2id=etiqueta_a_id,
    id2label=id_a_etiqueta,
)

print("Modelo preparado correctamente.")
print("Cantidad de etiquetas:", modelo.config.num_labels)


# ==================================================
# 7. PREPARAR EL ENTRENAMIENTO
# ==================================================

colador = DataCollatorForTokenClassification(
    tokenizer=tokenizador,
)

argumentos = TrainingArguments(
    output_dir=str(
        Path(__file__).resolve().parent
        / "resultados_entrenamiento"
    ),
    num_train_epochs=20,
    per_device_train_batch_size=4,
    learning_rate=3e-5,
    weight_decay=0.01,
    save_strategy="no",
    report_to="none",
)


# ==================================================
# 8. CREAR EL ENTRENADOR
# ==================================================

entrenador = Trainer(
    model=modelo,
    args=argumentos,
    train_dataset=dataset,
    data_collator=colador,
)

print("Entrenador creado correctamente.")


# ==================================================
# 9. INICIAR EL ENTRENAMIENTO
# ==================================================

print("\nComenzando el entrenamiento...")

resultado_entrenamiento = entrenador.train()

print("\nEntrenamiento terminado.")
print("Resultado:", resultado_entrenamiento.metrics)


# ==================================================
# 10. GUARDAR EL MODELO ENTRENADO
# ==================================================

RUTA_MODELO.mkdir(
    parents=True,
    exist_ok=True,
)

entrenador.save_model(str(RUTA_MODELO))
tokenizador.save_pretrained(str(RUTA_MODELO))

print("\nModelo guardado correctamente.")
print(f"Ruta: {RUTA_MODELO}")

