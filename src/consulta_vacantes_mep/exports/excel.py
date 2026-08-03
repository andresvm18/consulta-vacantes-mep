from datetime import datetime

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from consulta_vacantes_mep.utils.paths import OUTPUT_DIR


def format_worksheet(worksheet):
    header_fill = PatternFill(
        start_color="1F4E78",
        end_color="1F4E78",
        fill_type="solid"
    )

    header_font = Font(
        color="FFFFFF",
        bold=True
    )

    for cell in worksheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions

    for column_cells in worksheet.columns:
        max_length = 0
        column_letter = get_column_letter(column_cells[0].column)

        for cell in column_cells:
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))

        adjusted_width = min(max_length + 2, 45)
        worksheet.column_dimensions[column_letter].width = adjusted_width


def export_data_to_excel(
    vacancies,
    appointments=None,
    filename_prefix="vacantes"
):
    if not vacancies:
        print("\nNo hay datos para exportar.")
        return None

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"{filename_prefix}_{timestamp}.xlsx"
    file_path = OUTPUT_DIR / filename

    vacancies_df = pd.DataFrame(vacancies)
    appointments_df = pd.DataFrame(appointments if appointments else [])

    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        vacancies_df.to_excel(
            writer,
            sheet_name="Vacantes",
            index=False
        )

        appointments_df.to_excel(
            writer,
            sheet_name="Nombramientos",
            index=False
        )

        workbook = writer.book

        for sheet_name in workbook.sheetnames:
            worksheet = workbook[sheet_name]
            format_worksheet(worksheet)

    return file_path