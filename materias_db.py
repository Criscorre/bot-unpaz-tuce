# materias_db.py — Materias disponibles en el cuatrimestre actual
# Actualizado con datos oficiales 1er cuatrimestre 2026.
# Formato: [materia, comisión, día, hora_inicio, hora_fin, modalidad, //, //, aula]

LISTA_HORARIOS = [
    ["Tecnología y Sociedad", "B1", "Martes",    "14:00:00", "18:00:00", "100% Presencial",             "//", "//", "110 PUEYRREDON"],
    ["Tecnología y Sociedad", "C1", "Miercoles", "18:00:00", "22:00:00", "100% Presencial",             "//", "//", "104 ALEM"],
    ["Tecnología y Sociedad", "B2", "Jueves",    "14:00:00", "18:00:00", "100% Presencial",             "//", "//", "114 PUEYRREDON"],

    ["Inglés I", "C1", "Lunes",   "18:00:00", "22:00:00", "50% Presencial - 50% Virtual", "//", "//", "60 ARREGUI"],
    ["Inglés I", "B1", "Lunes",   "14:00:00", "18:00:00", "50% Presencial - 50% Virtual", "//", "//", "60 ARREGUI"],
    ["Inglés I", "B2", "Viernes", "14:00:00", "18:00:00", "50% Presencial - 50% Virtual", "//", "//", "03 ARREGUI"],

    ["Principios de Economía", "C1", "Jueves",   "18:00:00", "22:00:00", "100% Presencial", "//", "//", "211-212 PUEYRREDON"],
    ["Principios de Economía", "A2", "Viernes",  "08:00:00", "12:00:00", "100% Presencial", "//", "//", "101 ARREGUI"],
    ["Principios de Economía", "C2", "Martes",   "18:00:00", "22:00:00", "100% Presencial", "//", "//", "SUM - PUEYRREDON"],
    ["Principios de Economía", "A1", "Jueves",   "08:00:00", "12:00:00", "100% Presencial", "//", "//", "211-212 PUEYRREDON"],
    ["Principios de Economía", "B1", "Jueves",   "14:00:00", "18:00:00", "100% Presencial", "//", "//", "209-210 PUEYRREDON"],

    ["Comunicación Institucional", "C1", "Viernes", "18:00:00", "22:00:00", "100% Presencial", "//", "//", "104 ALEM"],
    ["Comunicación Institucional", "B1", "Viernes", "14:00:00", "18:00:00", "100% Presencial", "//", "//", "113 ALEM"],

    ["Internet: Infraestructura y Redes", "C1", "Viernes", "18:00:00", "22:00:00", "50% Presencial - 50% Virtual", "//", "//", "103 ALEM"],
    ["Internet: Infraestructura y Redes", "B1", "Viernes", "14:00:00", "18:00:00", "50% Presencial - 50% Virtual", "//", "//", "103 ALEM"],

    ["Semántica de las Interfaces", "C1", "Lunes",     "18:00:00", "22:00:00", "50% Presencial - 50% Virtual", "//", "//", "A confirmar"],
    ["Semántica de las Interfaces", "B1", "Miercoles", "14:00:00", "18:00:00", "50% Presencial - 50% Virtual", "//", "//", "116 ALEM"],
    ["Semántica de las Interfaces", "A1", "Sabado",    "10:00:00", "14:00:00", "50% Presencial - 50% Virtual", "//", "//", "210 ALEM"],

    ["Introducción al Comercio Electrónico", "B1", "Jueves", "14:00:00", "18:00:00", "100% Presencial", "//", "//", "01 ALEM"],
    ["Introducción al Comercio Electrónico", "C2", "Martes", "18:00:00", "22:00:00", "100% Presencial", "//", "//", "08 ARREGUI"],
    ["Introducción al Comercio Electrónico", "C1", "Jueves", "18:00:00", "22:00:00", "100% Presencial", "//", "//", "01 ALEM"],

    ["Usabilidad, Seguridad y Estándares Web", "B1", "Martes",    "14:00:00", "18:00:00", "50% Presencial - 50% Virtual", "//", "//", "A confirmar"],
    ["Usabilidad, Seguridad y Estándares Web", "C2", "Miercoles", "18:00:00", "22:00:00", "50% Presencial - 50% Virtual", "//", "//", "204 ALEM"],
    ["Usabilidad, Seguridad y Estándares Web", "C1", "Martes",    "18:00:00", "22:00:00", "50% Presencial - 50% Virtual", "//", "//", "SALA MULTIMEDIA"],

    ["Investigación de Mercado", "C1", "Viernes", "18:00:00", "22:00:00", "50% Presencial - 50% Virtual", "//", "//", "14 ARREGUI"],

    ["Marco Legal de Negocios Electrónicos", "C1", "Lunes", "18:00:00", "22:00:00", "100% Presencial", "//", "//", "101 PUEYRREDON"],
    ["Marco Legal de Negocios Electrónicos", "B1", "Lunes", "14:00:00", "18:00:00", "100% Presencial", "//", "//", "03 PUEYRREDON - 101 PUEYRREDON"],

    ["Gestión del Conocimiento", "C2", "Martes", "18:00:00", "22:00:00", "50% Presencial - 50% Virtual", "//", "//", "61 ARREGUI"],
    ["Gestión del Conocimiento", "C1", "Lunes",  "18:00:00", "22:00:00", "50% Presencial - 50% Virtual", "//", "//", "08 ARREGUI"],

    ["Formulación, Incubación y Evaluación de Proyectos", "C1", "Martes", "18:00:00", "22:00:00", "50% Presencial - 50% Virtual", "//", "//", "02 ARREGUI - 31 ARREGUI"],

    ["Métricas del Mundo Digital", "C1", "Lunes", "18:00:00", "22:00:00", "50% Presencial - 50% Virtual", "//", "//", "111 ALEM"],

    ["Desarrollo de Productos y Servicios", "C1", "Miercoles", "18:00:00", "22:00:00", "100% Presencial", "//", "//", "60 ARREGUI"],

    ["Desarrollos para Dispositivos Móviles", "C1", "Jueves", "18:00:00", "22:00:00", "100% Presencial", "//", "//", "06 ALEM"],

    ["Marketing Digital", "C1", "Miercoles", "18:00:00", "22:00:00", "50% Presencial - 50% Virtual", "//", "//", "204 ALEM"],

    ["Taller de Práctica Integradora", "C1", "Jueves", "18:00:00", "22:00:00", "50% Presencial - 50% Virtual", "//", "//", "103 ALEM"],

    ["Competencias Emprendedoras", "C1", "Lunes", "18:00:00", "22:00:00", "50% Presencial - 50% Virtual", "//", "//", "06 ARREGUI"],

    ["Gestión de Proyectos", "C1", "Martes", "18:00:00", "22:00:00", "50% Presencial - 50% Virtual", "//", "//", "68 ARREGUI"],
    ["Gestión de Proyectos", "B1", "Martes", "14:00:00", "18:00:00", "50% Presencial - 50% Virtual", "//", "//", "39 ARREGUI"],
]
