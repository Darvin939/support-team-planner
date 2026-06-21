def format_employee_name(last_name, first_name, middle_name=None):
    """
    Форматирует ФИО сотрудника в формат: Фамилия И.О.
    Пример: Иванов И.И.
    """
    if not last_name or not first_name:
        return ''

    # Берем первую букву имени с точкой
    first_initial = first_name[0].upper() + '.'

    # Если есть отчество, берем первую букву с точкой
    if middle_name:
        middle_initial = middle_name[0].upper() + '.'
        return f"{last_name} {first_initial} {middle_initial}"
    else:
        return f"{last_name} {first_initial}"