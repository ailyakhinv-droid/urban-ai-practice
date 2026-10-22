"""
Модуль для расчёта плотности населения.

Плотность населения — это среднее число жителей, приходящееся
на единицу площади:

    плотность = население / площадь

Если население задано в человеках (чел.), а площадь — в гектарах (га),
то результат получается в жителях на гектар (чел./га).
"""

POPULATION = 1200  # население, чел.
AREA_HECTARES = 8.0  # площадь территории, га


def calculate_density(population: float, area: float) -> float:
    """
    Рассчитывает плотность населения.

    Parameters
    ----------
    population : float
        Число жителей, чел.
    area : float
        Площадь территории, га.

    Returns
    -------
    float
        Плотность населения, чел./га.

    Raises
    ------
    ValueError
        Если площадь меньше или равна нулю.
    """
    if area <= 0:
        raise ValueError("Площадь должна быть больше нуля")
    return population / area


def main() -> None:
    """Выводит плотность населения для исходных данных."""
    density = calculate_density(POPULATION, AREA_HECTARES)
    print(f"Население: {POPULATION} чел.")
    print(f"Площадь территории: {AREA_HECTARES:g} га")
    print(f"Плотность населения: {density:g} чел./га")


if __name__ == "__main__":
    main()
