import subprocess
import sys

from playwright.sync_api import sync_playwright


def ensure_chromium_installed():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()

        return True

    except Exception as error:
        if getattr(sys, "frozen", False):
            print("\nChromium de Playwright no está instalado.")
            print("El ejecutable debe incluir los navegadores de Playwright.")
            print(f"Detalles: {error}")
            return False

        print("\nChromium de Playwright no está instalado.")
        print("Instalando Chromium automáticamente...")

        try:
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=True
            )
            return True

        except Exception:
            print("Error al instalar Playwright Chromium automáticamente.")
            print("Por favor, instálalo manualmente:")
            print("python -m playwright install chromium")
            return False
