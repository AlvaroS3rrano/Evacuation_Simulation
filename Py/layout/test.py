from shapely.geometry import Polygon

# Datos originales
complete_area = Polygon([(0, 0), (0, 50), (30, 50), (30, 0)])

obstacles = [
    Polygon([(0, 4), (2, 4), (2, 10), (5, 10), (5, 45), (10, 45), (10, 48), (20, 48), (20, 45), (25, 45),
             (25, 4), (30, 4), (30, 50), (0, 50), (0, 4)]),
    Polygon([(4, 0), (23, 0), (23, 4), (10, 4), (10, 7), (4, 7)]),  # 1
    Polygon([(7, 9), (10, 9), (10, 22.9), (10.5, 22.9), (10.5, 23), (9, 23), (9, 24), (7, 24)]),  # 2
    Polygon([(20, 6), (23, 6), (23, 23), (19.5, 23), (19.5, 22.9), (20, 22.9)]),
    Polygon([(12, 6), (18, 6), (18, 11), (12, 11)]),  # 3
    Polygon([(13, 13), (17, 13), (17, 19), (13, 19)]),
    Polygon([(13, 21), (17, 21), (17, 22.9), (17.5, 22.9), (17.5, 23), (17, 23), (12.5, 23),
             (12.5, 22.9), (13, 22.9)]),  # 4
    Polygon([(7, 41), (7, 35.5), (7.1, 35.5), (7.1, 41), (14, 40.9), (14, 41), (12, 41), (12, 43), (7, 43)]),
    Polygon([(7, 33.5), (7, 26), (11, 26), (11, 25), (14, 25), (14, 25.1), (11.1, 25.1), (11.1, 26.1),
             (7.1, 26.1), (7.1, 33.5)]),
    Polygon([(16, 25), (23, 25), (23, 29.5), (22.9, 29.5), (22.9, 25.1), (16, 25.1)]),
    Polygon([(22.9, 31.5), (23, 31.5), (23, 34.5), (22.9, 34.5)]),
    Polygon([(22.9, 36.5), (23, 36.5), (23, 43), (18, 43), (18, 41), (16, 41), (16, 40.9), (18.1, 40.9),
             (18.1, 42.9), (22.9, 42.9)]),
    Polygon([(4, 2), (2, 2), (2, 2.1), (4, 2.1)]),
    Polygon([(23, 2), (28, 2), (28, 2.1), (23, 2.1)]),
]

def rotar_180(poli, ancho=30, alto=50):
    # Transformación: (x, y) -> (ancho - x, alto - y)
    coords_rotadas = [(ancho - x, alto - y) for x, y in poli.exterior.coords]
    return Polygon(coords_rotadas)

# Aplicar la rotación 180° al área completa y a los obstáculos
complete_area_rotada = rotar_180(complete_area)
obstacles_rotados = [rotar_180(obs) for obs in obstacles]

# Función para formatear la salida como en tus datos de entrada
def formatear_poligono(poli):
    # Se obtiene la lista de coordenadas sin repetir el primer punto (cierre)
    coords = list(poli.exterior.coords)
    # Si el primer y último punto son iguales, se eliminan los duplicados en la salida
    if coords[0] == coords[-1]:
        coords = coords[:-1]
    return f"Polygon({coords}),"

# Imprimir el área completa y los obstáculos en el formato deseado
print("complete_area =", formatear_poligono(complete_area_rotada))
print("\nobstacles = [")
print("\n".join("    " + formatear_poligono(obs) for obs in obstacles_rotados))
print("]")
